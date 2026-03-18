"""Comprehensive tests for ExecutionEvent."""

from datetime import datetime

from miniautogen.core.contracts.events import ExecutionEvent


def test_event_creation_minimal() -> None:
    event = ExecutionEvent(type="run_started", run_id="run-1")
    assert event.type == "run_started"
    assert event.run_id == "run-1"
    assert event.correlation_id is None
    assert event.payload == ()


def test_event_creation_full() -> None:
    event = ExecutionEvent(
        type="run_finished",
        run_id="run-1",
        correlation_id="corr-1",
        payload={"status": "completed"},
    )
    assert event.correlation_id == "corr-1"
    assert event.get_payload("status") == "completed"


def test_event_has_timestamp() -> None:
    event = ExecutionEvent(type="test", run_id="r1")
    assert isinstance(event.timestamp, datetime)


def test_event_serialization_roundtrip() -> None:
    event = ExecutionEvent(
        type="run_started",
        run_id="run-1",
        correlation_id="corr-1",
        payload={"key": "value"},
    )
    data = event.model_dump()
    restored = ExecutionEvent.model_validate(data)
    assert restored.type == event.type
    assert restored.run_id == event.run_id
    assert restored.correlation_id == event.correlation_id


def test_event_allows_arbitrary_payload() -> None:
    event = ExecutionEvent(
        type="custom",
        run_id="r1",
        payload={"nested": {"deep": [1, 2, 3]}},
    )
    assert event.get_payload("nested") == {"deep": [1, 2, 3]}


def test_event_with_empty_payload() -> None:
    event = ExecutionEvent(type="test", run_id="r1", payload={})
    assert event.payload == ()
