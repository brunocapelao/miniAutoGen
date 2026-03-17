"""Presentation layer for CLI terminal output."""

from __future__ import annotations

import json
from typing import Any

import click


def echo_success(msg: str) -> None:
    """Print a success message in green."""
    click.secho(msg, fg="green")


def echo_error(msg: str) -> None:
    """Print an error message in red."""
    click.secho(msg, fg="red", err=True)


def echo_info(msg: str) -> None:
    """Print an informational message in blue."""
    click.secho(msg, fg="blue")


def echo_warning(msg: str) -> None:
    """Print a warning message in yellow."""
    click.secho(msg, fg="yellow")


def echo_json(data: Any) -> None:
    """Print data as formatted JSON."""
    click.echo(json.dumps(data, indent=2, default=str))


def echo_table(
    headers: list[str],
    rows: list[list[str]],
) -> None:
    """Print a simple aligned text table."""
    if not rows:
        click.echo("(no data)")
        return

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(cell)))

    header_line = "  ".join(
        h.ljust(col_widths[i]) for i, h in enumerate(headers)
    )
    separator = "  ".join("-" * w for w in col_widths)
    click.echo(header_line)
    click.echo(separator)
    for row in rows:
        line = "  ".join(
            str(cell).ljust(col_widths[i])
            for i, cell in enumerate(row[:len(headers)])
        )
        click.echo(line)
