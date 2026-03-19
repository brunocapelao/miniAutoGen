"""Typed enums replacing magic strings in runtime coordination."""

from enum import Enum


class RunStatus(str, Enum):
    """Terminal status of a coordination run."""

    FINISHED = "finished"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class LoopStopReason(str, Enum):
    """Reason why an agentic loop stopped iterating."""

    MAX_TURNS = "max_turns"
    ROUTER_TERMINATED = "router_terminated"
    STAGNATION = "stagnation"
    TIMEOUT = "timeout"


class ErrorCategory(str, Enum):
    """Canonical error categories for the MiniAutoGen error taxonomy.

    Aligns with the 8 categories defined in CLAUDE.md section 4.2.
    Used by classify_error() and supervision decisions.
    """

    TRANSIENT = "transient"
    PERMANENT = "permanent"
    VALIDATION = "validation"
    TIMEOUT = "timeout"
    CANCELLATION = "cancellation"
    ADAPTER = "adapter"
    CONFIGURATION = "configuration"
    STATE_CONSISTENCY = "state_consistency"


class SupervisionStrategy(str, Enum):
    """Supervision action to take when a step fails.

    Used by StepSupervision configuration and SupervisionDecision results.
    """

    RESTART = "restart"
    RESUME = "resume"
    STOP = "stop"
    ESCALATE = "escalate"
