from enum import Enum


class EventType(str, Enum):
    RUN_STARTED = "run_started"
    RUN_FINISHED = "run_finished"
    RUN_FAILED = "run_failed"
    RUN_CANCELLED = "run_cancelled"
    RUN_TIMED_OUT = "run_timed_out"
    COMPONENT_STARTED = "component_started"
    COMPONENT_FINISHED = "component_finished"
    COMPONENT_SKIPPED = "component_skipped"
    COMPONENT_RETRIED = "component_retried"
    TOOL_INVOKED = "tool_invoked"
    TOOL_SUCCEEDED = "tool_succeeded"
    TOOL_FAILED = "tool_failed"
    CHECKPOINT_SAVED = "checkpoint_saved"
    CHECKPOINT_RESTORED = "checkpoint_restored"
    ADAPTER_FAILED = "adapter_failed"
    VALIDATION_FAILED = "validation_failed"
    POLICY_APPLIED = "policy_applied"
    BUDGET_EXCEEDED = "budget_exceeded"

    # Agentic loop events
    AGENTIC_LOOP_STARTED = "agentic_loop_started"
    ROUTER_DECISION = "router_decision"
    AGENT_REPLIED = "agent_replied"
    AGENTIC_LOOP_STOPPED = "agentic_loop_stopped"
    STAGNATION_DETECTED = "stagnation_detected"

    # Backend driver events
    BACKEND_SESSION_STARTED = "backend_session_started"
    BACKEND_TURN_STARTED = "backend_turn_started"
    BACKEND_MESSAGE_DELTA = "backend_message_delta"
    BACKEND_MESSAGE_COMPLETED = "backend_message_completed"
    BACKEND_TOOL_CALL_REQUESTED = "backend_tool_call_requested"
    BACKEND_TOOL_CALL_EXECUTED = "backend_tool_call_executed"
    BACKEND_ARTIFACT_EMITTED = "backend_artifact_emitted"
    BACKEND_WARNING = "backend_warning"
    BACKEND_ERROR = "backend_error"
    BACKEND_TURN_COMPLETED = "backend_turn_completed"
    BACKEND_SESSION_CLOSED = "backend_session_closed"


AGENTIC_LOOP_EVENT_TYPES = {
    EventType.AGENTIC_LOOP_STARTED.value,
    EventType.ROUTER_DECISION.value,
    EventType.AGENT_REPLIED.value,
    EventType.AGENTIC_LOOP_STOPPED.value,
    EventType.STAGNATION_DETECTED.value,
}

DELIBERATION_EVENT_TYPES = {
    "deliberation_started",
    "deliberation_finished",
    "deliberation_failed",
}

BACKEND_EVENT_TYPES = {
    EventType.BACKEND_SESSION_STARTED.value,
    EventType.BACKEND_TURN_STARTED.value,
    EventType.BACKEND_MESSAGE_DELTA.value,
    EventType.BACKEND_MESSAGE_COMPLETED.value,
    EventType.BACKEND_TOOL_CALL_REQUESTED.value,
    EventType.BACKEND_TOOL_CALL_EXECUTED.value,
    EventType.BACKEND_ARTIFACT_EMITTED.value,
    EventType.BACKEND_WARNING.value,
    EventType.BACKEND_ERROR.value,
    EventType.BACKEND_TURN_COMPLETED.value,
    EventType.BACKEND_SESSION_CLOSED.value,
}
