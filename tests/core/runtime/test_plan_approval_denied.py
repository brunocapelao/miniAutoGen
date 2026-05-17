"""Tests for plan approval — lead denies approval."""

from __future__ import annotations

import anyio
import pytest

from miniautogen.core.contracts.team_message import MailMessage
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.runtime.team_mailbox import InMemoryMailboxStore
from miniautogen.core.runtime.team_plan_approval import PlanApprovalRegistry


@pytest.mark.anyio
async def test_request_and_deny() -> None:
    sink = InMemoryEventSink()
    mailbox = InMemoryMailboxStore(
        agents=["teammate_x", "lead"],
        team_run_id="test-deny",
        event_sink=sink,
    )
    approvals = PlanApprovalRegistry(event_sink=sink, team_run_id="test-deny")

    async def teammate() -> tuple[str, str | None]:
        corr_id = await approvals.register("teammate_x", "lead", 60.0)
        await mailbox.send(MailMessage(
            id="deny-req-1",
            from_agent="teammate_x", to_agent="lead",
            content="DELETE production", kind="plan_approval_request",
            correlation_id=corr_id,
        ))
        return await approvals.wait(corr_id)

    async def lead() -> None:
        async for msg in mailbox.receive_stream("lead"):
            if msg.kind == "plan_approval_request" and msg.correlation_id:
                await approvals.resolve(
                    msg.correlation_id, "denied", reason="too risky"
                )
                await mailbox.send(MailMessage(
                    id="deny-resp-1",
                    from_agent="lead", to_agent="teammate_x",
                    content="denied", kind="plan_approval_denied",
                    correlation_id=msg.correlation_id,
                ))
            break

    async with anyio.create_task_group() as tg:
        tg.start_soon(lead)
        decision, reason = await teammate()

    assert decision == "denied"
    assert reason == "too risky"


@pytest.mark.anyio
async def test_deny_with_reason_payload() -> None:
    sink = InMemoryEventSink()
    mailbox = InMemoryMailboxStore(
        agents=["A", "lead"],
        team_run_id="test-deny-reason",
        event_sink=sink,
    )
    approvals = PlanApprovalRegistry(event_sink=sink, team_run_id="test-deny-reason")

    async def lead() -> None:
        async for msg in mailbox.receive_stream("lead"):
            if msg.kind == "plan_approval_request" and msg.correlation_id:
                await approvals.resolve(
                    msg.correlation_id, "denied",
                    reason="missing risk assessment"
                )
                await mailbox.send(MailMessage(
                    id="deny-resp-2",
                    from_agent="lead", to_agent="A",
                    content="denied", kind="plan_approval_denied",
                    correlation_id=msg.correlation_id,
                ))
            break

    async with anyio.create_task_group() as tg:
        tg.start_soon(lead)
        corr_id = await approvals.register("A", "lead", 60.0)
        await mailbox.send(MailMessage(
            id="deny-req-2",
            from_agent="A", to_agent="lead",
            content="schema change", kind="plan_approval_request",
            correlation_id=corr_id,
        ))
        decision, reason = await approvals.wait(corr_id)

    assert decision == "denied"
    assert reason == "missing risk assessment"
