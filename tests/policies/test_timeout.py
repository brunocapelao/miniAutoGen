"""Tests for TimeoutScope."""

import pytest

from miniautogen.policies.timeout import TimeoutScope


def test_timeout_scope_defaults() -> None:
    scope = TimeoutScope()
    assert scope.pipeline_seconds is None
    assert scope.turn_seconds is None
    assert scope.tool_seconds is None


def test_timeout_scope_valid_hierarchy() -> None:
    scope = TimeoutScope(
        pipeline_seconds=120.0,
        turn_seconds=60.0,
        tool_seconds=30.0,
    )
    assert scope.pipeline_seconds == 120.0


def test_timeout_scope_rejects_turn_gte_pipeline() -> None:
    with pytest.raises(ValueError, match="turn_seconds"):
        TimeoutScope(pipeline_seconds=60.0, turn_seconds=60.0)


def test_timeout_scope_rejects_tool_gte_turn() -> None:
    with pytest.raises(ValueError, match="tool_seconds"):
        TimeoutScope(turn_seconds=30.0, tool_seconds=30.0)


def test_timeout_scope_partial_hierarchy() -> None:
    scope = TimeoutScope(pipeline_seconds=120.0, tool_seconds=30.0)
    assert scope.turn_seconds is None  # no constraint


def test_timeout_scope_rejects_tool_gte_pipeline_no_turn() -> None:
    with pytest.raises(ValueError, match="tool_seconds"):
        TimeoutScope(pipeline_seconds=60.0, tool_seconds=90.0)
