"""miniautogen console command — standalone web dashboard."""

from __future__ import annotations

from pathlib import Path

import click

from miniautogen.cli.output import echo_info


@click.command("console")
@click.option("--port", type=int, default=8080, help="Server port (default: 8080).")
@click.option(
    "--workspace",
    type=click.Path(exists=True, file_okay=False),
    default=".",
    help="Workspace directory (default: current directory).",
)
def console_command(port: int, workspace: str) -> None:
    """Launch the MiniAutoGen Console dashboard (standalone mode).

    Opens a web dashboard for observing agents, flows, and run history.
    Note: Standalone mode with live event access requires Sprint 2.
    """
    import webbrowser

    import uvicorn

    from miniautogen.server.app import create_app

    app = create_app(workspace_path=workspace, mode="standalone")

    url = f"http://localhost:{port}"
    echo_info(f"Console running at {url}")
    echo_info("Press Ctrl+C to stop.")
    webbrowser.open(url)

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
