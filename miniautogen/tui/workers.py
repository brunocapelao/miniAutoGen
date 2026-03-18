"""Textual Workers for background event processing.

EventBridgeWorker reads from TuiEventSink's receive stream and
posts TuiEvent messages into the Textual message loop.

Uses batching (100ms) to coalesce renders via App.batch_update().
"""

from __future__ import annotations

import asyncio
from collections import deque

from miniautogen.tui.event_sink import TuiEventSink
from miniautogen.tui.messages import TuiEvent

# Batch interval: coalesce events within this window to reduce renders
_BATCH_INTERVAL_SECONDS = 0.1


class EventBridgeWorker:
    """Reads events from TuiEventSink and posts them as TuiEvent messages.

    This worker is started by the App and runs in the background.
    It bridges the anyio MemoryObjectStream to Textual's message loop.

    Usage in App::

        def on_mount(self) -> None:
            self._bridge = EventBridgeWorker(self._event_sink)
            self.run_worker(self._bridge.run(self), exclusive=True)

    The worker reads events in a loop, batches them every 100ms,
    and calls app.post_message() within app.batch_update() to
    coalesce widget re-renders.
    """

    def __init__(self, sink: TuiEventSink) -> None:
        self._sink = sink

    async def run(self, app: object) -> None:
        """Main worker loop. Reads events and posts TuiEvent messages.

        Batches events every 100ms using App.batch_update() to
        reduce the number of render passes.

        Args:
            app: The Textual App instance (must have post_message and
                 batch_update methods).
        """
        post_message = getattr(app, "post_message")
        batch_update = getattr(app, "batch_update", None)
        buffer: deque[TuiEvent] = deque()

        async def _drain() -> None:
            """Post all buffered events, optionally within batch_update."""
            if not buffer:
                return
            if batch_update is not None:
                with batch_update():
                    while buffer:
                        post_message(buffer.popleft())
            else:
                while buffer:
                    post_message(buffer.popleft())

        try:
            async for event in self._sink:
                buffer.append(TuiEvent(event))
                # Allow more events to arrive within the batch window
                await asyncio.sleep(_BATCH_INTERVAL_SECONDS)
                await _drain()
        except (asyncio.CancelledError, GeneratorExit):
            # Worker cancelled -- drain remaining events
            await _drain()
