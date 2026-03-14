import pytest

from miniautogen.core.events import EventType, InMemoryEventSink
from miniautogen.core.runtime import PipelineRunner
from miniautogen.stores import InMemoryCheckpointStore, InMemoryRunStore


class SuccessfulPipeline:
    async def run(self, state):
        return {"ok": True}


class BrokenRunStore(InMemoryRunStore):
    async def save_run(self, run_id: str, payload: dict[str, object]) -> None:
        if payload.get("status") == "finished":
            raise RuntimeError("run-store-write-failed")
        await super().save_run(run_id, payload)


class BrokenCheckpointStore(InMemoryCheckpointStore):
    async def save_checkpoint(self, run_id: str, payload: dict[str, object]) -> None:
        raise RuntimeError("checkpoint-store-write-failed")


@pytest.mark.asyncio
async def test_runner_marks_failed_when_run_store_terminal_write_fails() -> None:
    sink = InMemoryEventSink()
    run_store = BrokenRunStore()
    runner = PipelineRunner(event_sink=sink, run_store=run_store)

    with pytest.raises(RuntimeError, match="run-store-write-failed"):
        await runner.run_pipeline(SuccessfulPipeline(), {})

    assert runner.last_run_id is not None
    assert await run_store.get_run(runner.last_run_id) == {
        "status": "failed",
        "correlation_id": sink.events[0].correlation_id,
        "error_type": "RuntimeError",
    }
    assert sink.events[-1].type == EventType.RUN_FAILED.value


@pytest.mark.asyncio
async def test_runner_marks_failed_when_checkpoint_write_fails() -> None:
    sink = InMemoryEventSink()
    run_store = InMemoryRunStore()
    checkpoint_store = BrokenCheckpointStore()
    runner = PipelineRunner(
        event_sink=sink,
        run_store=run_store,
        checkpoint_store=checkpoint_store,
    )

    with pytest.raises(RuntimeError, match="checkpoint-store-write-failed"):
        await runner.run_pipeline(SuccessfulPipeline(), {})

    assert runner.last_run_id is not None
    assert await run_store.get_run(runner.last_run_id) == {
        "status": "failed",
        "correlation_id": sink.events[0].correlation_id,
        "error_type": "RuntimeError",
    }
    assert sink.events[-1].type == EventType.RUN_FAILED.value
