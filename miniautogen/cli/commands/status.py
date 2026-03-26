"""miniautogen status command -- workspace overview at a glance."""

from __future__ import annotations

import click

from miniautogen.cli.config import require_project_config
from miniautogen.cli.output import echo_json


@click.command("status")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def status_command(fmt: str) -> None:
    """Show workspace status overview."""
    from miniautogen.cli.services.status_service import get_workspace_status

    root, _config = require_project_config()
    status = get_workspace_status(root)

    if fmt == "json":
        echo_json(status)
        return

    # Text output
    project = status["project"]
    click.echo(
        f"Workspace: {click.style(project['name'], bold=True)} "
        f"(v{project['version']})"
    )

    # Server line
    server = status["server"]
    srv_status = server.get("status", "stopped")
    if srv_status == "running":
        port = server.get("port", "?")
        click.echo(f"Server:    {click.style('●', fg='green')} running on :{port}")
    elif srv_status in ("degraded", "unreachable"):
        click.echo(
            f"Server:    {click.style('◐', fg='yellow')} {srv_status}"
        )
    else:
        click.echo(f"Server:    {click.style('○', fg='red')} stopped")

    # Agents
    agents = status["agents"]
    names_str = ", ".join(agents["names"]) if agents["names"] else "(none)"
    click.echo(f"Agents:    {agents['count']} configured ({names_str})")

    # Engines
    engines = status["engines"]
    names_str = ", ".join(engines["names"]) if engines["names"] else "(none)"
    click.echo(f"Engines:   {engines['count']} configured ({names_str})")

    # Flows
    flows = status["flows"]
    names_str = ", ".join(flows["names"]) if flows["names"] else "(none)"
    click.echo(f"Flows:     {flows['count']} configured ({names_str})")
