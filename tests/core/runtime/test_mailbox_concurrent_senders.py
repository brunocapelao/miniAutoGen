"""Tests for InMemoryMailboxStore with concurrent senders — FIFO ordering under load."""

from __future__ import annotations

import anyio
import pytest

from miniautogen.core.contracts.team_message import MailMessage
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.runtime.team_mailbox import InMemoryMailboxStore


@pytest.fixture
def mailbox() -> InMemoryMailboxStore:
    sink = InMemoryEventSink()
    return InMemoryMailboxStore(
        agents=["alice", "bob", "lead", "charlie", "dave", "eve"],
        team_run_id="test-concurrent",
        event_sink=sink,
    )


@pytest.mark.anyio
async def test_5_senders_concurrent_to_1_inbox(mailbox: InMemoryMailboxStore) -> None:
    senders = ["alice", "lead", "charlie", "dave", "eve"]
    total_per_sender = 100

    async def sender_worker(from_agent: str) -> None:
        for i in range(total_per_sender):
            await mailbox.send(MailMessage(
                id=f"{from_agent}-{i}",
                from_agent=from_agent,
                to_agent="bob",
                content=f"From {from_agent} msg {i}",
                kind="chat",
            ))

    received: list[MailMessage] = []

    async def reader() -> None:
        async for m in mailbox.receive_stream("bob"):
            received.append(m)

    async with anyio.create_task_group() as tg:
        tg.start_soon(reader)
        for sender in senders:
            tg.start_soon(sender_worker, sender)
        await anyio.sleep(0.5)
        tg.cancel_scope.cancel()

    total_expected = len(senders) * total_per_sender
    assert len(received) == total_expected, (
        f"Expected {total_expected}, got {len(received)}"
    )

    ids = [m.id for m in received]
    seen: set[str] = set()
    for msg_id in ids:
        assert msg_id not in seen, f"Duplicate message: {msg_id}"
        seen.add(msg_id)


@pytest.mark.anyio
async def test_fifo_order_per_sender(mailbox: InMemoryMailboxStore) -> None:
    """Messages from a single sender must arrive in send order."""
    async def sender() -> None:
        for i in range(50):
            await mailbox.send(MailMessage(
                id=f"alice-{i}",
                from_agent="alice",
                to_agent="bob",
                content=f"msg {i}",
                kind="chat",
            ))

    received: list[MailMessage] = []

    async def reader() -> None:
        async for m in mailbox.receive_stream("bob"):
            received.append(m)

    async with anyio.create_task_group() as tg:
        tg.start_soon(reader)
        tg.start_soon(sender)
        await anyio.sleep(0.2)
        tg.cancel_scope.cancel()

    alice_msgs = [m for m in received if m.from_agent == "alice"]
    assert len(alice_msgs) == 50
    for i in range(50):
        assert alice_msgs[i].id == f"alice-{i}"
