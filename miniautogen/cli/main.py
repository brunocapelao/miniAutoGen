"""MiniAutoGen CLI entry point.

Provides the Click command group and async bridge helper.
"""

from __future__ import annotations

from typing import Any

import anyio
import click

try:
    from importlib.metadata import version as pkg_version

    _VERSION = pkg_version("miniautogen")
except Exception:
    _VERSION = "0.1.0"


def run_async(func: Any, *args: Any, **kwargs: Any) -> Any:
    """Run an async function synchronously via anyio."""

    async def _wrapper() -> Any:
        return await func(*args, **kwargs)

    return anyio.run(_wrapper)


@click.group(invoke_without_command=True)
@click.version_option(version=_VERSION, prog_name="miniautogen")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """MiniAutoGen -- Multi-agent orchestration framework."""
    if ctx.invoked_subcommand is None:
        import re
        from pathlib import Path

        from miniautogen.cli.commands.team import team_command
        from miniautogen.cli.output import echo_info
        from miniautogen.cli.services.init_project import scaffold_project

        root = Path.cwd()
        if not (root / "miniautogen.yaml").exists():
            echo_info("No workspace found. Auto-initializing with quickstart template...")
            
            # Ensure name is valid, else fallback
            name = root.name
            if not re.match(r"^[a-zA-Z][a-zA-Z0-9_-]*$", name):
                name = "miniautogen-project"
                
            scaffold_project(
                name=name,
                target_dir=root.parent,
                force=True,
                template="quickstart",
                model="gemini-2.5-pro",
                provider="gemini-cli",  # Native CLI provider
            )
            echo_info("Workspace initialized with 'tech_lead' agent.")

        # If no command, default to 'team' mode
        ctx.invoke(team_command)



# Import and register commands
from miniautogen.cli.commands.agent import agent_group
from miniautogen.cli.commands.chat import chat_command
from miniautogen.cli.commands.check import check_command
from miniautogen.cli.commands.completions import completions_command
from miniautogen.cli.commands.console import console_command
from miniautogen.cli.commands.daemon import daemon_group
from miniautogen.cli.commands.dash import dash_command
from miniautogen.cli.commands.doctor import doctor_command
from miniautogen.cli.commands.engine import engine_group
from miniautogen.cli.commands.flow import flow_group
from miniautogen.cli.commands.init import init_command
from miniautogen.cli.commands.lead import lead_command
from miniautogen.cli.commands.pipeline import pipeline_group
from miniautogen.cli.commands.run import run_command
from miniautogen.cli.commands.send import send_command
from miniautogen.cli.commands.server import server_group
from miniautogen.cli.commands.sessions import sessions_group
from miniautogen.cli.commands.status import status_command
from miniautogen.cli.commands.team import team_command

cli.add_command(init_command)
cli.add_command(check_command)
cli.add_command(run_command)
cli.add_command(sessions_group)
cli.add_command(engine_group)
cli.add_command(agent_group)
cli.add_command(flow_group)
cli.add_command(server_group)
cli.add_command(doctor_command)
cli.add_command(completions_command)
cli.add_command(dash_command)
cli.add_command(console_command)
cli.add_command(send_command)
cli.add_command(chat_command)
cli.add_command(status_command)
cli.add_command(daemon_group)
cli.add_command(team_command)
cli.add_command(lead_command)

# Hidden/Legacy
pipeline_group.hidden = True
cli.add_command(pipeline_group)
