from datetime import UTC, datetime

from miniautogen.core.contracts.events import ExecutionEvent


def test_execution_event_contains_type_and_correlation():
    event = ExecutionEvent(
        event_type="run_started",
        created_at=datetime.now(UTC),
        correlation_id="corr-1",
        payload={"run_id": "run-1"},
    )

    assert event.event_type == "run_started"
    assert event.correlation_id == "corr-1"
