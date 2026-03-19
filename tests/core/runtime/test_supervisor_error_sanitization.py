"""Tests for error message sanitization in StepSupervisor events."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from miniautogen.core.contracts.enums import ErrorCategory, SupervisionStrategy
from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.contracts.supervision import StepSupervision, SupervisionDecision
from miniautogen.core.events.event_sink import EventSink
from miniautogen.core.runtime.supervisors import StepSupervisor


class CapturingEventSink(EventSink):
    """Event sink that captures all published events for inspection."""

    def __init__(self):
        self.events: list[ExecutionEvent] = []

    async def publish(self, event: ExecutionEvent) -> None:
        self.events.append(event)


@pytest.fixture()
def event_sink():
    return CapturingEventSink()


@pytest.fixture()
def supervisor(event_sink):
    return StepSupervisor(event_sink=event_sink)


@pytest.fixture()
def supervision():
    return StepSupervision(
        strategy=SupervisionStrategy.STOP,
        max_restarts=3,
        restart_window_seconds=60.0,
        circuit_breaker_threshold=10,
    )


@pytest.mark.asyncio
async def test_failure_event_does_not_contain_raw_error_message(
    supervisor, event_sink, supervision
):
    """The SUPERVISION_FAILURE_RECEIVED event must NOT contain str(error).

    It should only contain type(error).__name__ to prevent leaking
    sensitive information like file paths, credentials, or SQL queries.
    """
    sensitive_error = ValueError("database password is s3cr3t! at /etc/db.conf")

    await supervisor.handle_failure(
        child_id="step-1",
        error=sensitive_error,
        error_category=ErrorCategory.TRANSIENT,
        supervision=supervision,
        restart_count=0,
    )

    # Find the SUPERVISION_FAILURE_RECEIVED event
    failure_events = [
        e for e in event_sink.events
        if e.type == "supervision_failure_received"
    ]
    assert len(failure_events) == 1

    payload = failure_events[0].payload_dict()
    assert payload["exception_type"] == "ValueError"
    # The raw error message must NOT appear in the payload
    assert "s3cr3t" not in str(payload)
    assert "db.conf" not in str(payload)
    # The 'message' field should only contain the exception type name
    assert payload["message"] == "ValueError"
