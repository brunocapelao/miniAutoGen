import anyio
import pytest

from miniautogen.core.events import EventType, InMemoryEventSink
from miniautogen.core.runtime import PipelineRunner
from miniautogen.policies import ExecutionPolicy
from miniautogen.stores import InMemoryRunStore


class SlowPipeline:
    async def run(self, state):
        await anyio.sleep(0.2)
        return state


class FastPipeline:
    async def run(self, state):
        await anyio.sleep(0)
        return {"ok": True}


class FailingPipeline:
    async def run(self, state):
        raise ValueError("boom")


@pytest.mark.asyncio
async def test_runner_marks_timed_out_runs_and_publishes_timeout_event() -> None:
    sink = InMemoryEventSink()
    run_store = InMemoryRunStore()
    runner = PipelineRunner(
        event_sink=sink,
        run_store=run_store,
        execution_policy=ExecutionPolicy(timeout_seconds=0.01),
    )

    with pytest.raises(TimeoutError):
        await runner.run_pipeline(SlowPipeline(), {})

    assert runner.last_run_id is not None
    assert await run_store.get_run(runner.last_run_id) == {
        "status": "timed_out",
        "correlation_id": sink.events[0].correlation_id,
    }
    assert sink.events[-1].type == EventType.RUN_TIMED_OUT.value


@pytest.mark.asyncio
async def test_runner_finishes_successfully_when_timeout_is_configured_but_not_hit() -> None:
    sink = InMemoryEventSink()
    run_store = InMemoryRunStore()
    runner = PipelineRunner(
        event_sink=sink,
        run_store=run_store,
        execution_policy=ExecutionPolicy(timeout_seconds=1),
    )

    result = await runner.run_pipeline(FastPipeline(), {})

    assert result == {"ok": True}
    assert runner.last_run_id is not None
    assert await run_store.get_run(runner.last_run_id) == {
        "status": "finished",
        "correlation_id": sink.events[0].correlation_id,
    }
    assert sink.events[-1].type == EventType.RUN_FINISHED.value


@pytest.mark.asyncio
async def test_runner_marks_failed_runs_and_publishes_failure_event() -> None:
    sink = InMemoryEventSink()
    run_store = InMemoryRunStore()
    runner = PipelineRunner(event_sink=sink, run_store=run_store)

    with pytest.raises(ValueError, match="boom"):
        await runner.run_pipeline(FailingPipeline(), {})

    assert runner.last_run_id is not None
    assert await run_store.get_run(runner.last_run_id) == {
        "status": "failed",
        "correlation_id": sink.events[0].correlation_id,
        "error_type": "ValueError",
    }
    assert sink.events[-1].type == EventType.RUN_FAILED.value
