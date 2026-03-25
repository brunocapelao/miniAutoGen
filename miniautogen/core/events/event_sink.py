from __future__ import annotations

from typing import Protocol

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.filters import EventFilter


class EventSink(Protocol):
    async def publish(self, event: ExecutionEvent) -> None:
        """Publish a runtime execution event."""


class InMemoryEventSink:
    def __init__(self) -> None:
        self.events: list[ExecutionEvent] = []

    async def publish(self, event: ExecutionEvent) -> None:
        self.events.append(event)

    async def __aenter__(self) -> InMemoryEventSink:
        return self

    async def __aexit__(self, *exc: object) -> None:
        pass


class NullEventSink:
    async def publish(self, event: ExecutionEvent) -> None:
        return None

    async def __aenter__(self) -> NullEventSink:
        return self

    async def __aexit__(self, *exc: object) -> None:
        pass


class CompositeEventSink:
    """Fans out events to multiple sinks."""

    def __init__(self, sinks: list[EventSink]) -> None:
        self._sinks = list(sinks)

    async def publish(self, event: ExecutionEvent) -> None:
        for sink in self._sinks:
            try:
                await sink.publish(event)
            except Exception:
                import logging

                logging.getLogger(__name__).warning(
                    "Event sink %s failed to publish event %s",
                    type(sink).__name__,
                    event.type,
                    exc_info=True,
                )

    async def __aenter__(self) -> CompositeEventSink:
        return self

    async def __aexit__(self, *exc: object) -> None:
        pass


class FilteredEventSink:
    """Only forwards events that match a filter."""

    def __init__(
        self, sink: EventSink, filter: EventFilter  # noqa: A002
    ) -> None:
        self._sink = sink
        self._filter = filter

    async def publish(self, event: ExecutionEvent) -> None:
        if self._filter.matches(event):
            await self._sink.publish(event)

    async def __aenter__(self) -> FilteredEventSink:
        return self

    async def __aexit__(self, *exc: object) -> None:
        pass
