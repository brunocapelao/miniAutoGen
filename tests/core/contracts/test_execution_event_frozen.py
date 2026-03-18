"""Tests for frozen ExecutionEvent with tuple payload."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from miniautogen.core.contracts.events import ExecutionEvent


class TestExecutionEventFrozen:
    def test_attribute_assignment_raises(self) -> None:
        event = ExecutionEvent(type="run_started", run_id="r1")
        with pytest.raises(ValidationError):
            event.run_id = "changed"  # type: ignore[misc]

    def test_payload_attribute_assignment_raises(self) -> None:
        event = ExecutionEvent(type="run_started", run_id="r1")
        with pytest.raises(ValidationError):
            event.payload = ()  # type: ignore[misc]


class TestExecutionEventPayload:
    def test_dict_payload_converted_to_tuple(self) -> None:
        event = ExecutionEvent(
            type="run_started",
            run_id="r1",
            payload={"status": "ok", "count": 3},
        )
        assert isinstance(event.payload, tuple)

    def test_get_payload(self) -> None:
        event = ExecutionEvent(
            type="run_started",
            run_id="r1",
            payload={"status": "ok"},
        )
        assert event.get_payload("status") == "ok"

    def test_get_payload_missing_returns_default(self) -> None:
        event = ExecutionEvent(type="run_started", run_id="r1")
        assert event.get_payload("missing") is None
        assert event.get_payload("missing", "fallback") == "fallback"

    def test_empty_payload(self) -> None:
        event = ExecutionEvent(type="test", run_id="r1", payload={})
        assert event.payload == ()

    def test_empty_payload_default(self) -> None:
        event = ExecutionEvent(type="test", run_id="r1")
        assert event.payload == ()


class TestExecutionEventRunIdInference:
    def test_run_id_inferred_from_dict_payload(self) -> None:
        event = ExecutionEvent(
            type="run_started",
            payload={"run_id": "inferred-1"},
        )
        assert event.run_id == "inferred-1"

    def test_run_id_not_overridden_when_explicit(self) -> None:
        event = ExecutionEvent(
            type="run_started",
            run_id="explicit-1",
            payload={"run_id": "from-payload"},
        )
        assert event.run_id == "explicit-1"

    def test_run_id_not_inferred_from_non_string(self) -> None:
        event = ExecutionEvent(
            type="run_started",
            payload={"run_id": 123},
        )
        assert event.run_id is None


class TestExecutionEventAliases:
    def test_event_type_alias(self) -> None:
        event = ExecutionEvent(event_type="run_started", run_id="r1")
        assert event.type == "run_started"
        assert event.event_type == "run_started"

    def test_created_at_alias(self) -> None:
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        event = ExecutionEvent(type="test", run_id="r1", created_at=ts)
        assert event.timestamp == ts
        assert event.created_at == ts


class TestExecutionEventSerialization:
    def test_round_trip(self) -> None:
        event = ExecutionEvent(
            type="run_started",
            run_id="r1",
            correlation_id="c1",
            payload={"status": "ok", "count": 3},
        )
        dumped = event.model_dump()
        restored = ExecutionEvent.model_validate(dumped)
        assert restored.type == event.type
        assert restored.run_id == event.run_id
        assert restored.get_payload("status") == "ok"
        assert restored.get_payload("count") == 3

    def test_serialized_payload_from_tuple(self) -> None:
        """model_validate accepts the tuple-of-tuples form from model_dump."""
        event = ExecutionEvent(
            type="test",
            run_id="r1",
            payload={"a": 1},
        )
        dumped = event.model_dump()
        # payload in dumped form is a list of pairs
        assert isinstance(dumped["payload"], (list, tuple))
        restored = ExecutionEvent.model_validate(dumped)
        assert restored.get_payload("a") == 1
