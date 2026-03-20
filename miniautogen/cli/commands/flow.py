"""miniautogen flow command group.

DA-9: Renamed from 'pipeline'. CRUD operations for flow configurations
in miniautogen.yaml. Supports all coordination modes: workflow,
deliberation, loop, composite.
"""

from __future__ import annotations

import click

from miniautogen.cli.config import require_project_config
from miniautogen.cli.output import (
    echo_error,
    echo_info,
    echo_json,
    echo_success,
    echo_table,
    echo_warning,
)

_VALID_MODES = ("workflow", "deliberation", "loop", "composite")


@click.group("flow")
def flow_group() -> None:
    """Manage flow configurations."""


@flow_group.command("create")
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
@click.option("--target", default=None, help="Flow target (module:callable).")
@click.option("--max-rounds", type=int, default=None, help="Max coordination rounds.")
@click.option(
    "--chain-flows",
    default=None,
    help="Comma-separated flow names to chain (composite mode).",
)
def flow_create(
    name: str,
    mode: str | None,
    participants: str | None,
    leader: str | None,
    target: str | None,
    max_rounds: int | None,
    chain_flows: str | None,
) -> None:
    """Create a new flow configuration."""
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
        if chain_flows:
            chain_list = [p.strip() for p in chain_flows.split(",")]
        else:
            existing = list_pipelines(root)
            if existing:
                echo_info("Existing flows:")
                for p in existing:
                    click.echo(f"  - {p['name']} ({p['mode']})")
            raw = click.prompt(
                "Flows to chain (comma-separated names)",
                default="",
                type=str,
            )
            if raw.strip():
                chain_list = [p.strip() for p in raw.split(",")]
    elif mode in ("workflow", "loop"):
        if participants:
            participant_list = [p.strip() for p in participants.split(",")]
        else:
            agents = list_agents(root)
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
            agents = list_agents(root)
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

    # Confirmation summary
    echo_info(f"\nFlow '{name}' will be created:")
    echo_info(f"  mode: {mode}")
    if participant_list:
        echo_info(f"  participants: {', '.join(participant_list)}")
    if leader:
        echo_info(f"  leader: {leader}")
    if max_rounds is not None:
        echo_info(f"  max_rounds: {max_rounds}")
    if chain_list:
        echo_info(f"  chain: {', '.join(chain_list)}")
    if target:
        echo_info(f"  target: {target}")

    if not click.confirm("\nConfirm?", default=True):
        echo_warning("Cancelled.")
        return

    try:
        flow = create_pipeline(
            root,
            name,
            mode=mode,
            participants=participant_list,
            leader=leader,
            target=target,
            max_rounds=max_rounds,
            chain_pipelines=chain_list,
        )
        echo_success(f"Flow '{name}' created: mode={flow['mode']}")
    except ValueError as exc:
        echo_error(str(exc))
        raise SystemExit(1)


@flow_group.command("list")
@click.option(
    "--format", "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def flow_list(output_format: str) -> None:
    """List all flow configurations."""
    from miniautogen.cli.services.pipeline_ops import list_pipelines

    root, _config = require_project_config()
    flows = list_pipelines(root)

    if output_format == "json":
        echo_json(flows)
    elif not flows:
        click.echo("No flows configured.")
    else:
        rows = [
            [
                p["name"],
                p["mode"],
                ", ".join(p.get("participants", [])) or "-",
            ]
            for p in flows
        ]
        echo_table(["Name", "Mode", "Participants"], rows)


@flow_group.command("show")
@click.argument("name")
@click.option(
    "--format", "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def flow_show(name: str, output_format: str) -> None:
    """Show details for a specific flow."""
    from miniautogen.cli.services.pipeline_ops import show_pipeline

    root, _config = require_project_config()

    try:
        flow = show_pipeline(root, name)
    except KeyError as exc:
        echo_error(str(exc))
        raise SystemExit(1)

    if output_format == "json":
        echo_json(flow)
    else:
        for key, value in flow.items():
            click.echo(f"{key}: {value}")


@flow_group.command("update")
@click.argument("name")
@click.option("--mode", type=click.Choice(_VALID_MODES), default=None, help="New mode.")
@click.option("--participants", default=None, help="Replace participants (comma-separated).")
@click.option("--add-participant", default=None, help="Add agent to participants.")
@click.option("--remove-participant", default=None, help="Remove agent from participants.")
@click.option("--leader", default=None, help="New leader agent.")
@click.option("--max-rounds", type=int, default=None, help="New max rounds.")
@click.option("--dry-run", is_flag=True, default=False, help="Show changes without applying.")
def flow_update(
    name: str,
    mode: str | None,
    participants: str | None,
    add_participant: str | None,
    remove_participant: str | None,
    leader: str | None,
    max_rounds: int | None,
    dry_run: bool,
) -> None:
    """Update an existing flow configuration."""
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
        result = update_pipeline(root, name, dry_run=dry_run, **updates)
    except (KeyError, ValueError) as exc:
        echo_error(str(exc))
        raise SystemExit(1)

    if dry_run:
        click.echo("Dry run -- changes not applied:")
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
        echo_success(f"Flow '{name}' updated.")


@flow_group.command("delete")
@click.argument("name")
@click.option("--yes", "skip_confirm", is_flag=True, default=False, help="Skip confirmation.")
def flow_delete(name: str, skip_confirm: bool) -> None:
    """Delete a flow configuration."""
    from miniautogen.cli.services.pipeline_ops import delete_pipeline

    root, _config = require_project_config()

    if not skip_confirm:
        if not click.confirm(f"Delete flow '{name}'?"):
            echo_warning("Cancelled.")
            return

    try:
        result = delete_pipeline(root, name)
        echo_success(f"Flow '{result['deleted']}' deleted.")
    except (KeyError, ValueError) as exc:
        echo_error(str(exc))
        raise SystemExit(1)
