"""miniautogen pipeline command group.

CRUD operations for pipeline configurations in miniautogen.yaml.
"""

from __future__ import annotations

import click

from miniautogen.cli.config import require_project_config
from miniautogen.cli.main import run_async
from miniautogen.cli.output import (
    echo_error,
    echo_json,
    echo_success,
    echo_table,
)

_VALID_MODES = ("workflow", "deliberation", "loop", "composite")


@click.group("pipeline")
def pipeline_group() -> None:
    """Manage pipeline configurations."""


@pipeline_group.command("create")
@click.argument("name")
@click.option(
    "--mode",
    type=click.Choice(_VALID_MODES),
    default=None,
    help="Coordination mode.",
)
@click.option(
    "--participants",
    default=None,
    help="Comma-separated list of agent names.",
)
@click.option("--leader", default=None, help="Leader agent (for deliberation mode).")
@click.option("--target", default=None, help="Pipeline target (module:callable).")
@click.option("--max-rounds", type=int, default=None, help="Max coordination rounds.")
def pipeline_create(
    name: str,
    mode: str | None,
    participants: str | None,
    leader: str | None,
    target: str | None,
    max_rounds: int | None,
) -> None:
    """Create a new pipeline configuration."""
    from miniautogen.cli.services.pipeline_ops import create_pipeline

    root, _config = require_project_config()

    # Interactive mode for missing required fields
    if mode is None:
        mode = click.prompt(
            "Coordination mode",
            type=click.Choice(_VALID_MODES),
            default="workflow",
        )

    participant_list = None
    if participants:
        participant_list = [p.strip() for p in participants.split(",")]
    elif mode != "composite":
        raw = click.prompt("Participants (comma-separated agent names)", default="", type=str)
        if raw.strip():
            participant_list = [p.strip() for p in raw.split(",")]

    if mode == "deliberation" and leader is None:
        leader = click.prompt("Leader agent", type=str)

    try:
        pipeline = run_async(
            create_pipeline,
            root,
            name,
            mode=mode,
            participants=participant_list,
            leader=leader,
            target=target,
            max_rounds=max_rounds,
        )
        echo_success(f"Pipeline '{name}' created: mode={pipeline['mode']}")
    except ValueError as exc:
        echo_error(str(exc))
        raise SystemExit(1)


@pipeline_group.command("list")
@click.option(
    "--format", "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def pipeline_list(output_format: str) -> None:
    """List all pipeline configurations."""
    from miniautogen.cli.services.pipeline_ops import list_pipelines

    root, _config = require_project_config()
    pipelines = run_async(list_pipelines, root)

    if output_format == "json":
        echo_json(pipelines)
    elif not pipelines:
        click.echo("No pipelines configured.")
    else:
        rows = [
            [
                p["name"],
                p["mode"],
                ", ".join(p.get("participants", [])) or "-",
            ]
            for p in pipelines
        ]
        echo_table(["Name", "Mode", "Participants"], rows)


@pipeline_group.command("show")
@click.argument("name")
@click.option(
    "--format", "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def pipeline_show(name: str, output_format: str) -> None:
    """Show details for a specific pipeline."""
    from miniautogen.cli.services.pipeline_ops import show_pipeline

    root, _config = require_project_config()

    try:
        pipeline = run_async(show_pipeline, root, name)
    except KeyError as exc:
        echo_error(str(exc))
        raise SystemExit(1)

    if output_format == "json":
        echo_json(pipeline)
    else:
        for key, value in pipeline.items():
            click.echo(f"{key}: {value}")


@pipeline_group.command("update")
@click.argument("name")
@click.option("--mode", type=click.Choice(_VALID_MODES), default=None, help="New mode.")
@click.option("--participants", default=None, help="New comma-separated participants.")
@click.option("--leader", default=None, help="New leader agent.")
@click.option("--max-rounds", type=int, default=None, help="New max rounds.")
@click.option("--dry-run", is_flag=True, default=False, help="Show changes without applying.")
def pipeline_update(
    name: str,
    mode: str | None,
    participants: str | None,
    leader: str | None,
    max_rounds: int | None,
    dry_run: bool,
) -> None:
    """Update an existing pipeline configuration."""
    from miniautogen.cli.services.pipeline_ops import update_pipeline

    root, _config = require_project_config()

    updates: dict[str, object] = {}
    if mode is not None:
        updates["mode"] = mode
    if participants is not None:
        updates["participants"] = [p.strip() for p in participants.split(",")]
    if leader is not None:
        updates["leader"] = leader
    if max_rounds is not None:
        updates["max_rounds"] = max_rounds

    if not updates:
        echo_error("No updates specified.")
        raise SystemExit(1)

    try:
        result = run_async(
            update_pipeline, root, name, dry_run=dry_run, **updates,
        )
    except KeyError as exc:
        echo_error(str(exc))
        raise SystemExit(1)

    if dry_run:
        click.echo("Dry run — changes not applied:")
        for key in updates:
            before_val = result["before"].get(key, "(unset)")
            after_val = result["after"].get(key)
            click.echo(f"  {key}: {before_val} -> {after_val}")
    else:
        echo_success(f"Pipeline '{name}' updated.")
