"""miniautogen team command -- interactive team orchestration.

Starts a Lead Agent in an interactive chat session with background
teammates draining a shared task list (Kanban board).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import anyio
import click

from miniautogen.cli.config import require_project_config
from miniautogen.cli.main import run_async
from miniautogen.cli.output import echo_error, echo_info, echo_success, echo_warning
from miniautogen.cli.services.chat_service import ChatSession, list_available_agents


@click.command("team")
@click.argument("lead_agent", required=False)
@click.option(
    "--teammates",
    "-t",
    help="Comma-separated list of teammate agents. Defaults to all other agents.",
)
def team_command(lead_agent: str | None, teammates: str | None) -> None:
    """Start an interactive team orchestration session.

    The LEAD_AGENT will be your main point of contact. They have access
    to tools to manage a shared task list that background teammates
    will execute.
    """
    root, config = require_project_config()

    # 1. Resolve Lead Agent
    available = list_available_agents(root)
    if not available:
        echo_error("No agents found in workspace.")
        raise SystemExit(1)

    if lead_agent is None:
        # Try to find 'tech_lead', 'lead', or just use the first one
        for candidate in ["tech_lead", "lead", "assistant", "manager"]:
            if candidate in available:
                lead_agent = candidate
                break
        if lead_agent is None:
            lead_agent = available[0]

    if lead_agent not in available:
        echo_error(f"Lead agent '{lead_agent}' not found.")
        raise SystemExit(1)

    # 2. Resolve Teammates
    teammate_list: list[str] = []
    if teammates:
        teammate_list = [t.strip() for t in teammates.split(",")]
        for t in teammate_list:
            if t not in available:
                echo_error(f"Teammate '{t}' not found.")
                raise SystemExit(1)
    else:
        # Default to all other agents
        teammate_list = [t for t in available if t != lead_agent]

    if not teammate_list:
        echo_warning("No teammates specified. Lead will work alone.")

    echo_info(f"Starting team session with Lead: {lead_agent}")
    if teammate_list:
        echo_info(f"Teammates: {', '.join(teammate_list)}")

    # 3. Launch Team Session
    try:
        run_async(_run_team_session, root, lead_agent, teammate_list)
    except KeyboardInterrupt:
        click.echo()
    except Exception as exc:
        echo_error(f"Team session failed: {exc}")
        raise SystemExit(1)

    echo_success("\nTeam session ended.")


async def _run_team_session(
    root: Path,
    lead_name: str,
    teammates: list[str],
) -> None:
    from miniautogen.api import InMemoryTaskListStore, PipelineRunner, NullEventSink, TeamRuntime
    from miniautogen.cli.services.agent_ops import load_agent_specs

    # Initialize Task List Store
    run_id = f"team-{lead_name}-{Path.cwd().name}"
    store = InMemoryTaskListStore(team_run_id=run_id, event_sink=NullEventSink())

    # Load agent specs for registry
    agent_specs = load_agent_specs(root)

    # Initialize Lead Session
    # Note: We need to inject tools into the lead's runtime
    session = await ChatSession.create(root, agent_name=lead_name)

    # Create a dummy runner for tool injection
    runner = PipelineRunner()
    runtime = TeamRuntime(runner, agent_registry={}) # Registry will be filled by factory if needed

    # Inject task tools into lead
    runtime._inject_task_tools(session._runtime, store, lead_name)

    echo_info(f"Lead '{lead_name}' initialized with task management tools.")

    # Start teammates in background task group
    async with anyio.create_task_group() as tg:
        for t_name in teammates:
            # Create a runtime for the teammate
            from miniautogen.cli.services.runtime_factory import create_runtime
            t_runtime, _ = await create_runtime(root, t_name, run_id_prefix=f"t-{t_name}")

            # Inject task tools into teammate
            runtime._inject_task_tools(t_runtime, store, t_name)

            echo_info(f"Spawning background teammate: {t_name}")
            tg.start_soon(
                runtime._run_teammate_drain_loop,
                t_name,
                t_runtime,
                t_runtime._run_context,
                "isolate", # failure policy
                {}, # contributions dict (unused in drain loop but required by signature)
                run_id,
                tg.cancel_scope,
                None, # limiter
                store,
            )

        # Enter interactive chat loop for Lead
        click.echo(click.style(f"\nTeam Lead> ", fg="cyan", bold=True) + "Ready for orders.")

        while True:
            try:
                user_input = await anyio.to_thread.run_sync(
                    lambda: input(click.style("You> ", fg="green"))
                )
            except EOFError:
                break

            if not user_input.strip():
                continue

            stripped = user_input.strip()

            if stripped == "/quit":
                break

            # Handle other chat commands if needed, or just send to lead
            if stripped.startswith("/"):
                # For now, just bypass or handle simple ones
                if stripped == "/help":
                    click.echo("Commands: /quit, /tasks, /help")
                elif stripped == "/tasks":
                    tasks = await store.list_tasks()
                    if not tasks:
                        click.echo("No tasks in board.")
                    else:
                        for t in tasks:
                            click.echo(f"[{t.status.value}] {t.id}: {t.title} ({t.assigned_to or 'unassigned'})")
                continue

            # Send to Lead
            try:
                # Use a progress spinner or similar?
                response = await session.send(user_input)
                click.echo(
                    click.style(f"{lead_name}> ", fg="cyan") + response
                )
            except Exception as exc:
                echo_error(f"Lead error: {exc}")
                break

        # Shutdown teammates
        tg.cancel_scope.cancel()

    await session.close()
