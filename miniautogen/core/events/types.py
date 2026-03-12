from enum import Enum


class EventType(str, Enum):
    RUN_STARTED = "run_started"
    RUN_FINISHED = "run_finished"
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
