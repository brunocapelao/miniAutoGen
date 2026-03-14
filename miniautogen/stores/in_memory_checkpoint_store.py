from typing import Any

from miniautogen.stores.checkpoint_store import CheckpointStore


class InMemoryCheckpointStore(CheckpointStore):
    """Simple in-memory checkpoint persistence for the new runtime."""

    def __init__(self) -> None:
        self._checkpoints: dict[str, dict[str, Any]] = {}

    async def save_checkpoint(self, run_id: str, payload: dict[str, Any]) -> None:
        self._checkpoints[run_id] = payload

    async def get_checkpoint(self, run_id: str) -> dict[str, Any] | None:
        return self._checkpoints.get(run_id)
