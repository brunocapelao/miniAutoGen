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

    # Deliberation events
    DELIBERATION_STARTED = "deliberation_started"
    DELIBERATION_ROUND_COMPLETED = "deliberation_round_completed"
    DELIBERATION_FINISHED = "deliberation_finished"
    DELIBERATION_FAILED = "deliberation_failed"

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

    # Approval lifecycle
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    APPROVAL_TIMEOUT = "approval_timeout"

    # Effect engine events (Phase 2)
    EFFECT_REGISTERED = "effect_registered"
    EFFECT_EXECUTED = "effect_executed"
    EFFECT_SKIPPED = "effect_skipped"
    EFFECT_FAILED = "effect_failed"
    EFFECT_DENIED = "effect_denied"
    EFFECT_STALE_RECLAIMED = "effect_stale_reclaimed"
    EFFECT_UNPROTECTED = "effect_unprotected"

    # Supervision events (Phase 3)
    SUPERVISION_FAILURE_RECEIVED = "supervision_failure_received"
    SUPERVISION_DECISION_MADE = "supervision_decision_made"
    SUPERVISION_RESTART_STARTED = "supervision_restart_started"
    SUPERVISION_CIRCUIT_OPENED = "supervision_circuit_opened"
    SUPERVISION_ESCALATED = "supervision_escalated"
    SUPERVISION_RETRY_SUCCEEDED = "supervision_retry_succeeded"

    # Agent Runtime events (Phase B)
    AGENT_TURN_STARTED = "agent_turn_started"
    AGENT_TURN_COMPLETED = "agent_turn_completed"
    AGENT_HOOK_EXECUTED = "agent_hook_executed"
    AGENT_TOOL_INVOKED = "agent_tool_invoked"

    # RuntimeInterceptor events (Phase B)
    INTERCEPTOR_BEFORE_STEP = "interceptor_before_step"
    INTERCEPTOR_AFTER_STEP = "interceptor_after_step"
    INTERCEPTOR_BAIL = "interceptor_bail"

    # Run state machine events
    RUN_STATE_CHANGED = "run_state_changed"


APPROVAL_EVENT_TYPES: set[EventType] = {
    EventType.APPROVAL_REQUESTED,
    EventType.APPROVAL_GRANTED,
    EventType.APPROVAL_DENIED,
    EventType.APPROVAL_TIMEOUT,
}

AGENTIC_LOOP_EVENT_TYPES: set[EventType] = {
    EventType.AGENTIC_LOOP_STARTED,
    EventType.ROUTER_DECISION,
    EventType.AGENT_REPLIED,
    EventType.AGENTIC_LOOP_STOPPED,
    EventType.STAGNATION_DETECTED,
}

DELIBERATION_EVENT_TYPES: set[EventType] = {
    EventType.DELIBERATION_STARTED,
    EventType.DELIBERATION_ROUND_COMPLETED,
    EventType.DELIBERATION_FINISHED,
    EventType.DELIBERATION_FAILED,
}

BACKEND_EVENT_TYPES: set[EventType] = {
    EventType.BACKEND_SESSION_STARTED,
    EventType.BACKEND_TURN_STARTED,
    EventType.BACKEND_MESSAGE_DELTA,
    EventType.BACKEND_MESSAGE_COMPLETED,
    EventType.BACKEND_TOOL_CALL_REQUESTED,
    EventType.BACKEND_TOOL_CALL_EXECUTED,
    EventType.BACKEND_ARTIFACT_EMITTED,
    EventType.BACKEND_WARNING,
    EventType.BACKEND_ERROR,
    EventType.BACKEND_TURN_COMPLETED,
    EventType.BACKEND_SESSION_CLOSED,
}

EFFECT_EVENT_TYPES: set[EventType] = {
    EventType.EFFECT_REGISTERED,
    EventType.EFFECT_EXECUTED,
    EventType.EFFECT_SKIPPED,
    EventType.EFFECT_FAILED,
    EventType.EFFECT_DENIED,
    EventType.EFFECT_STALE_RECLAIMED,
    EventType.EFFECT_UNPROTECTED,
}

SUPERVISION_EVENT_TYPES: set[EventType] = {
    EventType.SUPERVISION_FAILURE_RECEIVED,
    EventType.SUPERVISION_DECISION_MADE,
    EventType.SUPERVISION_RESTART_STARTED,
    EventType.SUPERVISION_CIRCUIT_OPENED,
    EventType.SUPERVISION_ESCALATED,
    EventType.SUPERVISION_RETRY_SUCCEEDED,
}

AGENT_RUNTIME_EVENT_TYPES: set[EventType] = {
    EventType.AGENT_TURN_STARTED,
    EventType.AGENT_TURN_COMPLETED,
    EventType.AGENT_HOOK_EXECUTED,
    EventType.AGENT_TOOL_INVOKED,
}

INTERCEPTOR_EVENT_TYPES: set[EventType] = {
    EventType.INTERCEPTOR_BEFORE_STEP,
    EventType.INTERCEPTOR_AFTER_STEP,
    EventType.INTERCEPTOR_BAIL,
}
