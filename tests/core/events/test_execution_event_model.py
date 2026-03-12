from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.types import EventType


def test_execution_event_supports_canonical_fields() -> None:
    event = ExecutionEvent(
        type=EventType.RUN_STARTED.value,
        run_id="run-1",
        correlation_id="corr-1",
        scope="runner",
        payload={"step": "start"},
    )

    assert event.type == EventType.RUN_STARTED.value
    assert event.event_type == EventType.RUN_STARTED.value
    assert event.run_id == "run-1"
    assert event.scope == "runner"


def test_execution_event_accepts_legacy_aliases() -> None:
    event = ExecutionEvent(
        event_type="run_started",
        correlation_id="corr-1",
        payload={"run_id": "run-1"},
    )

    assert event.type == "run_started"
    assert event.run_id == "run-1"
