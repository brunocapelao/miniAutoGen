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

    # -- CRUD: Agents ----------------------------------------------------------

    def create_agent(self, name: str, *, role: str, goal: str, engine_profile: str, temperature: float | None = None) -> dict[str, Any]:
        return self._base.create_agent(name, role=role, goal=goal, engine_profile=engine_profile, temperature=temperature)

    def update_agent(self, name: str, **updates: Any) -> dict[str, Any]:
        return self._base.update_agent(name, **updates)

    def delete_agent(self, name: str) -> dict[str, Any]:
        return self._base.delete_agent(name)

    # -- CRUD: Engines ---------------------------------------------------------

    def get_engines(self) -> list[dict[str, Any]]:
        return self._base.get_engines()

    def get_engine(self, name: str) -> dict[str, Any]:
        return self._base.get_engine(name)

    def create_engine(self, name: str, *, provider: str, model: str, kind: str = "api", temperature: float = 0.2, api_key_env: str | None = None, endpoint: str | None = None) -> dict[str, Any]:
        return self._base.create_engine(name, provider=provider, model=model, kind=kind, temperature=temperature, api_key_env=api_key_env, endpoint=endpoint)

    def update_engine(self, name: str, **updates: Any) -> dict[str, Any]:
        return self._base.update_engine(name, **updates)

    def delete_engine(self, name: str) -> dict[str, Any]:
        return self._base.delete_engine(name)

    # -- Config: Read-only view ------------------------------------------------

    def get_config_detail(self) -> dict[str, Any]:
        return self._base.get_config_detail()

    # -- CRUD: Pipelines -------------------------------------------------------

    def create_pipeline(self, name: str, *, mode: str = "workflow", participants: list[str] | None = None, leader: str | None = None, target: str | None = None) -> dict[str, Any]:
        return self._base.create_pipeline(name, mode=mode, participants=participants, leader=leader, target=target)

    def update_pipeline(self, name: str, **updates: Any) -> dict[str, Any]:
        return self._base.update_pipeline(name, **updates)

    def delete_pipeline(self, name: str) -> dict[str, Any]:
        return self._base.delete_pipeline(name)

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
