"""In-memory implementation of EventStore for testing and single-process use."""

from __future__ import annotations

from collections import defaultdict

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.stores.event_store import EventStore


class InMemoryEventStore(EventStore):
    """Dict-of-lists-backed event store.

    Sufficient for testing and single-process use.
    Not suitable for multi-process or durable persistence.
    """

    def __init__(self) -> None:
        self._events: dict[str, list[ExecutionEvent]] = defaultdict(list)

    async def append(self, run_id: str, event: ExecutionEvent) -> None:
        """Append an event to the log for the given run."""
        self._events[run_id].append(event)

    async def list_events(
        self,
        run_id: str,
        after_index: int = 0,
    ) -> list[ExecutionEvent]:
        """List events for a run, optionally starting after a given index."""
        return list(self._events[run_id][after_index:])

    async def count_events(self, run_id: str) -> int:
        """Return the number of events stored for a given run."""
        return len(self._events[run_id])
