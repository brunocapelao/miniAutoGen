"""miniautogen run command."""

from __future__ import annotations

import sys

import click

from miniautogen.cli.config import require_project_config
from miniautogen.cli.errors import PipelineNotFoundError
from miniautogen.cli.main import run_async
from miniautogen.cli.output import echo_error, echo_info, echo_json, echo_success


def _resolve_input(input_value: str | None) -> str | None:
    """Resolve input from --input flag, @file reference, or stdin.

    - If input_value starts with '@', reads from file path.
    - If input_value is provided, uses it as-is.
    - If None and stdin has data, reads from stdin.
    - Otherwise returns None.
    """
    if input_value is not None:
        if input_value.startswith("@"):
            file_path = input_value[1:]
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
def run_command(
    pipeline_name: str,
    timeout: float | None,
    output_format: str,
    verbose: bool,
    input_value: str | None,
    resume: str | None,
) -> None:
    """Execute a pipeline headlessly."""
    from miniautogen.cli.services.run_pipeline import execute_pipeline

    root, config = require_project_config()

    if pipeline_name not in config.pipelines:
        raise PipelineNotFoundError(
            f"Pipeline '{pipeline_name}' not found in config"
        )

    # Resolve input
    try:
        pipeline_input = _resolve_input(input_value)
    except click.BadParameter as exc:
        echo_error(str(exc))
        raise SystemExit(1)

    if resume:
        echo_info(f"Resuming run '{resume}' for pipeline '{pipeline_name}'...")

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

    if output_format == "json":
        echo_json(result)
    else:
        status = result.get("status", "unknown")
        if status == "completed":
            echo_success(
                f"Pipeline '{pipeline_name}' completed successfully"
            )
            if result.get("events"):
                echo_success(f"Events emitted: {result['events']}")
        else:
            echo_error(
                f"Pipeline '{pipeline_name}' failed: "
                f"{result.get('error', 'unknown')}"
            )
            raise SystemExit(1)
