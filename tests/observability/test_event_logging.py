"""Tests for LoggingEventSink."""

import pytest

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.observability.event_logging import LoggingEventSink


def _make_event(
    event_type: str = "run_started",
    run_id: str = "run-1",
    **payload: object,
) -> ExecutionEvent:
    return ExecutionEvent(
        type=event_type, run_id=run_id, payload=payload
    )


@pytest.mark.anyio
async def test_logging_sink_publishes_without_error() -> None:
    sink = LoggingEventSink()
    await sink.publish(_make_event("run_started"))
    await sink.publish(_make_event("run_failed"))
    await sink.publish(_make_event("stagnation_detected"))
    # No assertion on log output — just verify no exceptions


@pytest.mark.anyio
async def test_logging_sink_async_context_manager() -> None:
    async with LoggingEventSink() as sink:
        await sink.publish(_make_event())


@pytest.mark.anyio
async def test_logging_sink_with_payload() -> None:
    sink = LoggingEventSink()
    await sink.publish(
        _make_event("run_finished", status="completed")
    )
