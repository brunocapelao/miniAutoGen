"""Tests for CheckpointManager coordinated state transitions."""

from __future__ import annotations

import pytest

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.runtime.checkpoint_manager import CheckpointManager
from miniautogen.stores.in_memory_checkpoint_store import InMemoryCheckpointStore
from miniautogen.stores.in_memory_event_store import InMemoryEventStore

pytestmark = pytest.mark.anyio


@pytest.fixture
def checkpoint_store() -> InMemoryCheckpointStore:
    return InMemoryCheckpointStore()


@pytest.fixture
def event_store() -> InMemoryEventStore:
    return InMemoryEventStore()


@pytest.fixture
def event_sink() -> InMemoryEventSink:
    return InMemoryEventSink()


@pytest.fixture
def manager(
    checkpoint_store: InMemoryCheckpointStore,
    event_store: InMemoryEventStore,
    event_sink: InMemoryEventSink,
) -> CheckpointManager:
    return CheckpointManager(checkpoint_store, event_store, event_sink)


@pytest.fixture
def manager_no_sink(
    checkpoint_store: InMemoryCheckpointStore,
    event_store: InMemoryEventStore,
) -> CheckpointManager:
    return CheckpointManager(checkpoint_store, event_store)


async def test_atomic_transition_saves_checkpoint_and_events(
    manager: CheckpointManager,
    checkpoint_store: InMemoryCheckpointStore,
    event_store: InMemoryEventStore,
) -> None:
    """atomic_transition persists both checkpoint and events."""
    events = [
        ExecutionEvent(type="step_started", run_id="run-1"),
        ExecutionEvent(type="step_finished", run_id="run-1"),
    ]
    await manager.atomic_transition(
        "run-1", new_state={"result": 42}, events=events, step_index=0
    )

    cp = await checkpoint_store.get_checkpoint("run-1")
    assert cp is not None
    assert cp["state"] == {"result": 42}
    assert cp["step_index"] == 0

    stored = await event_store.list_events("run-1")
    assert len(stored) == 2
    assert stored[0].type == "step_started"
    assert stored[1].type == "step_finished"


async def test_atomic_transition_publishes_to_sink(
    manager: CheckpointManager,
    event_sink: InMemoryEventSink,
) -> None:
    """atomic_transition publishes events to the live event sink."""
    events = [ExecutionEvent(type="step_done", run_id="run-2")]
    await manager.atomic_transition(
        "run-2", new_state={"x": 1}, events=events, step_index=1
    )

    assert len(event_sink.events) == 1
    assert event_sink.events[0].type == "step_done"


async def test_atomic_transition_works_without_sink(
    manager_no_sink: CheckpointManager,
) -> None:
    """atomic_transition works when no event_sink is provided."""
    events = [ExecutionEvent(type="step_done", run_id="run-3")]
    # Should not raise
    await manager_no_sink.atomic_transition(
        "run-3", new_state={"y": 2}, events=events, step_index=0
    )


async def test_get_last_checkpoint_roundtrip(
    manager: CheckpointManager,
) -> None:
    """get_last_checkpoint returns (state, step_index) after a transition."""
    await manager.atomic_transition(
        "run-4", new_state={"val": "hello"}, events=[], step_index=3
    )

    result = await manager.get_last_checkpoint("run-4")
    assert result is not None
    state, step_index = result
    assert state == {"val": "hello"}
    assert step_index == 3


async def test_get_last_checkpoint_returns_none_when_missing(
    manager: CheckpointManager,
) -> None:
    """get_last_checkpoint returns None for unknown run_id."""
    result = await manager.get_last_checkpoint("nonexistent")
    assert result is None


async def test_get_events_after_transition(
    manager: CheckpointManager,
) -> None:
    """Events are retrievable after atomic_transition."""
    events_batch1 = [ExecutionEvent(type="ev1", run_id="run-5")]
    events_batch2 = [ExecutionEvent(type="ev2", run_id="run-5")]

    await manager.atomic_transition(
        "run-5", new_state={"s": 1}, events=events_batch1, step_index=0
    )
    await manager.atomic_transition(
        "run-5", new_state={"s": 2}, events=events_batch2, step_index=1
    )

    all_events = await manager.get_events("run-5")
    assert len(all_events) == 2

    after_first = await manager.get_events("run-5", after_index=1)
    assert len(after_first) == 1
    assert after_first[0].type == "ev2"


async def test_step_index_tracked_across_transitions(
    manager: CheckpointManager,
) -> None:
    """step_index updates correctly across multiple transitions."""
    for i in range(3):
        await manager.atomic_transition(
            "run-6", new_state={"step": i}, events=[], step_index=i
        )

    result = await manager.get_last_checkpoint("run-6")
    assert result is not None
    state, step_index = result
    assert step_index == 2
    assert state == {"step": 2}
