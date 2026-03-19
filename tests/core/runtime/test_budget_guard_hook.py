"""Tests for BudgetGuardHook -- aborts if budget exceeded."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from miniautogen.core.contracts.agent_hook import AgentHook
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.runtime.agent_hooks import BudgetGuardHook
from miniautogen.policies.budget import BudgetExceededError, BudgetPolicy, BudgetTracker


def _make_context() -> RunContext:
    return RunContext(
        run_id="run-1",
        started_at=datetime.now(timezone.utc),
        correlation_id="corr-1",
    )


def test_budget_guard_hook_satisfies_protocol() -> None:
    tracker = BudgetTracker(policy=BudgetPolicy(max_cost=10.0))
    hook = BudgetGuardHook(tracker=tracker)
    assert isinstance(hook, AgentHook)


@pytest.mark.anyio
async def test_budget_guard_passes_when_within_budget() -> None:
    tracker = BudgetTracker(policy=BudgetPolicy(max_cost=10.0))
    hook = BudgetGuardHook(tracker=tracker)
    messages = [{"role": "user", "content": "hello"}]
    ctx = _make_context()

    result = await hook.before_turn(messages, ctx)
    assert result == messages


@pytest.mark.anyio
async def test_budget_guard_raises_when_budget_exceeded() -> None:
    tracker = BudgetTracker(policy=BudgetPolicy(max_cost=1.0))
    # record() raises BudgetExceededError when exceeding; catch it
    # so we can test that before_turn also raises on check()
    with pytest.raises(BudgetExceededError):
        tracker.record(1.5)

    # Now the tracker is over budget; before_turn should raise
    hook = BudgetGuardHook(tracker=tracker)
    messages = [{"role": "user", "content": "hello"}]
    ctx = _make_context()

    with pytest.raises(BudgetExceededError):
        await hook.before_turn(messages, ctx)


@pytest.mark.anyio
async def test_budget_guard_after_event_is_passthrough() -> None:
    from miniautogen.core.contracts.events import ExecutionEvent

    tracker = BudgetTracker(policy=BudgetPolicy(max_cost=10.0))
    hook = BudgetGuardHook(tracker=tracker)
    event = ExecutionEvent(type="test_event")
    ctx = _make_context()

    result = await hook.after_event(event, ctx)
    assert result.type == "test_event"


@pytest.mark.anyio
async def test_budget_guard_on_error_propagates() -> None:
    tracker = BudgetTracker(policy=BudgetPolicy(max_cost=10.0))
    hook = BudgetGuardHook(tracker=tracker)
    ctx = _make_context()

    result = await hook.on_error(RuntimeError("test"), ctx)
    assert result is None


@pytest.mark.anyio
async def test_budget_guard_passes_when_no_limit() -> None:
    tracker = BudgetTracker(policy=BudgetPolicy(max_cost=None))
    hook = BudgetGuardHook(tracker=tracker)
    messages = [{"role": "user", "content": "hello"}]
    ctx = _make_context()

    result = await hook.before_turn(messages, ctx)
    assert result == messages
