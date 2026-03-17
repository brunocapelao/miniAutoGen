"""Cross-module integration tests for the SDK.

Tests that verify components work together correctly:
PipelineRunner + EventSink + Policies + Stores.
"""

import anyio
import pytest

from miniautogen.core.events.event_sink import (
    CompositeEventSink,
    FilteredEventSink,
    InMemoryEventSink,
)
from miniautogen.core.events.filters import TypeFilter
from miniautogen.core.events.types import EventType
from miniautogen.core.runtime.pipeline_runner import PipelineRunner
from miniautogen.core.runtime.recovery import SessionRecovery
from miniautogen.policies.execution import ExecutionPolicy
from miniautogen.stores.in_memory_checkpoint_store import (
    InMemoryCheckpointStore,
)
from miniautogen.stores.in_memory_run_store import InMemoryRunStore


class _SimplePipeline:
    async def run(self, state):  # noqa: ANN001, ANN201
        return {**state, "completed": True}


class _FailingPipeline:
    async def run(self, state):  # noqa: ANN001, ANN201
        msg = "intentional failure"
        raise ValueError(msg)


class _SlowPipeline:
    async def run(self, state):  # noqa: ANN001, ANN201
        await anyio.sleep(10)
        return state


# --- Pipeline + Events + Stores ---


@pytest.mark.anyio
async def test_full_execution_with_events_and_stores() -> None:
    """Pipeline execution persists to stores and emits events."""
    event_sink = InMemoryEventSink()
    run_store = InMemoryRunStore()
    checkpoint_store = InMemoryCheckpointStore()

    runner = PipelineRunner(
        event_sink=event_sink,
        run_store=run_store,
        checkpoint_store=checkpoint_store,
    )

    result = await runner.run_pipeline(
        _SimplePipeline(), {"input": 42},
    )

    # Result correct
    assert result["completed"] is True
    assert result["input"] == 42

    # Events emitted
    types = [e.type for e in event_sink.events]
    assert "run_started" in types
    assert "run_finished" in types

    # Run persisted
    runs = await run_store.list_runs()
    assert len(runs) >= 1

    # Checkpoint saved
    checkpoints = await checkpoint_store.list_checkpoints()
    assert len(checkpoints) >= 1


@pytest.mark.anyio
async def test_failed_execution_persists_error_state() -> None:
    """Failed pipeline persists error state to run store."""
    event_sink = InMemoryEventSink()
    run_store = InMemoryRunStore()

    runner = PipelineRunner(
        event_sink=event_sink,
        run_store=run_store,
    )

    with pytest.raises(ValueError):
        await runner.run_pipeline(_FailingPipeline(), {})

    types = [e.type for e in event_sink.events]
    assert "run_started" in types
    assert "run_failed" in types


# --- Composite EventSink ---


@pytest.mark.anyio
async def test_composite_sink_receives_all_events() -> None:
    """Multiple sinks receive the same events."""
    sink1 = InMemoryEventSink()
    sink2 = InMemoryEventSink()
    composite = CompositeEventSink([sink1, sink2])

    runner = PipelineRunner(event_sink=composite)
    await runner.run_pipeline(_SimplePipeline(), {})

    assert len(sink1.events) == len(sink2.events)
    assert len(sink1.events) >= 2


# --- Filtered EventSink ---


@pytest.mark.anyio
async def test_filtered_sink_captures_only_matching() -> None:
    """FilteredEventSink only captures matching events."""
    all_sink = InMemoryEventSink()
    started_sink = InMemoryEventSink()
    filtered = FilteredEventSink(
        started_sink,
        TypeFilter({EventType.RUN_STARTED}),
    )
    composite = CompositeEventSink([all_sink, filtered])

    runner = PipelineRunner(event_sink=composite)
    await runner.run_pipeline(_SimplePipeline(), {})

    assert len(all_sink.events) >= 2
    assert len(started_sink.events) == 1
    assert started_sink.events[0].type == "run_started"


# --- Timeout + Events ---


@pytest.mark.anyio
async def test_timeout_emits_timed_out_event() -> None:
    """Timeout produces RUN_TIMED_OUT event."""
    sink = InMemoryEventSink()
    policy = ExecutionPolicy(timeout_seconds=0.1)
    runner = PipelineRunner(
        event_sink=sink,
        execution_policy=policy,
    )

    with pytest.raises(TimeoutError):
        await runner.run_pipeline(_SlowPipeline(), {})

    types = [e.type for e in sink.events]
    assert "run_timed_out" in types


# --- Multiple Sequential Runs ---


@pytest.mark.anyio
async def test_sequential_runs_isolated() -> None:
    """Multiple runs have distinct run_ids and events."""
    sink = InMemoryEventSink()
    store = InMemoryRunStore()
    runner = PipelineRunner(event_sink=sink, run_store=store)

    await runner.run_pipeline(_SimplePipeline(), {"run": 1})
    await runner.run_pipeline(_SimplePipeline(), {"run": 2})

    run_ids = {e.run_id for e in sink.events}
    assert len(run_ids) == 2

    runs = await store.list_runs()
    assert len(runs) >= 2


# --- Recovery Flow ---


@pytest.mark.anyio
async def test_recovery_can_resume_from_checkpoint() -> None:
    """SessionRecovery can load checkpoint from a previous run."""
    cp_store = InMemoryCheckpointStore()
    run_store = InMemoryRunStore()

    # Simulate a completed run that saved checkpoint
    await cp_store.save_checkpoint(
        "run-crashed",
        {"state": {"progress": 50}},
    )
    await run_store.save_run(
        "run-crashed",
        {"status": "failed"},
    )

    recovery = SessionRecovery(cp_store, run_store)

    assert await recovery.can_resume("run-crashed") is True
    checkpoint = await recovery.load_checkpoint("run-crashed")
    assert checkpoint["state"]["progress"] == 50

    await recovery.mark_resumed("run-crashed")
    run = await run_store.get_run("run-crashed")
    assert run["status"] == "resumed"
