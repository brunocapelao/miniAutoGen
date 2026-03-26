"""Protocol defining the data provider interface for Console Server routes."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ConsoleDataProvider(Protocol):
    """Protocol for data providers used by Console Server routes.

    DashDataProvider is the primary implementation.
    """

    def get_config(self) -> dict[str, Any]: ...
    def get_agents(self) -> list[dict[str, Any]]: ...
    def get_agent(self, name: str) -> dict[str, Any]: ...
    def get_pipelines(self) -> list[dict[str, Any]]: ...
    def get_pipeline(self, name: str) -> dict[str, Any]: ...
    def get_runs(self) -> list[dict[str, Any]]: ...
    def get_events(self) -> list[dict[str, Any]]: ...
    def record_run(self, run_data: dict[str, Any]) -> None: ...
    def update_run(self, run_id: str, updates: dict[str, Any]) -> None: ...
    async def run_pipeline(
        self,
        pipeline_name: str,
        *,
        event_sink: Any | None = None,
        timeout: float | None = None,
        pipeline_input: str | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]: ...

    async def query_runs(
        self,
        *,
        status: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """Query runs from persistent store. Returns (items, total)."""
        ...

    async def query_run(self, run_id: str) -> dict[str, Any] | None:
        """Query a single run from persistent store."""
        ...

    async def query_run_events(
        self,
        run_id: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[dict[str, Any]], int]:
        """Query events for a run from persistent store. Returns (items, total)."""
        ...

    # -- CRUD: Agents ----------------------------------------------------------

    def create_agent(
        self,
        name: str,
        *,
        role: str,
        goal: str,
        engine_profile: str,
        temperature: float | None = None,
    ) -> dict[str, Any]: ...

    def update_agent(self, name: str, **updates: Any) -> dict[str, Any]: ...

    def delete_agent(self, name: str) -> dict[str, Any]: ...

    # -- CRUD: Pipelines -------------------------------------------------------

    def create_pipeline(
        self,
        name: str,
        *,
        mode: str = "workflow",
        participants: list[str] | None = None,
        leader: str | None = None,
        target: str | None = None,
    ) -> dict[str, Any]: ...

    def update_pipeline(self, name: str, **updates: Any) -> dict[str, Any]: ...

    def delete_pipeline(self, name: str) -> dict[str, Any]: ...

    # -- CRUD: Engines ---------------------------------------------------------

    def get_engines(self) -> list[dict[str, Any]]: ...

    def get_engine(self, name: str) -> dict[str, Any]: ...

    def create_engine(
        self,
        name: str,
        *,
        provider: str,
        model: str,
        kind: str = "api",
        temperature: float = 0.2,
        api_key_env: str | None = None,
        endpoint: str | None = None,
    ) -> dict[str, Any]: ...

    def update_engine(self, name: str, **updates: Any) -> dict[str, Any]: ...

    def delete_engine(self, name: str) -> dict[str, Any]: ...

    # -- Config: Read-only view ------------------------------------------------

    def get_config_detail(self) -> dict[str, Any]:
        """Get detailed config for settings editor.

        Unlike get_config() which returns a summary, this returns
        the full structure needed for the settings editor.
        """
        ...
