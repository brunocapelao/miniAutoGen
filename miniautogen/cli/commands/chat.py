"""miniautogen chat command -- interactive multi-turn chat with an agent."""

from __future__ import annotations

import click

from miniautogen.cli.config import require_project_config
from miniautogen.cli.main import run_async
from miniautogen.cli.output import echo_error


_HELP_TEXT = """Available commands:
  /help              Show this help message
  /quit              Exit the chat session
  /clear             Clear conversation history
  /switch <agent>    Switch to a different agent
  /history           Show conversation history
"""


@click.command("chat")
@click.argument("agent_name", required=False, default=None)
def chat_command(agent_name: str | None) -> None:
    """Start an interactive chat session with an agent."""
    from miniautogen.cli.services.chat_service import ChatSession, list_available_agents

    root, _config = require_project_config()

    # Create initial session
    try:
        session = run_async(ChatSession.create, root, agent_name=agent_name)
    except (ValueError, RuntimeError) as exc:
        echo_error(str(exc))
        raise SystemExit(1)

    click.echo(
        click.style(f"Chat session started with ", fg="blue")
        + click.style(session.agent_name, fg="cyan", bold=True)
        + click.style(f" (run: {session.run_id})", fg="blue")
    )
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

            # Handle commands
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

            if stripped.startswith("/switch"):
                parts = stripped.split(maxsplit=1)
                if len(parts) < 2:
                    # Show available agents
                    try:
                        agents = list_available_agents(root)
                        click.echo(
                            click.style("Available agents: ", fg="blue")
                            + ", ".join(agents)
                        )
                    except ValueError as exc:
                        echo_error(str(exc))
                    continue

                new_agent = parts[1].strip()
                try:
                    run_async(session.close)
                    session = run_async(
                        ChatSession.create, root, agent_name=new_agent
                    )
                    click.echo(
                        click.style("Switched to ", fg="blue")
                        + click.style(session.agent_name, fg="cyan", bold=True)
                    )
                except (ValueError, RuntimeError) as exc:
                    echo_error(str(exc))
                continue

            if stripped.startswith("/"):
                echo_error(f"Unknown command: {stripped}. Type /help for help.")
                continue

            # Send message to agent
            try:
                response = run_async(session.send, user_input)
                click.echo(
                    click.style(f"{session.agent_name}> ", fg="cyan") + response
                )
            except RuntimeError as exc:
                echo_error(str(exc))
                break

    except KeyboardInterrupt:
        click.echo()  # newline after ^C

    # Cleanup
    try:
        if not session.is_closed:
            run_async(session.close)
    except Exception:
        pass

    click.echo(click.style("\nChat session ended.", fg="blue"))
