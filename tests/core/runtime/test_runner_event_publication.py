import pytest

from miniautogen.core.events import EventType, InMemoryEventSink
from miniautogen.core.runtime import PipelineRunner


class DummyPipeline:
    async def run(self, state):
        return state


@pytest.mark.asyncio
async def test_pipeline_runner_publishes_run_start_and_finish_events() -> None:
    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)

    result = await runner.run_pipeline(DummyPipeline(), {"ok": True})

    assert result == {"ok": True}
    assert [event.type for event in sink.events] == [
        EventType.RUN_STARTED.value,
        EventType.RUN_FINISHED.value,
    ]
    assert sink.events[0].run_id
    assert sink.events[0].correlation_id
