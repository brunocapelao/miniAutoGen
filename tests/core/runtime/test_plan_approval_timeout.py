"""Tests for plan approval timeout — lead never responds."""

from __future__ import annotations

import anyio
import pytest

from miniautogen.core.contracts.team_message import MailMessage
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.runtime.team_mailbox import InMemoryMailboxStore
from miniautogen.core.runtime.team_plan_approval import PlanApprovalRegistry


@pytest.mark.anyio
async def test_timeout_when_lead_never_responds() -> None:
    sink = InMemoryEventSink()
    mailbox = InMemoryMailboxStore(
        agents=["teammate", "lead"],
        team_run_id="test-timeout",
        event_sink=sink,
    )
    approvals = PlanApprovalRegistry(event_sink=sink, team_run_id="test-timeout")
    timeout_seconds = 0.2

    start = anyio.current_time()
    corr_id = await approvals.register("teammate", "lead", timeout_seconds)
    await mailbox.send(MailMessage(
        id="timeout-req",
        from_agent="teammate", to_agent="lead",
        content="risky operation", kind="plan_approval_request",
        correlation_id=corr_id,
    ))

    with anyio.fail_after(timeout_seconds + 0.5):
        decision, reason = await approvals.wait(corr_id)
    elapsed = anyio.current_time() - start

    assert decision == "timeout"
    assert elapsed >= timeout_seconds - 0.05
    assert elapsed <= timeout_seconds + 0.3


@pytest.mark.anyio
async def test_resolve_is_idempotent_after_timeout() -> None:
    sink = InMemoryEventSink()
    mailbox = InMemoryMailboxStore(
        agents=["A", "lead"],
        team_run_id="test-idempotent",
        event_sink=sink,
    )
    approvals = PlanApprovalRegistry(event_sink=sink, team_run_id="test-idempotent")

    corr_id = await approvals.register("A", "lead", 0.1)
    with anyio.fail_after(0.5):
        decision, _ = await approvals.wait(corr_id)

    assert decision == "timeout"

    await approvals.resolve(corr_id, "granted", reason="late")
    decision2, reason2 = await approvals.wait(corr_id)
    assert decision2 == "timeout"
