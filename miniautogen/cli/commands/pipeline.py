"""miniautogen pipeline command group.

CRUD operations for pipeline configurations in miniautogen.yaml.
Supports all coordination modes: workflow, deliberation, loop, composite.
"""

from __future__ import annotations

import click

from miniautogen.cli.config import require_project_config
from miniautogen.cli.main import run_async
from miniautogen.cli.output import (
    echo_error,
    echo_info,
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
@click.option(
    "--chain-pipelines",
    default=None,
    help="Comma-separated pipeline names to chain (composite mode).",
)
def pipeline_create(
    name: str,
    mode: str | None,
    participants: str | None,
    leader: str | None,
    target: str | None,
    max_rounds: int | None,
    chain_pipelines: str | None,
) -> None:
    """Create a new pipeline configuration."""
    from miniautogen.cli.services.agent_ops import list_agents
    from miniautogen.cli.services.pipeline_ops import create_pipeline, list_pipelines

    root, _config = require_project_config()

    # Interactive mode for missing required fields
    if mode is None:
        mode = click.prompt(
            "Coordination mode",
            type=click.Choice(_VALID_MODES),
            default="workflow",
        )

    participant_list = None
    chain_list = None

    if mode == "composite":
        # Composite wizard: list existing pipelines to chain
        if chain_pipelines:
            chain_list = [p.strip() for p in chain_pipelines.split(",")]
        else:
            existing = run_async(list_pipelines, root)
            if existing:
                echo_info("Existing pipelines:")
                for p in existing:
                    click.echo(f"  - {p['name']} ({p['mode']})")
            raw = click.prompt(
                "Pipelines to chain (comma-separated names)",
                default="",
                type=str,
            )
            if raw.strip():
                chain_list = [p.strip() for p in raw.split(",")]
    elif mode in ("workflow", "loop"):
        # Workflow/loop wizard: list agents and ask order
        if participants:
            participant_list = [p.strip() for p in participants.split(",")]
        else:
            agents = run_async(list_agents, root)
            if agents:
                echo_info("Available agents:")
                for a in agents:
                    click.echo(f"  - {a['name']} ({a['role']})")
            if mode == "workflow":
                raw = click.prompt(
                    "Agents to chain in order (comma-separated)",
                    default="",
                    type=str,
                )
            else:
                raw = click.prompt(
                    "Participant agents (comma-separated)",
                    default="",
                    type=str,
                )
            if raw.strip():
                participant_list = [p.strip() for p in raw.split(",")]

        if mode == "loop" and leader is None:
            leader = click.prompt("Router agent", type=str)

    elif mode == "deliberation":
        if participants:
            participant_list = [p.strip() for p in participants.split(",")]
        else:
            agents = run_async(list_agents, root)
            if agents:
                echo_info("Available agents:")
                for a in agents:
                    click.echo(f"  - {a['name']} ({a['role']})")
            raw = click.prompt(
                "Peer agents (comma-separated)",
                default="",
                type=str,
            )
            if raw.strip():
                participant_list = [p.strip() for p in raw.split(",")]

        if leader is None:
            leader = click.prompt("Leader agent", type=str)

        if max_rounds is None:
            raw_rounds = click.prompt(
                "Max deliberation rounds",
                default="3",
                type=str,
            )
            try:
                max_rounds = int(raw_rounds)
            except ValueError:
                pass

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
            chain_pipelines=chain_list,
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
@click.option("--participants", default=None, help="Replace participants (comma-separated).")
@click.option("--add-participant", default=None, help="Add agent to participants.")
@click.option("--remove-participant", default=None, help="Remove agent from participants.")
@click.option("--leader", default=None, help="New leader agent.")
@click.option("--max-rounds", type=int, default=None, help="New max rounds.")
@click.option("--dry-run", is_flag=True, default=False, help="Show changes without applying.")
def pipeline_update(
    name: str,
    mode: str | None,
    participants: str | None,
    add_participant: str | None,
    remove_participant: str | None,
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
    if add_participant is not None:
        updates["add_participant"] = add_participant
    if remove_participant is not None:
        updates["remove_participant"] = remove_participant
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
    except (KeyError, ValueError) as exc:
        echo_error(str(exc))
        raise SystemExit(1)

    if dry_run:
        click.echo("Dry run — changes not applied:")
        before_p = result["before"].get("participants", [])
        after_p = result["after"].get("participants", [])
        if before_p != after_p:
            click.echo(f"  participants: {before_p} -> {after_p}")
        for key in updates:
            if key in ("add_participant", "remove_participant", "participants"):
                continue
            before_val = result["before"].get(key, "(unset)")
            after_val = result["after"].get(key)
            click.echo(f"  {key}: {before_val} -> {after_val}")
    else:
        echo_success(f"Pipeline '{name}' updated.")
