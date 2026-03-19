"""Tests for InMemoryEventStore implementation."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from miniautogen.core.contracts.events import ExecutionEvent


def _make_event(
    event_type: str = "component_finished",
    run_id: str | None = "run-1",
) -> ExecutionEvent:
    return ExecutionEvent(
        type=event_type,
        run_id=run_id,
        timestamp=datetime.now(timezone.utc),
        payload={"status": "ok"},
    )


class TestInMemoryEventStoreImport:
    def test_import(self) -> None:
        from miniautogen.stores.in_memory_event_store import InMemoryEventStore  # noqa: F401

    def test_is_subclass_of_abc(self) -> None:
        from miniautogen.stores.event_store import EventStore
        from miniautogen.stores.in_memory_event_store import InMemoryEventStore

        assert issubclass(InMemoryEventStore, EventStore)


@pytest.mark.asyncio
async def test_append_and_list_roundtrip() -> None:
    from miniautogen.stores.in_memory_event_store import InMemoryEventStore

    store = InMemoryEventStore()
    event = _make_event()

    await store.append("run-1", event)
    events = await store.list_events("run-1")

    assert len(events) == 1
    assert events[0].type == "component_finished"
    assert events[0].run_id == "run-1"


@pytest.mark.asyncio
async def test_after_index_filtering() -> None:
    from miniautogen.stores.in_memory_event_store import InMemoryEventStore

    store = InMemoryEventStore()
    await store.append("run-1", _make_event(event_type="run_started"))
    await store.append("run-1", _make_event(event_type="component_finished"))
    await store.append("run-1", _make_event(event_type="run_finished"))

    # Get all events
    all_events = await store.list_events("run-1")
    assert len(all_events) == 3

    # Get events after index 1
    after_1 = await store.list_events("run-1", after_index=1)
    assert len(after_1) == 2
    assert after_1[0].type == "component_finished"

    # Get events after index 2
    after_2 = await store.list_events("run-1", after_index=2)
    assert len(after_2) == 1
    assert after_2[0].type == "run_finished"

    # Get events after last index
    after_3 = await store.list_events("run-1", after_index=3)
    assert len(after_3) == 0


@pytest.mark.asyncio
async def test_count_events() -> None:
    from miniautogen.stores.in_memory_event_store import InMemoryEventStore

    store = InMemoryEventStore()
    await store.append("run-1", _make_event())
    await store.append("run-1", _make_event())
    await store.append("run-1", _make_event())

    assert await store.count_events("run-1") == 3


@pytest.mark.asyncio
async def test_count_events_empty_run() -> None:
    from miniautogen.stores.in_memory_event_store import InMemoryEventStore

    store = InMemoryEventStore()
    assert await store.count_events("nonexistent") == 0


@pytest.mark.asyncio
async def test_list_events_empty_run() -> None:
    from miniautogen.stores.in_memory_event_store import InMemoryEventStore

    store = InMemoryEventStore()
    events = await store.list_events("nonexistent")
    assert events == []


@pytest.mark.asyncio
async def test_multiple_runs_isolated() -> None:
    from miniautogen.stores.in_memory_event_store import InMemoryEventStore

    store = InMemoryEventStore()
    await store.append("run-1", _make_event(run_id="run-1"))
    await store.append("run-1", _make_event(run_id="run-1"))
    await store.append("run-2", _make_event(run_id="run-2"))

    run1_events = await store.list_events("run-1")
    run2_events = await store.list_events("run-2")

    assert len(run1_events) == 2
    assert len(run2_events) == 1
    assert await store.count_events("run-1") == 2
    assert await store.count_events("run-2") == 1
