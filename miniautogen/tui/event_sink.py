"""TuiEventSink -- bridges core ExecutionEvents to the Textual UI loop.

Uses anyio.create_memory_object_stream() for async-safe cross-loop
communication. The PipelineRunner publishes events via publish(),
and the Textual Worker reads via receive().

This module imports ONLY protocols and data models from core.
Zero coupling to runtime internals.
"""

from __future__ import annotations

import anyio
from anyio.abc import ObjectReceiveStream, ObjectSendStream

from miniautogen.core.contracts.events import ExecutionEvent

# Default buffer: 256 events before backpressure
_DEFAULT_BUFFER_SIZE = 256


class TuiEventSink:
    """EventSink that bridges events to a Textual app via memory stream.

    Satisfies the EventSink protocol::

        async def publish(self, event: ExecutionEvent) -> None

    Usage::

        sink = TuiEventSink()
        # Pass sink to PipelineRunner as event_sink
        runner = PipelineRunner(event_sink=CompositeEventSink([existing, sink]))
        # In Textual Worker, read events:
        async for event in sink:
            self.post_message(TuiEvent(event))
    """

    def __init__(self, buffer_size: int = _DEFAULT_BUFFER_SIZE) -> None:
        send: ObjectSendStream[ExecutionEvent]
        recv: ObjectReceiveStream[ExecutionEvent]
        send, recv = anyio.create_memory_object_stream[ExecutionEvent](
            max_buffer_size=buffer_size,
        )
        self._send = send
        self._recv = recv

    async def publish(self, event: ExecutionEvent) -> None:
        """Publish an event to the stream (called by PipelineRunner)."""
        await self._send.send(event)

    async def receive(self) -> ExecutionEvent:
        """Receive the next event from the stream (called by Textual Worker)."""
        return await self._recv.receive()

    def __aiter__(self) -> TuiEventSink:
        return self

    async def __anext__(self) -> ExecutionEvent:
        try:
            return await self._recv.receive()
        except anyio.EndOfStream:
            raise StopAsyncIteration

    async def close(self) -> None:
        """Close both ends of the stream."""
        await self._send.aclose()
        await self._recv.aclose()

    async def __aenter__(self) -> TuiEventSink:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()
