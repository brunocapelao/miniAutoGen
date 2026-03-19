"""Tests for SQLAlchemyEventStore implementation."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
import pytest_asyncio

from miniautogen.core.contracts.events import ExecutionEvent


def _make_event(
    event_type: str = "component_finished",
    run_id: str | None = "run-1",
    correlation_id: str | None = None,
    scope: str | None = None,
) -> ExecutionEvent:
    return ExecutionEvent(
        type=event_type,
        run_id=run_id,
        timestamp=datetime.now(timezone.utc),
        correlation_id=correlation_id,
        scope=scope,
        payload={"status": "ok"},
    )


@pytest_asyncio.fixture
async def store():
    from miniautogen.stores.sqlalchemy_event_store import SQLAlchemyEventStore

    s = SQLAlchemyEventStore(db_url="sqlite+aiosqlite:///:memory:")
    await s.init_db()
    return s


@pytest.mark.asyncio
async def test_import() -> None:
    from miniautogen.stores.sqlalchemy_event_store import SQLAlchemyEventStore  # noqa: F401


@pytest.mark.asyncio
async def test_is_subclass_of_abc() -> None:
    from miniautogen.stores.event_store import EventStore
    from miniautogen.stores.sqlalchemy_event_store import SQLAlchemyEventStore

    assert issubclass(SQLAlchemyEventStore, EventStore)


@pytest.mark.asyncio
async def test_append_and_list_roundtrip(store) -> None:
    event = _make_event()
    await store.append("run-1", event)
    events = await store.list_events("run-1")

    assert len(events) == 1
    assert events[0].type == "component_finished"
    assert events[0].run_id == "run-1"


@pytest.mark.asyncio
async def test_after_index_filtering(store) -> None:
    await store.append("run-1", _make_event(event_type="run_started"))
    await store.append("run-1", _make_event(event_type="component_finished"))
    await store.append("run-1", _make_event(event_type="run_finished"))

    all_events = await store.list_events("run-1")
    assert len(all_events) == 3

    after_1 = await store.list_events("run-1", after_index=1)
    assert len(after_1) == 2
    assert after_1[0].type == "component_finished"

    after_2 = await store.list_events("run-1", after_index=2)
    assert len(after_2) == 1
    assert after_2[0].type == "run_finished"

    after_3 = await store.list_events("run-1", after_index=3)
    assert len(after_3) == 0


@pytest.mark.asyncio
async def test_count_events(store) -> None:
    await store.append("run-1", _make_event())
    await store.append("run-1", _make_event())
    await store.append("run-1", _make_event())

    assert await store.count_events("run-1") == 3


@pytest.mark.asyncio
async def test_count_events_empty_run(store) -> None:
    assert await store.count_events("nonexistent") == 0


@pytest.mark.asyncio
async def test_list_events_empty_run(store) -> None:
    events = await store.list_events("nonexistent")
    assert events == []


@pytest.mark.asyncio
async def test_multiple_runs_isolated(store) -> None:
    await store.append("run-1", _make_event(run_id="run-1"))
    await store.append("run-1", _make_event(run_id="run-1"))
    await store.append("run-2", _make_event(run_id="run-2"))

    run1_events = await store.list_events("run-1")
    run2_events = await store.list_events("run-2")

    assert len(run1_events) == 2
    assert len(run2_events) == 1
    assert await store.count_events("run-1") == 2
    assert await store.count_events("run-2") == 1


@pytest.mark.asyncio
async def test_preserves_correlation_id_and_scope(store) -> None:
    event = _make_event(correlation_id="corr-123", scope="agent.planner")
    await store.append("run-1", event)

    events = await store.list_events("run-1")
    assert len(events) == 1
    assert events[0].correlation_id == "corr-123"
    assert events[0].scope == "agent.planner"


@pytest.mark.asyncio
async def test_preserves_payload(store) -> None:
    event = ExecutionEvent(
        type="test_event",
        run_id="run-1",
        payload={"key1": "value1", "key2": 42},
    )
    await store.append("run-1", event)

    events = await store.list_events("run-1")
    assert len(events) == 1
    payload = events[0].payload_dict()
    assert payload["key1"] == "value1"
    assert payload["key2"] == 42
