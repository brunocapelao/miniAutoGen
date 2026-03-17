from typing import Any

from miniautogen.stores.run_store import RunStore


class InMemoryRunStore(RunStore):
    """Simple in-memory run persistence for the new runtime."""

    def __init__(self) -> None:
        self._runs: dict[str, dict[str, Any]] = {}

    async def save_run(self, run_id: str, payload: dict[str, Any]) -> None:
        self._runs[run_id] = payload

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        return self._runs.get(run_id)

    async def list_runs(
        self,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        runs = list(self._runs.values())
        if status:
            runs = [r for r in runs if r.get("status") == status]
        return runs[:limit]

    async def delete_run(self, run_id: str) -> bool:
        if run_id in self._runs:
            del self._runs[run_id]
            return True
        return False
