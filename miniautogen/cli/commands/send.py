"""miniautogen send command -- send a single message to an agent."""

from __future__ import annotations

import sys

import click

from miniautogen.cli.config import require_project_config
from miniautogen.cli.main import run_async
from miniautogen.cli.output import echo_error, echo_json


@click.command("send")
@click.argument("message", required=False, default=None)
@click.option(
    "--agent",
    default=None,
    help="Agent name (defaults to first agent in workspace).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def send_command(
    message: str | None,
    agent: str | None,
    output_format: str,
) -> None:
    """Send a single message to an agent."""
    from miniautogen.cli.services.send_service import send_message

    # Resolve message from argument or stdin
    if message is None and not sys.stdin.isatty():
        message = sys.stdin.read().strip()

    if not message:
        echo_error("No message provided. Pass MESSAGE argument or pipe via stdin.")
        raise SystemExit(1)

    root, _config = require_project_config()

    try:
        result = run_async(
            send_message,
            root,
            message,
            agent_name=agent,
            output_format=output_format,
        )
    except (ValueError, RuntimeError) as exc:
        echo_error(str(exc))
        raise SystemExit(1)

    if output_format == "json":
        echo_json(result)
    else:
        click.echo(result.get("response", ""))
