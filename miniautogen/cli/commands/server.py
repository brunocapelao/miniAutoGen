"""miniautogen server command group.

Gateway lifecycle management (start, stop, status, logs).
"""

from __future__ import annotations

import click

from miniautogen.cli.config import require_project_config
from miniautogen.cli.main import run_async
from miniautogen.cli.output import echo_error, echo_info, echo_success, echo_warning


@click.group("server")
def server_group() -> None:
    """Manage the local gateway server."""


@server_group.command("start")
@click.option("--host", default="127.0.0.1", help="Bind address.")
@click.option("--port", type=int, default=8080, help="Bind port.")
@click.option("--daemon", is_flag=True, default=False, help="Run in background.")
@click.option("--timeout", type=int, default=None, help="Request timeout in seconds.")
@click.option("--max-concurrency", type=int, default=None, help="Max concurrent requests.")
def server_start(
    host: str,
    port: int,
    daemon: bool,
    timeout: int | None,
    max_concurrency: int | None,
) -> None:
    """Start the gateway server."""
    from miniautogen.cli.services.server_ops import start_server

    root, _config = require_project_config()

    result = run_async(
        start_server,
        root,
        host=host,
        port=port,
        daemon=daemon,
        timeout=timeout,
        max_concurrency=max_concurrency,
    )

    if result["status"] == "already_running":
        echo_info(result["message"])
    elif result["status"] == "started":
        echo_success(result["message"])
    elif result["status"] == "starting":
        echo_info(result["message"])
        # Foreground mode: launch uvicorn directly
        import subprocess

        cmd = result.get("cmd", [])
        try:
            subprocess.run(cmd, cwd=str(root), check=True)
        except KeyboardInterrupt:
            echo_info("\nServer stopped.")
        except subprocess.CalledProcessError:
            echo_error("Server exited with error.")
            raise SystemExit(1)


@server_group.command("stop")
def server_stop() -> None:
    """Stop the gateway server."""
    from miniautogen.cli.services.server_ops import stop_server

    root, _config = require_project_config()
    result = run_async(stop_server, root)

    if result["status"] == "stopped" and result.get("pid"):
        echo_success(result["message"])
    else:
        echo_info(result["message"])


@server_group.command("status")
def server_status_cmd() -> None:
    """Show gateway server status."""
    from miniautogen.cli.services.server_ops import server_status

    root, _config = require_project_config()
    result = run_async(server_status, root)

    status = result["status"]
    msg = result["message"]

    if status == "running":
        echo_success(msg)
    elif status == "degraded":
        echo_warning(msg)
    elif status == "unreachable":
        echo_warning(msg)
    else:
        echo_info(msg)


@server_group.command("logs")
@click.option("--lines", "-n", type=int, default=50, help="Number of lines to show.")
def server_logs_cmd(lines: int) -> None:
    """Show recent gateway logs."""
    from miniautogen.cli.services.server_ops import server_logs

    root, _config = require_project_config()
    output = run_async(server_logs, root, lines=lines)
    click.echo(output)
