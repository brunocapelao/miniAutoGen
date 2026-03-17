"""Bridges execution events to structlog.

Maps event types to appropriate log levels:
- error: RUN_FAILED, RUN_TIMED_OUT, *_FAILED
- warning: STAGNATION_DETECTED, BUDGET_EXCEEDED, VALIDATION_FAILED
- info: everything else (started, finished, completed, etc.)
"""

from __future__ import annotations

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.types import EventType
from miniautogen.observability.logging import get_logger

logger = get_logger(__name__)

_ERROR_TYPES: set[str] = {
    EventType.RUN_FAILED.value,
    EventType.RUN_TIMED_OUT.value,
    EventType.TOOL_FAILED.value,
    EventType.ADAPTER_FAILED.value,
    EventType.DELIBERATION_FAILED.value,
}

_WARNING_TYPES: set[str] = {
    EventType.STAGNATION_DETECTED.value,
    EventType.BUDGET_EXCEEDED.value,
    EventType.VALIDATION_FAILED.value,
}


class LoggingEventSink:
    """EventSink that logs events via structlog.

    Error events are logged at error level, warnings at warning,
    and everything else at info.
    """

    async def publish(self, event: ExecutionEvent) -> None:
        bound = logger.bind(
            event_type=event.type,
            run_id=event.run_id,
            correlation_id=event.correlation_id,
        )
        if event.type in _ERROR_TYPES:
            bound.error("execution_event", **event.payload)
        elif event.type in _WARNING_TYPES:
            bound.warning("execution_event", **event.payload)
        else:
            bound.info("execution_event", **event.payload)

    async def __aenter__(self) -> LoggingEventSink:
        return self

    async def __aexit__(self, *exc: object) -> None:
        pass
