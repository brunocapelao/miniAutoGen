from abc import ABC, abstractmethod
from typing import Any


class RunStore(ABC):
    """Reserved contract for run persistence introduced in later waves."""

    @abstractmethod
    async def save_run(self, run_id: str, payload: dict[str, Any]) -> None:
        """Persist run metadata."""

    @abstractmethod
    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        """Fetch persisted run metadata."""

    @abstractmethod
    async def list_runs(
        self,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List runs, optionally filtered by status."""

    @abstractmethod
    async def delete_run(self, run_id: str) -> bool:
        """Delete a run. Returns True if found and deleted."""
