"""Tests for RunContext parent_run_id field.

Spec 015 requires RunContext to carry an optional parent_run_id
for tracing nested executions (team -> teammate, composite, sub-agents).
"""

from __future__ import annotations

from datetime import datetime, timezone

from miniautogen.core.contracts.run_context import RunContext


def test_parent_run_id_optional() -> None:
    """parent_run_id must be Optional[str] with default None."""
    ctx = RunContext(
        run_id="run-1",
        started_at=datetime.now(timezone.utc),
        correlation_id="corr-1",
    )
    assert ctx.parent_run_id is None


def test_parent_run_id_set_and_serialize() -> None:
    """Setting parent_run_id must work and survive model_dump."""
    ctx = RunContext(
        run_id="child-run",
        started_at=datetime.now(timezone.utc),
        correlation_id="corr-1",
        parent_run_id="parent-run",
    )
    assert ctx.parent_run_id == "parent-run"
    dumped = ctx.model_dump(mode="json")
    assert dumped["parent_run_id"] == "parent-run"


def test_parent_run_id_allowed_in_model_copy() -> None:
    """model_copy must allow updating parent_run_id."""
    ctx = RunContext(
        run_id="run-1",
        started_at=datetime.now(timezone.utc),
        correlation_id="corr-1",
    )
    child = ctx.model_copy(update={"parent_run_id": "parent-run"})
    assert child.parent_run_id == "parent-run"
    # Original must be unchanged
    assert ctx.parent_run_id is None


def test_parent_run_id_not_in_disallowed_fields() -> None:
    """parent_run_id must be explicitly allowed for update."""
    ctx = RunContext(
        run_id="run-1",
        started_at=datetime.now(timezone.utc),
        correlation_id="corr-1",
    )
    # This should work without raising
    child = ctx.model_copy(update={"parent_run_id": "parent-x"})
    assert child.parent_run_id == "parent-x"
