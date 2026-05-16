"""UI event sink selection and shared verbose sink.

This module avoids circular imports between run.py (CLI command) and
run_pipeline.py (execution service) by centralising sink creation.
"""

from __future__ import annotations

import os
import sys

from miniautogen.api import ExecutionEvent


class _VerboseEventSink:
    """Event sink that echoes events to stderr for --verbose mode."""

    async def publish(self, event: ExecutionEvent) -> None:
        import click

        click.echo(
            f"[{event.type}] run_id={event.run_id} scope={event.scope}",
            err=True,
        )


def _select_ui_sink(
    *,
    output_format: str,
    verbose: bool,
) -> _VerboseEventSink | None:
    """Decide which UI sink to use based on env, format, and TTY.

    Returns a RichLiveEventSink (via lazy import), _VerboseEventSink,
    or None (JSON mode).
    """
    if output_format == "json":
        return None
    if os.environ.get("MINIAUTOGEN_NO_TTY") == "1":
        return _VerboseEventSink()
    if verbose:
        return _VerboseEventSink()
    if sys.stderr.isatty():
        from miniautogen.cli.services.rich_live_sink import RichLiveEventSink

        return RichLiveEventSink()
    return _VerboseEventSink()
