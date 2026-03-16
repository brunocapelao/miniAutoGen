"""Tests for RunStatus and LoopStopReason enums."""

from miniautogen.core.contracts.enums import LoopStopReason, RunStatus


def test_run_status_values() -> None:
    """RunStatus enum has the expected string values."""
    assert RunStatus.FINISHED == "finished"
    assert RunStatus.FAILED == "failed"
    assert RunStatus.CANCELLED == "cancelled"
    assert RunStatus.TIMED_OUT == "timed_out"


def test_loop_stop_reason_values() -> None:
    """LoopStopReason enum has the expected string values."""
    assert LoopStopReason.MAX_TURNS == "max_turns"
    assert LoopStopReason.ROUTER_TERMINATED == "router_terminated"
    assert LoopStopReason.STAGNATION == "stagnation"
    assert LoopStopReason.TIMEOUT == "timeout"


def test_run_status_is_str_enum() -> None:
    """RunStatus values are usable as plain strings (str Enum)."""
    status: str = RunStatus.FINISHED
    assert status == "finished"
    assert isinstance(status, str)


def test_loop_stop_reason_is_str_enum() -> None:
    """LoopStopReason values are usable as plain strings (str Enum)."""
    reason: str = LoopStopReason.MAX_TURNS
    assert reason == "max_turns"
    assert isinstance(reason, str)
