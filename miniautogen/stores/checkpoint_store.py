from abc import ABC, abstractmethod
from typing import Any


class CheckpointStore(ABC):
    """Reserved contract for checkpoint persistence introduced later."""

    @abstractmethod
    async def save_checkpoint(self, run_id: str, payload: dict[str, Any]) -> None:
        """Persist checkpoint data."""

    @abstractmethod
    async def get_checkpoint(self, run_id: str) -> dict[str, Any] | None:
        """Fetch checkpoint data for a run."""

    @abstractmethod
    async def list_checkpoints(
        self,
        run_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """List checkpoints, optionally filtered by run_id."""

    @abstractmethod
    async def delete_checkpoint(self, run_id: str) -> bool:
        """Delete a checkpoint. Returns True if found and deleted."""
