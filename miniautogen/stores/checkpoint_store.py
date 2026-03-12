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
