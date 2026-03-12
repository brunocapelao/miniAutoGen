from __future__ import annotations

from typing import Protocol

from miniautogen.core.contracts.events import ExecutionEvent


class EventSink(Protocol):
    async def publish(self, event: ExecutionEvent) -> None:
        """Publish a runtime execution event."""


class InMemoryEventSink:
    def __init__(self) -> None:
        self.events: list[ExecutionEvent] = []

    async def publish(self, event: ExecutionEvent) -> None:
        self.events.append(event)


class NullEventSink:
    async def publish(self, event: ExecutionEvent) -> None:
        return None
