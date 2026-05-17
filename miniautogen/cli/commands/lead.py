"""miniautogen lead command — interactive lead agent session.

The lead agent has access to workspace management tools (create/update/
delete agents, flows, engines), can run flows, and receives execution
events for full ecosystem awareness.
"""

from __future__ import annotations

import click

from miniautogen.cli.config import require_project_config
from miniautogen.cli.main import run_async
from miniautogen.cli.output import echo_error, echo_info, echo_success


_HELP_TEXT = """Available commands:
  /help              Show this help message
  /quit              Exit the session
  /clear             Clear conversation history
  /history           Show conversation history
  /events            Show recent execution events
"""


@click.command("lead")
@click.argument("agent_name", required=False, default=None)
def lead_command(agent_name: str | None) -> None:
    """Start an interactive lead agent session.

    The lead agent has workspace tools to manage agents, flows,
    and engines, run pipelines, and full event awareness.
    """
    from miniautogen.cli.services.lead_agent_session import LeadAgentSession

    root, _config = require_project_config()

    try:
        session = run_async(LeadAgentSession.create, root, agent_name=agent_name)
    except (ValueError, RuntimeError) as exc:
        echo_error(str(exc))
        raise SystemExit(1)

    click.echo(
        click.style(f"Lead agent session started with ", fg="blue")
        + click.style(session.agent_name, fg="cyan", bold=True)
        + click.style(f" (run: {session.run_id})", fg="blue")
    )
    click.echo(click.style("Workspace tools and event awareness active.\n", fg="blue"))
    click.echo(click.style("Type /help for available commands.\n", fg="blue"))

    try:
        while True:
            try:
                user_input = input(click.style("You> ", fg="green"))
            except EOFError:
                break

            if not user_input.strip():
                continue

            stripped = user_input.strip()

            if stripped == "/quit":
                break

            if stripped == "/help":
                click.echo(_HELP_TEXT)
                continue

            if stripped == "/clear":
                session.clear_history()
                click.echo(click.style("History cleared.", fg="yellow"))
                continue

            if stripped == "/history":
                history = session.history
                if not history:
                    click.echo(click.style("No messages yet.", fg="yellow"))
                else:
                    for entry in history:
                        role = entry["role"]
                        content = entry["content"]
                        if role == "user":
                            click.echo(click.style(f"You> {content}", fg="green"))
                        else:
                            click.echo(
                                click.style(f"{session.agent_name}> ", fg="cyan")
                                + content
                            )
                continue

            if stripped == "/events":
                events = session.recent_events
                if not events:
                    click.echo(click.style("No events yet.", fg="yellow"))
                else:
                    for ev in events[-20:]:
                        ts = ev.timestamp.strftime("%H:%M:%S")
                        click.echo(f"[{ts}] {ev.type}")
                continue

            if stripped.startswith("/"):
                echo_error(f"Unknown command: {stripped}. Type /help for help.")
                continue

            try:
                response = run_async(session.send, user_input)
                click.echo(
                    click.style(f"{session.agent_name}> ", fg="cyan") + response
                )
            except RuntimeError as exc:
                echo_error(str(exc))
                break

    except KeyboardInterrupt:
        click.echo()

    try:
        if not session.is_closed:
            run_async(session.close)
    except Exception:
        pass

    echo_success("\nLead agent session ended.")
