import pytest

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events import EventType, InMemoryEventSink


@pytest.mark.asyncio
async def test_in_memory_event_sink_records_published_events() -> None:
    sink = InMemoryEventSink()
    event = ExecutionEvent(
        type=EventType.RUN_STARTED.value,
        run_id="run-1",
        correlation_id="corr-1",
    )

    await sink.publish(event)

    assert len(sink.events) == 1
    assert sink.events[0].type == EventType.RUN_STARTED.value
