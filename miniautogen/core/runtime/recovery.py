"""Session recovery from checkpoints.

Enables resuming a run from its last saved checkpoint after
a crash or interruption.
"""

from __future__ import annotations

from typing import Any

from miniautogen.observability.logging import get_logger
from miniautogen.stores.checkpoint_store import CheckpointStore
from miniautogen.stores.run_store import RunStore

logger = get_logger(__name__)


class SessionRecovery:
    """Manages run recovery from checkpoints."""

    def __init__(
        self,
        checkpoint_store: CheckpointStore,
        run_store: RunStore | None = None,
    ) -> None:
        self._checkpoint_store = checkpoint_store
        self._run_store = run_store

    async def can_resume(self, run_id: str) -> bool:
        checkpoint = await self._checkpoint_store.get_checkpoint(
            run_id,
        )
        return checkpoint is not None

    async def load_checkpoint(
        self,
        run_id: str,
    ) -> dict[str, Any] | None:
        checkpoint = await self._checkpoint_store.get_checkpoint(
            run_id,
        )
        if checkpoint is not None:
            logger.info(
                "checkpoint_loaded",
                run_id=run_id,
            )
        return checkpoint

    async def mark_resumed(self, run_id: str) -> None:
        if self._run_store is not None:
            await self._run_store.save_run(
                run_id,
                {"status": "resumed"},
            )
            logger.info("run_marked_resumed", run_id=run_id)
