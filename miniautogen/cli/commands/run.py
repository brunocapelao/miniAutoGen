"""miniautogen run command."""

from __future__ import annotations

from pathlib import Path

import click

from miniautogen.cli.config import CONFIG_FILENAME, find_project_root, load_config
from miniautogen.cli.errors import PipelineNotFoundError, ProjectNotFoundError
from miniautogen.cli.main import run_async
from miniautogen.cli.output import echo_error, echo_json, echo_success


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
def run_command(
    pipeline_name: str,
    timeout: float | None,
    output_format: str,
    verbose: bool,
) -> None:
    """Execute a pipeline headlessly."""
    from miniautogen.cli.services.run_pipeline import execute_pipeline

    root = find_project_root(Path.cwd())
    if root is None:
        raise ProjectNotFoundError(
            f"No {CONFIG_FILENAME} found in directory tree"
        )

    config = load_config(root / CONFIG_FILENAME)

    if pipeline_name not in config.pipelines:
        raise PipelineNotFoundError(
            f"Pipeline '{pipeline_name}' not found in config"
        )

    result = run_async(
        execute_pipeline,
        config,
        pipeline_name,
        root,
        timeout=timeout,
        verbose=verbose,
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
