"""Global event broadcaster for the console server.

Collects all events from running pipelines and broadcasts them
to connected WebSocket clients via the /ws/events endpoint.
"""
from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import Any

logger = logging.getLogger(__name__)

# Max events to keep in memory buffer
_MAX_BUFFER = 1000


class GlobalEventBroadcaster:
    """Broadcasts events to all connected WebSocket clients."""

    def __init__(self, max_buffer: int = _MAX_BUFFER) -> None:
        self._subscribers: set[asyncio.Queue] = set()
        self._buffer: deque[dict[str, Any]] = deque(maxlen=max_buffer)

    def subscribe(self) -> asyncio.Queue:
        """Create a new subscription queue for a WebSocket client."""
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Remove a subscription queue."""
        self._subscribers.discard(queue)

    async def publish(self, event: dict[str, Any]) -> None:
        """Publish an event to all subscribers and buffer it."""
        self._buffer.append(event)
        dead: list[asyncio.Queue] = []
        for queue in self._subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(queue)
        for q in dead:
            self._subscribers.discard(q)

    def get_recent(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent events from buffer."""
        items = list(self._buffer)
        return items[-limit:] if limit < len(items) else items

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)
