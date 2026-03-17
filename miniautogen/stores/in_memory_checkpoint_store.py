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

    async def list_checkpoints(
        self,
        run_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if run_id is not None:
            cp = self._checkpoints.get(run_id)
            return [cp] if cp is not None else []
        return list(self._checkpoints.values())

    async def delete_checkpoint(self, run_id: str) -> bool:
        if run_id in self._checkpoints:
            del self._checkpoints[run_id]
            return True
        return False
