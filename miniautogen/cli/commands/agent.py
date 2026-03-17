"""miniautogen agent command group.

CRUD operations for agent definitions (agents/*.yaml).
Supports dual mode: interactive wizard when flags missing,
silent mode when all flags provided.
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


@click.group("agent")
def agent_group() -> None:
    """Manage agents."""


@agent_group.command("create")
@click.argument("name")
@click.option("--role", default=None, help="Agent role.")
@click.option("--goal", default=None, help="Agent goal/objective.")
@click.option("--engine", "engine_profile", default=None, help="Engine profile to bind.")
@click.option("--temperature", type=float, default=None, help="Sampling temperature.")
@click.option("--max-tokens", type=int, default=None, help="Max generation tokens.")
def agent_create(
    name: str,
    role: str | None,
    goal: str | None,
    engine_profile: str | None,
    temperature: float | None,
    max_tokens: int | None,
) -> None:
    """Create a new agent."""
    from miniautogen.cli.services.agent_ops import create_agent
    from miniautogen.cli.services.engine_ops import list_engines

    root, _config = require_project_config()

    # Interactive wizard for missing required fields
    if engine_profile is None:
        engines = list_engines(root)
        if not engines:
            echo_error(
                "No engine profiles configured. "
                "Create one first: miniautogen engine create <name>"
            )
            raise SystemExit(1)
        names = [e["name"] for e in engines]
        click.echo(f"Available engines: {', '.join(names)}")
        engine_profile = click.prompt("Engine profile", type=str)

    if role is None:
        role = click.prompt("Role", type=str)
    if goal is None:
        goal = click.prompt("Goal", type=str)

    # Optional configuration prompts in interactive mode
    if temperature is None:
        raw_temp = click.prompt(
            "Temperature (leave empty for default)",
            default="",
            type=str,
        )
        if raw_temp.strip():
            try:
                temperature = float(raw_temp)
            except ValueError:
                echo_error(f"Invalid temperature: {raw_temp}")
                raise SystemExit(1)

    if max_tokens is None:
        raw_tokens = click.prompt(
            "Max tokens (leave empty for default)",
            default="",
            type=str,
        )
        if raw_tokens.strip():
            try:
                max_tokens = int(raw_tokens)
            except ValueError:
                echo_error(f"Invalid max tokens: {raw_tokens}")
                raise SystemExit(1)

    # Confirmation summary
    echo_info(f"\nAgent '{name}' will be created:")
    echo_info(f"  role: {role}")
    echo_info(f"  goal: {goal}")
    echo_info(f"  engine: {engine_profile}")
    if temperature is not None:
        echo_info(f"  temperature: {temperature}")
    if max_tokens is not None:
        echo_info(f"  max_tokens: {max_tokens}")

    if not click.confirm("\nConfirm?", default=True):
        echo_warning("Cancelled.")
        return

    try:
        agent = create_agent(
            root,
            name,
            role=role,
            goal=goal,
            engine_profile=engine_profile,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        echo_success(f"Agent '{name}' created: role={agent['role']}")
    except ValueError as exc:
        echo_error(str(exc))
        raise SystemExit(1)


@agent_group.command("list")
@click.option(
    "--format", "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def agent_list(output_format: str) -> None:
    """List all agents."""
    from miniautogen.cli.services.agent_ops import list_agents

    root, _config = require_project_config()
    agents = list_agents(root)

    if output_format == "json":
        echo_json(agents)
    elif not agents:
        click.echo("No agents defined.")
    else:
        rows = [
            [a["name"], a["role"], a["engine_profile"]]
            for a in agents
        ]
        echo_table(["Name", "Role", "Engine"], rows)


@agent_group.command("show")
@click.argument("name")
@click.option(
    "--format", "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def agent_show(name: str, output_format: str) -> None:
    """Show details for a specific agent."""
    from miniautogen.cli.services.agent_ops import show_agent

    root, _config = require_project_config()

    try:
        agent = show_agent(root, name)
    except KeyError as exc:
        echo_error(str(exc))
        raise SystemExit(1)

    if output_format == "json":
        echo_json(agent)
    else:
        for key, value in agent.items():
            click.echo(f"{key}: {value}")


@agent_group.command("update")
@click.argument("name")
@click.option("--role", default=None, help="New role.")
@click.option("--goal", default=None, help="New goal.")
@click.option("--engine", "engine_profile", default=None, help="New engine profile.")
@click.option("--temperature", type=float, default=None, help="New temperature.")
@click.option("--dry-run", is_flag=True, default=False, help="Show changes without applying.")
def agent_update(
    name: str,
    role: str | None,
    goal: str | None,
    engine_profile: str | None,
    temperature: float | None,
    dry_run: bool,
) -> None:
    """Update an existing agent."""
    from miniautogen.cli.services.agent_ops import update_agent

    root, _config = require_project_config()

    updates: dict[str, object] = {}
    if role is not None:
        updates["role"] = role
    if goal is not None:
        updates["goal"] = goal
    if engine_profile is not None:
        updates["engine_profile"] = engine_profile
    if temperature is not None:
        updates["temperature"] = temperature

    if not updates:
        echo_error("No updates specified.")
        raise SystemExit(1)

    try:
        result = update_agent(root, name, dry_run=dry_run, **updates)
    except (KeyError, ValueError) as exc:
        echo_error(str(exc))
        raise SystemExit(1)

    if dry_run:
        click.echo("Dry run — changes not applied:")
        for key in updates:
            before_val = result["before"].get(key, "(unset)")
            after_val = result["after"].get(key)
            click.echo(f"  {key}: {before_val} -> {after_val}")
    else:
        echo_success(f"Agent '{name}' updated.")


@agent_group.command("delete")
@click.argument("name")
@click.option("--yes", "skip_confirm", is_flag=True, default=False, help="Skip confirmation.")
def agent_delete(name: str, skip_confirm: bool) -> None:
    """Delete an agent."""
    from miniautogen.cli.services.agent_ops import delete_agent

    root, _config = require_project_config()

    if not skip_confirm:
        if not click.confirm(f"Delete agent '{name}'?"):
            click.echo("Cancelled.")
            return

    try:
        result = delete_agent(root, name)
        echo_success(f"Agent '{result['deleted']}' deleted.")
    except (KeyError, ValueError) as exc:
        echo_error(str(exc))
        raise SystemExit(1)
