"""miniautogen run command."""

from __future__ import annotations

import sys
import threading
import time

from pathlib import Path

import click

from miniautogen.cli.config import require_project_config
from miniautogen.cli.errors import PipelineNotFoundError
from miniautogen.cli.main import run_async
from miniautogen.cli.output import echo_error, echo_info, echo_json, echo_success, echo_warning


def _resolve_input(input_value: str | None) -> str | None:
    """Resolve input from --input flag, @file reference, or stdin."""
    if input_value is not None:
        if input_value.startswith("@"):
            file_path = Path(input_value[1:]).resolve()
            # Restrict to project directory
            project_root = Path.cwd().resolve()
            if not str(file_path).startswith(str(project_root)):
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


class _Spinner:
    """Simple terminal spinner for pipeline execution."""

    _FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def __init__(self, message: str) -> None:
        self._message = message
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def update(self, message: str) -> None:
        self._message = message

    def stop(self, final: str = "") -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)
        # Clear spinner line
        click.echo(f"\r\033[K{final}", nl=bool(final))

    def _spin(self) -> None:
        idx = 0
        while not self._stop.is_set():
            frame = self._FRAMES[idx % len(self._FRAMES)]
            click.echo(f"\r{frame} {self._message}", nl=False)
            idx += 1
            time.sleep(0.08)


@click.command("run")
@click.argument("pipeline_name", default="main")
@click.option(
    "--timeout",
    type=float,
    default=None,
    help="Timeout in seconds.",
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
    "--input", "input_value",
    default=None,
    help="Input text or @file path for the pipeline.",
)
@click.option(
    "--resume",
    default=None,
    help="Resume a previous run from checkpoint (run_id).",
)
@click.option(
    "--explain",
    is_flag=True,
    default=False,
    help="Show execution plan and decision logic before running.",
)
def run_command(
    pipeline_name: str,
    timeout: float | None,
    output_format: str,
    verbose: bool,
    input_value: str | None,
    resume: str | None,
    explain: bool,
) -> None:
    """Execute a pipeline headlessly."""
    from miniautogen.cli.services.run_pipeline import execute_pipeline

    root, config = require_project_config()

    if pipeline_name not in config.pipelines:
        raise PipelineNotFoundError(
            f"Pipeline '{pipeline_name}' not found in config",
            hint=f"Run 'miniautogen pipeline list' to see available pipelines.",
        )

    # Resolve input
    try:
        pipeline_input = _resolve_input(input_value)
    except click.BadParameter as exc:
        echo_error(str(exc))
        raise SystemExit(1)

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
        echo_info(f"Resolved pipeline '{pipeline_name}' -> {target}")
        echo_info(f"Pipeline mode: {mode}")
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
        echo_info(f"Resuming run '{resume}' for pipeline '{pipeline_name}'...")

    # Start spinner for interactive terminals
    spinner = None
    use_spinner = output_format == "text" and sys.stderr.isatty() and not verbose
    if use_spinner:
        spinner = _Spinner(f"Running pipeline '{pipeline_name}'...")
        spinner.start()

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
        )
    finally:
        if spinner:
            spinner.stop()

    if output_format == "json":
        echo_json(result)
    else:
        status = result.get("status", "unknown")
        events = result.get("events", 0)
        if status == "completed":
            echo_success(
                f"Pipeline '{pipeline_name}' completed successfully"
            )
            if events:
                echo_info(f"Events emitted: {events}")
        else:
            echo_error(
                f"Pipeline '{pipeline_name}' failed: "
                f"{result.get('error', 'unknown')}"
            )
            raise SystemExit(1)
