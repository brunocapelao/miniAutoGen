"""Tests for TuiEventSink -- the bridge between core events and Textual UI."""

from __future__ import annotations

import pytest

import anyio

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.types import EventType
from miniautogen.tui.event_sink import TuiEventSink


@pytest.mark.asyncio
async def test_tui_event_sink_satisfies_protocol() -> None:
    """TuiEventSink must satisfy the EventSink protocol (duck-typing check)."""
    sink = TuiEventSink()
    assert hasattr(sink, "publish")
    assert callable(sink.publish)


@pytest.mark.asyncio
async def test_tui_event_sink_publishes_to_stream() -> None:
    """Published events must be receivable from the stream."""
    sink = TuiEventSink()
    event = ExecutionEvent(
        type=EventType.RUN_STARTED.value,
        run_id="run-1",
        correlation_id="corr-1",
    )

    await sink.publish(event)

    received = await sink.receive()
    assert received.type == EventType.RUN_STARTED.value
    assert received.run_id == "run-1"


@pytest.mark.asyncio
async def test_tui_event_sink_multiple_events_ordered() -> None:
    """Multiple events must be received in publish order."""
    sink = TuiEventSink()

    events = [
        ExecutionEvent(type=EventType.RUN_STARTED.value, run_id="run-1"),
        ExecutionEvent(type=EventType.COMPONENT_STARTED.value, run_id="run-1"),
        ExecutionEvent(type=EventType.COMPONENT_FINISHED.value, run_id="run-1"),
    ]

    for event in events:
        await sink.publish(event)

    received = []
    for _ in range(3):
        received.append(await sink.receive())

    assert [e.type for e in received] == [
        EventType.RUN_STARTED.value,
        EventType.COMPONENT_STARTED.value,
        EventType.COMPONENT_FINISHED.value,
    ]


@pytest.mark.asyncio
async def test_tui_event_sink_close() -> None:
    """Closing the sink must close the underlying stream."""
    sink = TuiEventSink()
    await sink.publish(
        ExecutionEvent(type=EventType.RUN_STARTED.value, run_id="run-1"),
    )
    await sink.close()

    with pytest.raises(anyio.ClosedResourceError):
        await sink.publish(
            ExecutionEvent(type=EventType.RUN_FINISHED.value, run_id="run-1"),
        )


@pytest.mark.asyncio
async def test_tui_event_sink_context_manager() -> None:
    """TuiEventSink must work as an async context manager."""
    async with TuiEventSink() as sink:
        await sink.publish(
            ExecutionEvent(type=EventType.RUN_STARTED.value, run_id="run-1"),
        )
        received = await sink.receive()
        assert received.type == EventType.RUN_STARTED.value


@pytest.mark.asyncio
async def test_tui_event_sink_buffer_size() -> None:
    """TuiEventSink must accept a configurable buffer size."""
    sink = TuiEventSink(buffer_size=2)

    # Fill the buffer
    await sink.publish(
        ExecutionEvent(type=EventType.RUN_STARTED.value, run_id="run-1"),
    )
    await sink.publish(
        ExecutionEvent(type=EventType.COMPONENT_STARTED.value, run_id="run-1"),
    )

    # Buffer is full -- verify we can still drain
    r1 = await sink.receive()
    r2 = await sink.receive()
    assert r1.type == EventType.RUN_STARTED.value
    assert r2.type == EventType.COMPONENT_STARTED.value
