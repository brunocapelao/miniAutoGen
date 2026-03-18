"""miniautogen dash command -- launch the TUI dashboard."""

from __future__ import annotations

import sys

import click


def _check_textual_available() -> bool:
    """Check if textual is importable."""
    try:
        import textual  # noqa: F401

        return True
    except ImportError:
        return False


@click.command("dash")
@click.option(
    "--theme",
    type=click.Choice(["tokyo-night", "catppuccin", "monokai", "light"]),
    default="tokyo-night",
    help="Color theme for the dashboard.",
)
@click.option(
    "--notifications",
    type=click.Choice(["all", "failures-only", "none"]),
    default="all",
    help="Desktop notification level.",
)
def dash_command(theme: str, notifications: str) -> None:
    """Launch the TUI dashboard.

    Opens an interactive terminal UI showing your AI team at work.
    Requires the 'tui' extra: pip install miniautogen[tui]
    """
    if not _check_textual_available():
        click.secho(
            "Error: MiniAutoGen TUI requires the 'tui' extra.\n"
            "Install with: pip install miniautogen[tui]",
            fg="red",
            err=True,
        )
        raise SystemExit(1)

    from miniautogen.tui.app import MiniAutoGenDash

    app = MiniAutoGenDash()
    app.run()
