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


@click.group()
@click.version_option(version=_VERSION, prog_name="miniautogen")
def cli() -> None:
    """MiniAutoGen -- Multi-agent orchestration framework."""


from miniautogen.cli.commands.init import init_command  # noqa: E402

cli.add_command(init_command)

from miniautogen.cli.commands.check import check_command  # noqa: E402

cli.add_command(check_command)

from miniautogen.cli.commands.run import run_command  # noqa: E402

cli.add_command(run_command)

from miniautogen.cli.commands.sessions import sessions_group  # noqa: E402

cli.add_command(sessions_group)

from miniautogen.cli.commands.engine import engine_group  # noqa: E402

cli.add_command(engine_group)

from miniautogen.cli.commands.agent import agent_group  # noqa: E402

cli.add_command(agent_group)

from miniautogen.cli.commands.flow import flow_group  # noqa: E402

cli.add_command(flow_group)

from miniautogen.cli.commands.pipeline import pipeline_group  # noqa: E402

pipeline_group.hidden = True
cli.add_command(pipeline_group)

from miniautogen.cli.commands.server import server_group  # noqa: E402

cli.add_command(server_group)

from miniautogen.cli.commands.doctor import doctor_command  # noqa: E402

cli.add_command(doctor_command)

from miniautogen.cli.commands.completions import completions_command  # noqa: E402

cli.add_command(completions_command)

from miniautogen.cli.commands.dash import dash_command  # noqa: E402

cli.add_command(dash_command)

from miniautogen.cli.commands.console import console_command  # noqa: E402

cli.add_command(console_command)

from miniautogen.cli.commands.send import send_command  # noqa: E402

cli.add_command(send_command)

from miniautogen.cli.commands.chat import chat_command  # noqa: E402

cli.add_command(chat_command)

from miniautogen.cli.commands.status import status_command  # noqa: E402

cli.add_command(status_command)

from miniautogen.cli.commands.daemon import daemon_group  # noqa: E402

cli.add_command(daemon_group)
