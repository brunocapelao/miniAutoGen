import anyio
import pytest

from miniautogen.core.events import InMemoryEventSink
from miniautogen.core.runtime import PipelineRunner
from miniautogen.stores import InMemoryCheckpointStore, InMemoryRunStore


class RecordingRunStore(InMemoryRunStore):
    def __init__(self) -> None:
        super().__init__()
        self.saved_run_ids: list[str] = []

    async def save_run(self, run_id: str, payload: dict[str, object]) -> None:
        self.saved_run_ids.append(run_id)
        await super().save_run(run_id, payload)


class RecordingCheckpointStore(InMemoryCheckpointStore):
    def __init__(self) -> None:
        super().__init__()
        self.saved_run_ids: list[str] = []

    async def save_checkpoint(self, run_id: str, payload: dict[str, object]) -> None:
        self.saved_run_ids.append(run_id)
        await super().save_checkpoint(run_id, payload)


class SlowPipeline:
    async def run(self, state):
        await anyio.sleep(0.01)
        return {"seen": state["name"]}


@pytest.mark.asyncio
async def test_runner_supports_concurrent_executions_without_run_id_collision() -> None:
    sink = InMemoryEventSink()
    run_store = RecordingRunStore()
    checkpoint_store = RecordingCheckpointStore()
    runner = PipelineRunner(
        event_sink=sink,
        run_store=run_store,
        checkpoint_store=checkpoint_store,
    )

    async def execute(name: str) -> None:
        await runner.run_pipeline(SlowPipeline(), {"name": name})

    async with anyio.create_task_group() as tg:
        tg.start_soon(execute, "one")
        tg.start_soon(execute, "two")

    run_ids = set(run_store.saved_run_ids)
    checkpoint_ids = set(checkpoint_store.saved_run_ids)
    correlation_ids = {event.correlation_id for event in sink.events}
    events_by_correlation = {
        correlation_id: [event for event in sink.events if event.correlation_id == correlation_id]
        for correlation_id in correlation_ids
    }

    assert len(run_ids) == 2
    assert len(checkpoint_ids) == 2
    assert len(correlation_ids) == 2
    assert all(len(events) == 2 for events in events_by_correlation.values())
