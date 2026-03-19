"""CheckpointManager: coordinated state transitions with checkpoint + event persistence.

Composes CheckpointStore + EventStore for coordinated state transitions.
atomic_transition saves checkpoint + appends events + publishes to live sink.
Uses composition (not DB transactions) -- works with any store implementation.
True DB-level atomicity requires a SQLAlchemy-specific subclass (future).
"""

from __future__ import annotations

from typing import Any

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.event_sink import EventSink
from miniautogen.stores.checkpoint_store import CheckpointStore
from miniautogen.stores.event_store import EventStore


class CheckpointManager:
    """Composes CheckpointStore + EventStore for coordinated state transitions.

    atomic_transition saves checkpoint + appends events + publishes to live sink.
    Uses composition (not DB transactions) -- works with any store implementation.
    True DB-level atomicity requires a SQLAlchemy-specific subclass (future).
    """

    def __init__(
        self,
        checkpoint_store: CheckpointStore,
        event_store: EventStore,
        event_sink: EventSink | None = None,
    ) -> None:
        self._checkpoint_store = checkpoint_store
        self._event_store = event_store
        self._event_sink = event_sink

    async def atomic_transition(
        self,
        run_id: str,
        *,
        new_state: Any,
        events: list[ExecutionEvent],
        step_index: int,
    ) -> None:
        """Save checkpoint with step_index, append events to store, publish to live sink.

        Args:
            run_id: The run identifier.
            new_state: The state to persist in the checkpoint.
            events: Events to append to the event store.
            step_index: The current step index for resume support.
        """
        # 1. Save checkpoint
        await self._checkpoint_store.save_checkpoint(
            run_id, {"state": new_state, "step_index": step_index}
        )

        # 2. Append each event to event_store
        for event in events:
            await self._event_store.append(run_id, event)

        # 3. Publish each event to event_sink (fire-and-forget)
        if self._event_sink is not None:
            for event in events:
                await self._event_sink.publish(event)

    async def get_last_checkpoint(
        self, run_id: str
    ) -> tuple[Any, int] | None:
        """Load last checkpoint, return (state, step_index) or None.

        Args:
            run_id: The run identifier.

        Returns:
            Tuple of (state, step_index) or None if no checkpoint exists.
        """
        cp = await self._checkpoint_store.get_checkpoint(run_id)
        if cp is None:
            return None
        return cp["state"], cp["step_index"]

    async def get_events(
        self, run_id: str, after_index: int = 0
    ) -> list[ExecutionEvent]:
        """Retrieve events for a run.

        Args:
            run_id: The run identifier.
            after_index: Return only events with index >= this value.

        Returns:
            List of ExecutionEvent instances in insertion order.
        """
        return await self._event_store.list_events(run_id, after_index=after_index)
