"""Event filtering for selective event subscription.

Filters are composable predicates that determine which events
reach which sinks. Combine with FilteredEventSink for selective
event routing.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.types import EventType


@runtime_checkable
class EventFilter(Protocol):
    """Predicate that decides whether an event should be forwarded."""

    def matches(self, event: ExecutionEvent) -> bool: ...


class TypeFilter:
    """Matches events by their type."""

    def __init__(self, event_types: set[EventType | str]) -> None:
        self._types = {
            t.value if isinstance(t, EventType) else t
            for t in event_types
        }

    def matches(self, event: ExecutionEvent) -> bool:
        return event.type in self._types


class RunFilter:
    """Matches events by run_id."""

    def __init__(self, run_id: str) -> None:
        self._run_id = run_id

    def matches(self, event: ExecutionEvent) -> bool:
        return event.run_id == self._run_id


class CompositeFilter:
    """Combines multiple filters with AND or OR logic."""

    def __init__(
        self,
        filters: list[EventFilter],
        mode: str = "all",
    ) -> None:
        if mode not in ("all", "any"):
            msg = f"mode must be 'all' or 'any', got '{mode}'"
            raise ValueError(msg)
        self._filters = filters
        self._mode = mode

    def matches(self, event: ExecutionEvent) -> bool:
        if self._mode == "all":
            return all(f.matches(event) for f in self._filters)
        return any(f.matches(event) for f in self._filters)
