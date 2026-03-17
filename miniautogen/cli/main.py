"""MiniAutoGen CLI entry point.

Provides the Click command group and async bridge helper.
"""

from __future__ import annotations

from typing import Any

import anyio
import click


def run_async(func: Any, *args: Any, **kwargs: Any) -> Any:
    """Run an async function synchronously via anyio."""

    async def _wrapper() -> Any:
        return await func(*args, **kwargs)

    return anyio.run(_wrapper)


@click.group()
@click.version_option(version="0.1.0", prog_name="miniautogen")
def cli() -> None:
    """MiniAutoGen -- Multi-agent orchestration framework."""


from miniautogen.cli.commands.init import init_command  # noqa: E402

cli.add_command(init_command)
