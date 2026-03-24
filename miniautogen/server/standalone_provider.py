"""Store-backed provider for standalone Console mode."""

from __future__ import annotations

import logging
from typing import Any

from miniautogen.stores.event_store import EventStore
from miniautogen.stores.run_store import RunStore

logger = logging.getLogger(__name__)


class StandaloneProvider:
    """ConsoleDataProvider backed by RunStore + EventStore.

    Config/agents/flows are delegated to a base provider (DashDataProvider).
    Run and event queries go through persistent stores.
    """

    def __init__(
        self,
        *,
        base_provider: Any,
        run_store: RunStore,
        event_store: EventStore,
    ) -> None:
        self._base = base_provider
        self._run_store = run_store
        self._event_store = event_store

    # -- Delegated to base provider -------------------------------------------

    def get_config(self) -> dict[str, Any]:
        return self._base.get_config()

    def get_agents(self) -> list[dict[str, Any]]:
        return self._base.get_agents()

    def get_agent(self, name: str) -> dict[str, Any]:
        return self._base.get_agent(name)

    def get_pipelines(self) -> list[dict[str, Any]]:
        return self._base.get_pipelines()

    def get_pipeline(self, name: str) -> dict[str, Any]:
        return self._base.get_pipeline(name)

    # -- In-memory compatibility (Sprint 1 interface) -------------------------

    def get_runs(self) -> list[dict[str, Any]]:
        """Sync fallback -- returns empty for standalone. Use query_runs()."""
        return []

    def get_events(self) -> list[dict[str, Any]]:
        """Sync fallback -- returns empty for standalone. Use query_run_events()."""
        return []

    def record_run(self, run_data: dict[str, Any]) -> None:
        """Not supported in standalone read-only mode."""
        logger.warning("record_run called in standalone mode (no-op): %s", run_data.get("run_id"))

    def update_run(self, run_id: str, updates: dict[str, Any]) -> None:
        """Not supported in standalone read-only mode."""
        logger.warning("update_run called in standalone mode (no-op): %s", run_id)

    async def run_pipeline(
        self,
        pipeline_name: str,
        *,
        event_sink: Any | None = None,
        timeout: float | None = None,
        pipeline_input: str | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        """Not supported in standalone mode -- runs are observed, not triggered."""
        raise NotImplementedError("Cannot trigger runs in standalone mode")

    # -- Store-backed async queries -------------------------------------------

    async def query_runs(
        self,
        *,
        status: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        # RunStore.list_runs doesn't support offset or count; fetch all and slice.
        # The limit param on list_runs caps returned rows — use offset+limit to
        # avoid loading more than needed while still computing correct total.
        all_runs = await self._run_store.list_runs(status=status, limit=offset + limit)
        total = len(all_runs)
        return all_runs[offset : offset + limit], total

    async def query_run(self, run_id: str) -> dict[str, Any] | None:
        return await self._run_store.get_run(run_id)

    async def query_run_events(
        self,
        run_id: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[dict[str, Any]], int]:
        events = await self._event_store.list_events(run_id, after_index=offset)
        total = await self._event_store.count_events(run_id)
        items = [
            {
                "type": e.type,
                "timestamp": e.timestamp.isoformat(),
                "run_id": e.run_id,
                "scope": e.scope,
                "payload": e.payload,
            }
            for e in events[:limit]
        ]
        return items, total
