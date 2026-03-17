"""Tests for CompositeEventSink and FilteredEventSink."""

import pytest

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.event_sink import (
    CompositeEventSink,
    FilteredEventSink,
    InMemoryEventSink,
    NullEventSink,
)
from miniautogen.core.events.filters import TypeFilter
from miniautogen.core.events.types import EventType


def _make_event(
    event_type: str = "run_started",
    run_id: str = "run-1",
) -> ExecutionEvent:
    return ExecutionEvent(type=event_type, run_id=run_id)


@pytest.mark.anyio
async def test_composite_fans_out_to_all_sinks() -> None:
    s1 = InMemoryEventSink()
    s2 = InMemoryEventSink()
    composite = CompositeEventSink([s1, s2])
    event = _make_event()
    await composite.publish(event)
    assert len(s1.events) == 1
    assert len(s2.events) == 1


@pytest.mark.anyio
async def test_composite_empty_sinks() -> None:
    composite = CompositeEventSink([])
    await composite.publish(_make_event())  # no error


@pytest.mark.anyio
async def test_filtered_forwards_matching() -> None:
    sink = InMemoryEventSink()
    filtered = FilteredEventSink(
        sink, TypeFilter({EventType.RUN_STARTED})
    )
    await filtered.publish(_make_event("run_started"))
    await filtered.publish(_make_event("run_failed"))
    assert len(sink.events) == 1
    assert sink.events[0].type == "run_started"


@pytest.mark.anyio
async def test_filtered_blocks_non_matching() -> None:
    sink = InMemoryEventSink()
    filtered = FilteredEventSink(
        sink, TypeFilter({EventType.RUN_FAILED})
    )
    await filtered.publish(_make_event("run_started"))
    assert len(sink.events) == 0


@pytest.mark.anyio
async def test_in_memory_sink_async_context_manager() -> None:
    async with InMemoryEventSink() as sink:
        await sink.publish(_make_event())
        assert len(sink.events) == 1


@pytest.mark.anyio
async def test_null_sink_async_context_manager() -> None:
    async with NullEventSink() as sink:
        await sink.publish(_make_event())  # no error


@pytest.mark.anyio
async def test_composite_async_context_manager() -> None:
    async with CompositeEventSink([InMemoryEventSink()]) as c:
        await c.publish(_make_event())


@pytest.mark.anyio
async def test_filtered_async_context_manager() -> None:
    sink = InMemoryEventSink()
    f = TypeFilter({EventType.RUN_STARTED})
    async with FilteredEventSink(sink, f) as fs:
        await fs.publish(_make_event())
        assert len(sink.events) == 1
