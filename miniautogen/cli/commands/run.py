"""miniautogen run command."""

from __future__ import annotations

import contextlib
import os
import sys
import time
from pathlib import Path

import click

from miniautogen.cli.config import require_project_config
from miniautogen.cli.errors import PipelineNotFoundError
from miniautogen.cli.main import run_async
from miniautogen.cli.output import echo_error, echo_info, echo_json, echo_success, echo_warning
from miniautogen.cli.services.event_sinks import _select_ui_sink


def _wait_for_console_shutdown() -> None:
    """Block until Ctrl+C; uvicorn's daemon thread keeps serving."""
    echo_info("Console still running. Press Ctrl+C to exit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        echo_info("Shutting down console...")


def _resolve_input(input_value: str | None) -> str | None:
    """Resolve input from --input flag, @file reference, or stdin."""
    if input_value is not None:
        if input_value.startswith("@"):
            file_path = Path(input_value[1:]).resolve()
            # Restrict to project directory
            project_root = Path.cwd().resolve()
            if not file_path.is_relative_to(project_root):
                msg = f"Input file must be within the project directory: {file_path}"
                raise click.BadParameter(msg)
            try:
                with open(file_path) as f:
                    return f.read()
            except FileNotFoundError:
                msg = f"Input file not found: {file_path}"
                raise click.BadParameter(msg)
            except OSError as exc:
                msg = f"Cannot read input file: {exc}"
                raise click.BadParameter(msg)
        return input_value

    # Check if stdin has data (not a TTY)
    if not sys.stdin.isatty():
        return sys.stdin.read()

    return None


@click.command("run")
@click.argument("pipeline_name", default="main")
@click.option(
    "--timeout",
    type=float,
    default=None,
    help="Timeout sec. Checkpoint saved on timeout/Ctrl+C for --resume. Double Ctrl+C skips save.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.option(
    "--verbose",
    is_flag=True,
    default=False,
    help="Verbose output.",
)
@click.option(
    "--input",
    "input_value",
    default=None,
    help="Input text or @file path for the pipeline.",
)
@click.option(
    "--resume",
    default=None,
    help="Resume a previous run from checkpoint (run_id). Works for cancelled and timed-out runs.",
)
@click.option(
    "--explain",
    is_flag=True,
    default=False,
    help="Show execution plan and decision logic before running.",
)
@click.option(
    "--console",
    is_flag=True,
    default=False,
    help="Open web console dashboard during execution.",
)
@click.option(
    "--port",
    "console_port",
    type=int,
    default=8080,
    help="Port for the web console (default: 8080).",
)
def run_command(
    pipeline_name: str = "main",
    timeout: float | None = None,
    output_format: str = "text",
    verbose: bool = False,
    input_value: str | None = None,
    resume: str | None = None,
    explain: bool = False,
    console: bool = False,
    console_port: int = 8080,
) -> None:
    """Execute a pipeline headlessly."""
    from miniautogen.cli.services.run_pipeline import execute_pipeline

    root, config = require_project_config()

    if pipeline_name not in config.pipelines:
        raise PipelineNotFoundError(
            f"Flow '{pipeline_name}' not found in config",
            hint="Run 'miniautogen flow list' to see available flows.",
        )

    # Resolve input
    try:
        pipeline_input = _resolve_input(input_value)
    except click.BadParameter as exc:
        echo_error(str(exc))
        raise SystemExit(1)

    # Console mode: start web server in background
    console_server = None
    console_provider = None
    console_event_sink = None
    if console:
        import webbrowser

        from miniautogen.api import create_app
        from miniautogen.tui.data_provider import DashDataProvider

        console_provider = DashDataProvider(root)
        console_app = create_app(provider=console_provider, mode="embedded")
        console_event_sink = getattr(console_app.state, "event_sink", None)

        import threading

        import uvicorn

        server_config = uvicorn.Config(
            console_app, host="127.0.0.1", port=console_port, log_level="warning"
        )
        console_server = uvicorn.Server(server_config)
        server_thread = threading.Thread(target=console_server.run, daemon=True)
        server_thread.start()

        url = f"http://localhost:{console_port}"
        echo_info(f"Console running at {url}")
        webbrowser.open(url)

    # --explain mode: show execution plan then proceed
    if explain:
        from miniautogen.cli.services.pipeline_ops import show_pipeline

        try:
            pdata = show_pipeline(root, pipeline_name)
        except KeyError:
            pdata = {}

        target = config.pipelines[pipeline_name].target
        mode = pdata.get("mode", "unknown")
        participants = pdata.get("participants", [])
        leader = pdata.get("leader")

        echo_info(f"Loading config from {root / 'miniautogen.yaml'}")
        echo_info(f"Resolved flow '{pipeline_name}' -> {target}")
        echo_info(f"Flow mode: {mode}")
        if participants:
            echo_info(f"Participants: {participants}")
        if leader:
            echo_info(f"Leader: {leader}")
        if pdata.get("max_rounds"):
            echo_info(f"Max rounds: {pdata['max_rounds']}")
        if timeout:
            echo_info(f"Timeout: {timeout}s")
        if pipeline_input:
            preview = pipeline_input[:80] + ("..." if len(pipeline_input) > 80 else "")
            echo_info(f"Input: {preview}")
        if resume:
            echo_info(f"Resuming from checkpoint: {resume}")
        click.echo("")

    if resume:
        echo_info(f"Resuming run '{resume}' for flow '{pipeline_name}'...")

    ui_sink = _select_ui_sink(output_format=output_format, verbose=verbose)

    from miniautogen.cli.services.rich_live_sink import RichLiveEventSink

    cm = ui_sink if isinstance(ui_sink, RichLiveEventSink) else contextlib.nullcontext()

    try:
        with cm:
            try:
                result = run_async(
                    execute_pipeline,
                    config,
                    pipeline_name,
                    root,
                    timeout=timeout,
                    verbose=verbose,
                    pipeline_input=pipeline_input,
                    resume_run_id=resume,
                    event_sink=ui_sink,
                    console_event_sink=console_event_sink,
                )
            except KeyboardInterrupt:
                echo_warning("Saving checkpoint before exit...")
                raise SystemExit(130)
            except TimeoutError:
                echo_warning("Timeout reached. Checkpoint saved (use --resume to continue).")
                raise SystemExit(124)
    except KeyboardInterrupt:
        # Handle Ctrl+C during Rich Live exit
        raise SystemExit(130)

    if output_format == "json":
        echo_json(result)
    else:
        status = result.get("status", "unknown")
        events = result.get("events", 0)
        if status == "completed":
            echo_success(f"Flow '{pipeline_name}' completed successfully")
            # Show pipeline output if available
            output = result.get("output")
            if isinstance(output, dict) and "output" in output:
                click.echo(f"\n{output['output']}")
            elif isinstance(output, str):
                click.echo(f"\n{output}")
            if events:
                echo_info(f"Events emitted: {events}")
        else:
            echo_error(f"Flow '{pipeline_name}' failed: {result.get('error', 'unknown')}")
            if console and console_server:
                _wait_for_console_shutdown()
            raise SystemExit(1)

    if console and console_server:
        _wait_for_console_shutdown()
