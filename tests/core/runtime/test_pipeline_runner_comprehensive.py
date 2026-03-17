"""Comprehensive tests for PipelineRunner -- the canonical executor.

Tests cover: basic execution, state propagation, error handling,
event emission lifecycle, store persistence, timeout behavior,
approval integration, and edge cases.
"""

from __future__ import annotations

import pytest

from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.runtime.pipeline_runner import PipelineRunner
from miniautogen.policies.execution import ExecutionPolicy
from miniautogen.stores.in_memory_checkpoint_store import InMemoryCheckpointStore
from miniautogen.stores.in_memory_run_store import InMemoryRunStore

# --- Test Pipelines ---


class _SuccessPipeline:
    async def run(self, state: dict) -> dict:
        return {**state, "status": "done"}


class _FailPipeline:
    async def run(self, state: dict) -> dict:
        msg = "pipeline failed"
        raise RuntimeError(msg)


class _SlowPipeline:
    async def run(self, state: dict) -> dict:
        import anyio

        await anyio.sleep(10)  # Will be cancelled by timeout
        return state


class _StateMutatingPipeline:
    async def run(self, state: dict) -> dict:
        return {**state, "step1": True, "step2": True}


class _NoneReturningPipeline:
    async def run(self, state: dict) -> None:
        return None


# --- Basic Execution ---


@pytest.mark.anyio
async def test_runner_executes_pipeline_and_returns_result() -> None:
    runner = PipelineRunner(event_sink=InMemoryEventSink())
    result = await runner.run_pipeline(_SuccessPipeline(), {"input": 1})
    assert result == {"input": 1, "status": "done"}


@pytest.mark.anyio
async def test_runner_passes_state_to_pipeline() -> None:
    runner = PipelineRunner(event_sink=InMemoryEventSink())
    state = {"key": "value", "nested": {"a": 1}}
    result = await runner.run_pipeline(_StateMutatingPipeline(), state)
    assert result["key"] == "value"
    assert result["step1"] is True
    assert result["step2"] is True


@pytest.mark.anyio
async def test_runner_handles_none_return() -> None:
    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)
    # None return skips checkpoint save but still emits events
    result = await runner.run_pipeline(_NoneReturningPipeline(), {})
    assert result is None


# --- Event Emission ---


@pytest.mark.anyio
async def test_runner_emits_started_and_finished_events() -> None:
    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)
    await runner.run_pipeline(_SuccessPipeline(), {})

    types = [e.type for e in sink.events]
    assert "run_started" in types
    assert "run_finished" in types
    # Started before finished
    started_idx = types.index("run_started")
    finished_idx = types.index("run_finished")
    assert started_idx < finished_idx


@pytest.mark.anyio
async def test_runner_emits_failed_event_on_error() -> None:
    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)
    with pytest.raises(RuntimeError):
        await runner.run_pipeline(_FailPipeline(), {})

    types = [e.type for e in sink.events]
    assert "run_started" in types
    assert "run_failed" in types


@pytest.mark.anyio
async def test_runner_events_have_run_id() -> None:
    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)
    await runner.run_pipeline(_SuccessPipeline(), {})

    run_ids = {e.run_id for e in sink.events}
    assert len(run_ids) == 1  # All events share same run_id
    assert all(rid is not None and len(rid) > 0 for rid in run_ids)


@pytest.mark.anyio
async def test_runner_events_have_correlation_id() -> None:
    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)
    await runner.run_pipeline(_SuccessPipeline(), {})

    for event in sink.events:
        assert event.correlation_id is not None


# --- Error Handling ---


@pytest.mark.anyio
async def test_runner_propagates_runtime_error() -> None:
    runner = PipelineRunner(event_sink=InMemoryEventSink())
    with pytest.raises(RuntimeError, match="pipeline failed"):
        await runner.run_pipeline(_FailPipeline(), {})


@pytest.mark.anyio
async def test_runner_emits_events_even_on_failure() -> None:
    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)
    with pytest.raises(RuntimeError):
        await runner.run_pipeline(_FailPipeline(), {})
    assert len(sink.events) >= 2  # At least started + failed


@pytest.mark.anyio
async def test_runner_failed_event_contains_error_type() -> None:
    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)
    with pytest.raises(RuntimeError):
        await runner.run_pipeline(_FailPipeline(), {})

    failed_events = [e for e in sink.events if e.type == "run_failed"]
    assert len(failed_events) == 1
    assert failed_events[0].payload["error_type"] == "RuntimeError"


# --- Timeout ---


@pytest.mark.anyio
async def test_runner_timeout_cancels_slow_pipeline() -> None:
    sink = InMemoryEventSink()
    policy = ExecutionPolicy(timeout_seconds=0.1)
    runner = PipelineRunner(event_sink=sink, execution_policy=policy)

    with pytest.raises(TimeoutError):
        await runner.run_pipeline(_SlowPipeline(), {})

    types = [e.type for e in sink.events]
    assert "run_timed_out" in types


@pytest.mark.anyio
async def test_runner_timeout_via_run_pipeline_kwarg() -> None:
    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)

    with pytest.raises(TimeoutError):
        await runner.run_pipeline(
            _SlowPipeline(), {}, timeout_seconds=0.1,
        )

    types = [e.type for e in sink.events]
    assert "run_timed_out" in types


@pytest.mark.anyio
async def test_runner_no_timeout_when_policy_none() -> None:
    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)
    result = await runner.run_pipeline(_SuccessPipeline(), {})
    assert result["status"] == "done"
    types = [e.type for e in sink.events]
    assert "run_timed_out" not in types


@pytest.mark.anyio
async def test_runner_timeout_saves_status_to_run_store() -> None:
    sink = InMemoryEventSink()
    store = InMemoryRunStore()
    policy = ExecutionPolicy(timeout_seconds=0.1)
    runner = PipelineRunner(
        event_sink=sink, run_store=store, execution_policy=policy,
    )

    with pytest.raises(TimeoutError):
        await runner.run_pipeline(_SlowPipeline(), {})

    runs = await store.list_runs(status="timed_out")
    assert len(runs) == 1


# --- Store Persistence ---


@pytest.mark.anyio
async def test_runner_saves_to_run_store() -> None:
    sink = InMemoryEventSink()
    store = InMemoryRunStore()
    runner = PipelineRunner(event_sink=sink, run_store=store)
    await runner.run_pipeline(_SuccessPipeline(), {})

    runs = await store.list_runs()
    assert len(runs) >= 1
    assert runs[0]["status"] == "finished"


@pytest.mark.anyio
async def test_runner_saves_to_checkpoint_store() -> None:
    sink = InMemoryEventSink()
    cp_store = InMemoryCheckpointStore()
    runner = PipelineRunner(
        event_sink=sink, checkpoint_store=cp_store,
    )
    await runner.run_pipeline(_SuccessPipeline(), {"input": 42})

    checkpoints = await cp_store.list_checkpoints()
    assert len(checkpoints) >= 1


@pytest.mark.anyio
async def test_runner_checkpoint_contains_result() -> None:
    sink = InMemoryEventSink()
    cp_store = InMemoryCheckpointStore()
    runner = PipelineRunner(
        event_sink=sink, checkpoint_store=cp_store,
    )
    await runner.run_pipeline(_SuccessPipeline(), {"input": 42})

    assert runner.last_run_id is not None
    cp = await cp_store.get_checkpoint(runner.last_run_id)
    assert cp is not None
    assert cp["status"] == "done"
    assert cp["input"] == 42


@pytest.mark.anyio
async def test_runner_works_without_stores() -> None:
    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)
    result = await runner.run_pipeline(_SuccessPipeline(), {})
    assert result is not None


@pytest.mark.anyio
async def test_runner_failed_run_saved_to_store() -> None:
    sink = InMemoryEventSink()
    store = InMemoryRunStore()
    runner = PipelineRunner(event_sink=sink, run_store=store)

    with pytest.raises(RuntimeError):
        await runner.run_pipeline(_FailPipeline(), {})

    runs = await store.list_runs(status="failed")
    assert len(runs) == 1
    assert runs[0]["error_type"] == "RuntimeError"


# --- Multiple Runs ---


@pytest.mark.anyio
async def test_runner_generates_unique_run_ids() -> None:
    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)
    await runner.run_pipeline(_SuccessPipeline(), {})
    await runner.run_pipeline(_SuccessPipeline(), {})

    run_ids = {e.run_id for e in sink.events}
    assert len(run_ids) == 2  # Different run_ids for different runs


@pytest.mark.anyio
async def test_runner_last_run_id_updated_after_each_run() -> None:
    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)

    await runner.run_pipeline(_SuccessPipeline(), {})
    first_id = runner.last_run_id

    await runner.run_pipeline(_SuccessPipeline(), {})
    second_id = runner.last_run_id

    assert first_id is not None
    assert second_id is not None
    assert first_id != second_id


# --- Run ID Extraction ---


@pytest.mark.anyio
async def test_runner_uses_run_id_from_state_dict() -> None:
    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)
    # state is a dict, so getattr won't find run_id; uuid is generated
    await runner.run_pipeline(_SuccessPipeline(), {"data": 1})
    assert runner.last_run_id is not None


# --- Scope ---


@pytest.mark.anyio
async def test_runner_events_have_pipeline_runner_scope() -> None:
    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)
    await runner.run_pipeline(_SuccessPipeline(), {})

    for event in sink.events:
        assert event.scope == "pipeline_runner"


# --- Default Event Sink ---


@pytest.mark.anyio
async def test_runner_works_with_null_event_sink() -> None:
    """Runner uses NullEventSink when no sink is provided."""
    runner = PipelineRunner()
    result = await runner.run_pipeline(_SuccessPipeline(), {"x": 1})
    assert result == {"x": 1, "status": "done"}
