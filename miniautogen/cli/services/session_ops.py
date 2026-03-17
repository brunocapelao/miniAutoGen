"""Session/run management service for the CLI."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from miniautogen.api import InMemoryRunStore, RunStore

# Status values that are safe to delete
_CLEANABLE_STATUSES = frozenset({
    "completed", "finished", "failed", "cancelled", "timed_out",
})


async def list_sessions(
    store: RunStore,
    status: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """List runs from store, optionally filtered by status."""
    runs = await store.list_runs(status=status, limit=limit)
    return runs


async def clean_sessions(
    store: RunStore,
    older_than_days: int | None = None,
) -> int:
    """Delete completed/failed/cancelled runs.

    NEVER deletes active (started) runs. Returns count deleted.
    """
    all_runs = await store.list_runs()
    deleted = 0

    for run in all_runs:
        run_status = run.get("status", "")
        if run_status not in _CLEANABLE_STATUSES:
            continue

        if older_than_days is not None:
            created = run.get("created_at")
            if created:
                try:
                    created_dt = datetime.fromisoformat(
                        str(created).replace("Z", "+00:00"),
                    )
                    age = (
                        datetime.now(timezone.utc) - created_dt
                    ).days
                    if age < older_than_days:
                        continue
                except (ValueError, TypeError):
                    continue  # Cannot determine age; skip to be safe

        run_id = run.get("run_id")
        if run_id:
            result = await store.delete_run(run_id)
            if result:
                deleted += 1

    return deleted


def create_store_from_config(
    database_config: dict[str, Any] | None,
) -> RunStore:
    """Create a RunStore from project database config.

    Uses InMemoryRunStore if no database URL configured.
    """
    if database_config and database_config.get("url"):
        import warnings

        warnings.warn(
            "Database-backed sessions not yet supported; "
            "using in-memory store. Data will not persist.",
            stacklevel=2,
        )
    return InMemoryRunStore()
