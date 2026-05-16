"""Tests for graceful cancel checkpoint on SIGINT/timeout."""

import anyio
import pytest

from miniautogen.core.events import InMemoryEventSink
from miniautogen.core.runtime.pipeline_runner import PipelineRunner
from miniautogen.policies.execution import ExecutionPolicy


class _SlowPipeline:
    """Pipeline that simulates multi-step execution."""

    def __init__(self) -> None:
        self.steps_done: list[str] = []

    async def run(self, state: dict) -> dict:
        self.steps_done.append("agent_1")
        state["agent_1_done"] = True
        await anyio.sleep(10)
        self.steps_done.append("agent_2")
        state["agent_2_done"] = True
        await anyio.sleep(10)
        self.steps_done.append("agent_3")
        state["agent_3_done"] = True
        return state


class _SleepForeverPipeline:
    async def run(self, state: dict) -> dict:
        await anyio.sleep(3600)
        return state


class _CancelCheckpointCollector:
    """Collects cancel checkpoint calls for test assertions."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def __call__(self, reason: str, state: dict) -> None:
        self.calls.append((reason, state))


@pytest.mark.asyncio
async def test_cancel_after_first_agent_saves_checkpoint() -> None:
    collector = _CancelCheckpointCollector()
    policy = ExecutionPolicy(
        graceful_save_timeout=5.0,
        on_cancel=collector,
    )
    runner = PipelineRunner(execution_policy=policy)
    pipeline = _SlowPipeline()

    async def _run_and_cancel() -> None:
        async with anyio.create_task_group() as tg:
            tg.start_soon(runner.run_pipeline, pipeline, {})
            await anyio.sleep(0.1)
            tg.cancel_scope.cancel()

    await _run_and_cancel()

    assert len(collector.calls) == 1
    reason, state = collector.calls[0]
    assert reason == "cancelled"
    assert state.get("agent_1_done") is True


@pytest.mark.asyncio
async def test_timeout_emits_run_timed_out_and_checkpoint() -> None:
    event_sink = InMemoryEventSink()
    collector = _CancelCheckpointCollector()
    policy = ExecutionPolicy(
        timeout_seconds=0.1,
        graceful_save_timeout=5.0,
        on_cancel=collector,
    )
    runner = PipelineRunner(event_sink=event_sink, execution_policy=policy)

    with pytest.raises(TimeoutError):
        await runner.run_pipeline(_SleepForeverPipeline(), {})

    assert len(collector.calls) == 1
    reason, _state = collector.calls[0]
    assert reason == "timed_out"

    emitted_types = {e.type for e in event_sink.events}
    assert "run_timed_out" in emitted_types


@pytest.mark.asyncio
async def test_double_cancel_does_not_corrupt() -> None:
    collector = _CancelCheckpointCollector()
    policy = ExecutionPolicy(
        graceful_save_timeout=5.0,
        on_cancel=collector,
    )
    runner = PipelineRunner(execution_policy=policy)
    pipeline = _SlowPipeline()

    async def _run_and_double_cancel() -> None:
        async with anyio.create_task_group() as tg:
            tg.start_soon(runner.run_pipeline, pipeline, {})
            await anyio.sleep(0.1)
            tg.cancel_scope.cancel()
            await anyio.sleep(0.05)
            tg.cancel_scope.cancel()

    await _run_and_double_cancel()

    assert len(collector.calls) == 1


@pytest.mark.asyncio
async def test_no_policy_on_cancel_no_error() -> None:
    policy = ExecutionPolicy(graceful_save_timeout=5.0)
    runner = PipelineRunner(execution_policy=policy)

    async def _run_and_cancel() -> None:
        async with anyio.create_task_group() as tg:
            tg.start_soon(
                runner.run_pipeline, _SleepForeverPipeline(), {}
            )
            await anyio.sleep(0.1)
            tg.cancel_scope.cancel()

    await _run_and_cancel()
