"""Abstract base class for event store persistence.

The EventStore tracks ExecutionEvent instances per run for replay and audit.
Implementations must be async-compatible (AnyIO).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from miniautogen.core.contracts.events import ExecutionEvent


class EventStore(ABC):
    """Abstract store for persisting execution events.

    Mirrors the store pattern used by RunStore, CheckpointStore, etc.
    All methods are async for compatibility with both in-memory and
    durable (SQLAlchemy) implementations.
    """

    @abstractmethod
    async def append(self, run_id: str, event: ExecutionEvent) -> None:
        """Append an event to the log for the given run.

        Events are stored in insertion order; the store assigns
        a monotonically increasing index per run automatically.

        Args:
            run_id: The run identifier.
            event: The execution event to persist.
        """

    @abstractmethod
    async def list_events(
        self,
        run_id: str,
        after_index: int = 0,
    ) -> list[ExecutionEvent]:
        """List events for a run, optionally starting after a given index.

        Args:
            run_id: The run identifier.
            after_index: Return only events with index >= this value.
                Defaults to 0 (all events).

        Returns:
            List of ExecutionEvent instances in insertion order.
        """

    @abstractmethod
    async def count_events(self, run_id: str) -> int:
        """Return the number of events stored for a given run.

        Returns 0 if the run has no events.
        """
