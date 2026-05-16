"""Tests for InMemoryMailboxStore basic operations: send, receive, FIFO, peek, pending_count."""

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
        agents=["alice", "bob", "lead"],
        team_run_id="test-run-1",
        event_sink=sink,
    )


@pytest.mark.anyio
async def test_send_and_receive_single(mailbox: InMemoryMailboxStore) -> None:
    msg = MailMessage(
        id="msg-1",
        from_agent="alice",
        to_agent="bob",
        content="Hello Bob!",
        kind="chat",
    )
    await mailbox.send(msg)

    received = []
    async with anyio.create_task_group() as tg:

        async def reader() -> None:
            async for m in mailbox.receive_stream("bob"):
                received.append(m)

        tg.start_soon(reader)
        await anyio.sleep(0.05)
        tg.cancel_scope.cancel()

    assert len(received) == 1
    assert received[0].id == "msg-1"
    assert received[0].content == "Hello Bob!"


@pytest.mark.anyio
async def test_fifo_order(mailbox: InMemoryMailboxStore) -> None:
    messages = [
        MailMessage(id=f"msg-{i}", from_agent="alice", to_agent="bob",
                     content=f"Message {i}", kind="chat")
        for i in range(5)
    ]
    for m in messages:
        await mailbox.send(m)

    received = []
    async with anyio.create_task_group() as tg:

        async def reader() -> None:
            async for m in mailbox.receive_stream("bob"):
                received.append(m)

        tg.start_soon(reader)
        await anyio.sleep(0.05)
        tg.cancel_scope.cancel()

    assert len(received) == 5
    for i in range(5):
        assert received[i].id == f"msg-{i}"
        assert received[i].content == f"Message {i}"


@pytest.mark.anyio
async def test_peek_is_non_destructive(mailbox: InMemoryMailboxStore) -> None:
    msg = MailMessage(
        id="msg-1", from_agent="alice", to_agent="bob",
        content="Peek test", kind="chat",
    )
    await mailbox.send(msg)

    peeked = await mailbox.peek("bob")
    assert len(peeked) == 1
    assert peeked[0].id == "msg-1"

    peeked_again = await mailbox.peek("bob")
    assert len(peeked_again) == 1


@pytest.mark.anyio
async def test_pending_count(mailbox: InMemoryMailboxStore) -> None:
    assert await mailbox.pending_count("bob") == 0

    await mailbox.send(MailMessage(
        id="m1", from_agent="alice", to_agent="bob", content="1", kind="chat",
    ))
    assert await mailbox.pending_count("bob") == 1

    await mailbox.send(MailMessage(
        id="m2", from_agent="alice", to_agent="bob", content="2", kind="chat",
    ))
    assert await mailbox.pending_count("bob") == 2


@pytest.mark.anyio
async def test_different_agents_isolated(mailbox: InMemoryMailboxStore) -> None:
    await mailbox.send(MailMessage(
        id="m1", from_agent="alice", to_agent="bob", content="to bob", kind="chat",
    ))
    await mailbox.send(MailMessage(
        id="m2", from_agent="alice", to_agent="lead", content="to lead", kind="chat",
    ))

    assert await mailbox.pending_count("bob") == 1
    assert await mailbox.pending_count("lead") == 1
