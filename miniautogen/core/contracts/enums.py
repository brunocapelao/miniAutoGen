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
