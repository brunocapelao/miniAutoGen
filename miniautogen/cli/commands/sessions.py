"""miniautogen sessions command group."""

from __future__ import annotations

import click

from miniautogen.cli.config import require_project_config
from miniautogen.cli.main import run_async
from miniautogen.cli.output import (
    echo_error,
    echo_info,
    echo_json,
    echo_success,
    echo_table,
)


@click.group("sessions")
def sessions_group() -> None:
    """Manage local session/run data."""


@sessions_group.command("list")
@click.option("--status", default=None, help="Filter by status.")
@click.option("--limit", default=20, help="Max results.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
)
def sessions_list(
    status: str | None,
    limit: int,
    output_format: str,
) -> None:
    """List recent runs."""
    from miniautogen.cli.services.session_ops import (
        create_store_from_config,
        list_sessions,
    )

    _root, config = require_project_config()
    db_config = (
        config.database.model_dump()
        if config.database
        else None
    )
    store = create_store_from_config(db_config)

    runs = run_async(list_sessions, store, status, limit)

    if output_format == "json":
        echo_json(runs)
    elif not runs:
        echo_info("No runs found.")
    else:
        rows = [
            [
                str(r.get("run_id", "?"))[:12],
                str(r.get("status", "?")),
                str(r.get("created_at", "?")),
            ]
            for r in runs
        ]
        echo_table(["Run ID", "Status", "Created"], rows)


@sessions_group.command("clean")
@click.option(
    "--older-than",
    type=int,
    default=None,
    help="Only delete runs older than N days.",
)
@click.option(
    "--yes",
    "skip_confirm",
    is_flag=True,
    default=False,
    help="Skip confirmation prompt.",
)
def sessions_clean(
    older_than: int | None,
    skip_confirm: bool,
) -> None:
    """Remove completed/failed/cancelled runs."""
    from miniautogen.cli.services.session_ops import (
        clean_sessions,
        create_store_from_config,
    )

    if older_than is None and not skip_confirm:
        echo_error(
            "Specify --older-than N or --yes to confirm deletion"
        )
        raise SystemExit(1)

    _root, config = require_project_config()
    db_config = (
        config.database.model_dump()
        if config.database
        else None
    )
    store = create_store_from_config(db_config)

    if not skip_confirm:
        if not click.confirm("Delete matching runs?"):
            echo_info("Cancelled.")
            return

    count = run_async(clean_sessions, store, older_than)
    echo_success(f"Deleted {count} run(s).")
