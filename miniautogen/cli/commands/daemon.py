"""miniautogen daemon -- first-class daemon lifecycle management."""

from __future__ import annotations

import click

from miniautogen.cli.config import require_project_config
from miniautogen.cli.output import echo_error, echo_info, echo_json


@click.group("daemon")
def daemon_group() -> None:
    """Manage the MiniAutoGen background daemon.

    The daemon runs the API server and event processing in the background.
    """


@daemon_group.command("start")
@click.option("--host", default="127.0.0.1", help="Bind address.")
@click.option("--port", default=8080, type=int, help="Port number.")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def daemon_start(host: str, port: int, fmt: str) -> None:
    """Start the daemon in the background."""
    from miniautogen.cli.services.server_ops import start_server

    root, _ = require_project_config()
    try:
        result = start_server(root, host=host, port=port, daemon=True)
        if fmt == "json":
            echo_json(result)
        else:
            status = result.get("status", "unknown")
            if status == "started":
                pid = result.get("pid", "?")
                echo_info(f"Daemon started on {host}:{port} (PID {pid})")
            elif status == "already_running":
                echo_info(result.get("message", "Daemon already running."))
            else:
                echo_info(f"Daemon: {status}")
    except Exception as exc:
        echo_error(f"Failed to start daemon: {exc}")
        raise SystemExit(1)


@daemon_group.command("stop")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def daemon_stop(fmt: str) -> None:
    """Stop the running daemon."""
    from miniautogen.cli.services.server_ops import stop_server

    root, _ = require_project_config()
    try:
        result = stop_server(root)
        if fmt == "json":
            echo_json(result)
        else:
            echo_info(result.get("message", "Daemon stopped."))
    except Exception as exc:
        echo_error(f"Failed to stop daemon: {exc}")
        raise SystemExit(1)


@daemon_group.command("restart")
@click.option("--host", default="127.0.0.1", help="Bind address.")
@click.option("--port", default=8080, type=int, help="Port number.")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def daemon_restart(host: str, port: int, fmt: str) -> None:
    """Restart the daemon (stop + start)."""
    from miniautogen.cli.services.server_ops import start_server, stop_server

    root, _ = require_project_config()
    try:
        stop_server(root)
        result = start_server(root, host=host, port=port, daemon=True)
        if fmt == "json":
            echo_json(result)
        else:
            echo_info(f"Daemon restarted on {host}:{port}")
    except Exception as exc:
        echo_error(f"Failed to restart daemon: {exc}")
        raise SystemExit(1)


@daemon_group.command("status")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def daemon_status(fmt: str) -> None:
    """Show daemon status."""
    from miniautogen.cli.services.server_ops import server_status

    root, _ = require_project_config()
    result = server_status(root)
    if fmt == "json":
        echo_json(result)
    else:
        status = result.get("status", "unknown")
        pid = result.get("pid", "\u2014")
        port = result.get("port", "\u2014")
        if status == "running":
            click.echo(
                click.style(
                    f"\u25cf Daemon running (PID: {pid}, port: {port})", fg="green"
                )
            )
        elif status in ("degraded", "unreachable"):
            click.echo(
                click.style(
                    f"\u25cb Daemon {status} (PID: {pid}, port: {port})", fg="yellow"
                )
            )
        else:
            click.echo(click.style("\u25cb Daemon stopped", fg="yellow"))


@daemon_group.command("logs")
@click.option("--lines", "-n", default=50, type=int, help="Number of lines to show.")
def daemon_logs(lines: int) -> None:
    """View daemon logs."""
    from miniautogen.cli.services.server_ops import server_logs

    root, _ = require_project_config()
    try:
        output = server_logs(root, lines=lines)
        click.echo(output)
    except Exception as exc:
        echo_error(f"Failed to read logs: {exc}")
        raise SystemExit(1)
