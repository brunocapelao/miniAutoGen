"""Tests for plan approval — lead grants approval."""

from __future__ import annotations

import anyio
import pytest

from miniautogen.core.contracts.team_message import MailMessage
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.runtime.team_mailbox import InMemoryMailboxStore
from miniautogen.core.runtime.team_plan_approval import PlanApprovalRegistry


@pytest.mark.anyio
async def test_request_and_grant() -> None:
    sink = InMemoryEventSink()
    mailbox = InMemoryMailboxStore(
        agents=["teammate_a", "lead"],
        team_run_id="test-approve",
        event_sink=sink,
    )
    approvals = PlanApprovalRegistry(event_sink=sink, team_run_id="test-approve")

    async def teammate() -> str:
        corr_id = await approvals.register("teammate_a", "lead", 60.0)
        corr_id_str = corr_id
        plan_content = "DROP TABLE users;"
        await mailbox.send(MailMessage(
            id="approve-req-1",
            from_agent="teammate_a",
            to_agent="lead",
            content=plan_content,
            kind="plan_approval_request",
            correlation_id=corr_id_str,
        ))
        decision, reason = await approvals.wait(corr_id_str)
        return decision

    async def lead() -> None:
        async for msg in mailbox.receive_stream("lead"):
            if msg.kind == "plan_approval_request":
                assert msg.correlation_id is not None
                await approvals.resolve(
                    msg.correlation_id, "granted", reason="looks good"
                )
                await mailbox.send(MailMessage(
                    id="approve-resp-1",
                    from_agent="lead",
                    to_agent="teammate_a",
                    content="granted",
                    kind="plan_approval_granted",
                    correlation_id=msg.correlation_id,
                ))
            break

    async with anyio.create_task_group() as tg:
        tg.start_soon(lead)
        decision = await teammate()

    assert decision == "granted"


@pytest.mark.anyio
async def test_grant_within_200ms() -> None:
    sink = InMemoryEventSink()
    mailbox = InMemoryMailboxStore(
        agents=["A", "lead"],
        team_run_id="test-speed",
        event_sink=sink,
    )
    approvals = PlanApprovalRegistry(event_sink=sink, team_run_id="test-speed")

    async def fast_lead() -> None:
        async for msg in mailbox.receive_stream("lead"):
            if msg.kind == "plan_approval_request" and msg.correlation_id:
                await approvals.resolve(msg.correlation_id, "granted", reason="ok")
                await mailbox.send(MailMessage(
                    id="resp-fast", from_agent="lead", to_agent="A",
                    content="granted", kind="plan_approval_granted",
                    correlation_id=msg.correlation_id,
                ))
            break

    async with anyio.create_task_group() as tg:
        tg.start_soon(fast_lead)
        start = anyio.current_time()
        corr_id = await approvals.register("A", "lead", 60.0)
        await mailbox.send(MailMessage(
            id="req-fast", from_agent="A", to_agent="lead",
            content="migration", kind="plan_approval_request",
            correlation_id=corr_id,
        ))
        decision, _ = await approvals.wait(corr_id)
        elapsed = anyio.current_time() - start

    assert decision == "granted"
    assert elapsed < 0.2
