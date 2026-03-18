"""Maps core ExecutionEvents to TUI status updates.

This is the translation layer between the core event vocabulary
(44 EventTypes) and the TUI's 7-state status vocabulary.
"""

from __future__ import annotations

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.types import EventType
from miniautogen.tui.status import AgentStatus

# Mapping tables: EventType value -> AgentStatus

_RUN_STATUS_MAP: dict[str, AgentStatus] = {
    EventType.RUN_STARTED.value: AgentStatus.ACTIVE,
    EventType.RUN_FINISHED.value: AgentStatus.DONE,
    EventType.RUN_FAILED.value: AgentStatus.FAILED,
    EventType.RUN_CANCELLED.value: AgentStatus.CANCELLED,
    EventType.RUN_TIMED_OUT.value: AgentStatus.FAILED,
    EventType.APPROVAL_REQUESTED.value: AgentStatus.WAITING,
    EventType.APPROVAL_GRANTED.value: AgentStatus.ACTIVE,
    EventType.APPROVAL_DENIED.value: AgentStatus.CANCELLED,
    EventType.APPROVAL_TIMEOUT.value: AgentStatus.FAILED,
}

_COMPONENT_STATUS_MAP: dict[str, AgentStatus] = {
    EventType.COMPONENT_STARTED.value: AgentStatus.ACTIVE,
    EventType.COMPONENT_FINISHED.value: AgentStatus.DONE,
    EventType.COMPONENT_SKIPPED.value: AgentStatus.CANCELLED,
    EventType.COMPONENT_RETRIED.value: AgentStatus.WORKING,
}

_AGENT_STATUS_MAP: dict[str, AgentStatus] = {
    EventType.AGENT_REPLIED.value: AgentStatus.DONE,
    EventType.ROUTER_DECISION.value: AgentStatus.ACTIVE,
    EventType.BACKEND_SESSION_STARTED.value: AgentStatus.ACTIVE,
    EventType.BACKEND_TURN_STARTED.value: AgentStatus.ACTIVE,
    EventType.BACKEND_MESSAGE_DELTA.value: AgentStatus.WORKING,
    EventType.BACKEND_MESSAGE_COMPLETED.value: AgentStatus.DONE,
    EventType.BACKEND_TOOL_CALL_REQUESTED.value: AgentStatus.WORKING,
    EventType.BACKEND_TOOL_CALL_EXECUTED.value: AgentStatus.DONE,
    EventType.BACKEND_ERROR.value: AgentStatus.FAILED,
    EventType.BACKEND_TURN_COMPLETED.value: AgentStatus.DONE,
    EventType.BACKEND_SESSION_CLOSED.value: AgentStatus.DONE,
    EventType.TOOL_INVOKED.value: AgentStatus.WORKING,
    EventType.TOOL_SUCCEEDED.value: AgentStatus.DONE,
    EventType.TOOL_FAILED.value: AgentStatus.FAILED,
    EventType.AGENTIC_LOOP_STARTED.value: AgentStatus.ACTIVE,
    EventType.AGENTIC_LOOP_STOPPED.value: AgentStatus.DONE,
    EventType.STAGNATION_DETECTED.value: AgentStatus.FAILED,
    EventType.DELIBERATION_STARTED.value: AgentStatus.ACTIVE,
    EventType.DELIBERATION_ROUND_COMPLETED.value: AgentStatus.WORKING,
    EventType.DELIBERATION_FINISHED.value: AgentStatus.DONE,
    EventType.DELIBERATION_FAILED.value: AgentStatus.FAILED,
}


class EventMapper:
    """Translates core events to TUI status vocabulary."""

    @staticmethod
    def map_run_status(event: ExecutionEvent) -> AgentStatus | None:
        """Map an event to a pipeline-run-level status."""
        return _RUN_STATUS_MAP.get(event.type)

    @staticmethod
    def map_component_status(event: ExecutionEvent) -> AgentStatus | None:
        """Map an event to a component/step-level status."""
        return _COMPONENT_STATUS_MAP.get(event.type)

    @staticmethod
    def map_agent_status(event: ExecutionEvent) -> AgentStatus | None:
        """Map an event to an agent-level status."""
        return _AGENT_STATUS_MAP.get(event.type)

    @staticmethod
    def extract_agent_id(event: ExecutionEvent) -> str | None:
        """Extract the agent_id from an event payload, if present."""
        return event.payload.get("agent_id")
