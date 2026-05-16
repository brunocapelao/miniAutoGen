"""Tests for mailbox cancellation — no stream leaks on cancel."""

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
        agents=["alice", "bob"],
        team_run_id="test-cancel",
        event_sink=sink,
    )


@pytest.mark.anyio
async def test_cancel_while_receiving(mailbox: InMemoryMailboxStore) -> None:
    """Cancel the task group while receiver is blocked on receive_stream; no leak."""
    received: list[MailMessage] = []

    async def reader() -> None:
        async for m in mailbox.receive_stream("alice"):
            received.append(m)

    async def slow_sender() -> None:
        await anyio.sleep(0.1)
        await mailbox.send(MailMessage(
            id="m1", from_agent="bob", to_agent="alice",
            content="late", kind="chat",
        ))
        await anyio.sleep(1)
        await mailbox.send(MailMessage(
            id="m2", from_agent="bob", to_agent="alice",
            content="very late", kind="chat",
        ))

    async with anyio.create_task_group() as tg:
        tg.start_soon(reader)
        tg.start_soon(slow_sender)
        await anyio.sleep(0.3)
        tg.cancel_scope.cancel()

    await anyio.sleep(0.1)
    assert len(received) == 1
    assert received[0].id == "m1"


@pytest.mark.anyio
async def test_aclose_cleans_streams(mailbox: InMemoryMailboxStore) -> None:
    """aclose should not raise and leave streams clean."""
    await mailbox.send(MailMessage(
        id="m1", from_agent="alice", to_agent="bob",
        content="pending", kind="chat",
    ))
    await mailbox.aclose()

    assert await mailbox.pending_count("bob") == 0


@pytest.mark.anyio
async def test_concurrent_send_and_cancel(mailbox: InMemoryMailboxStore) -> None:
    """Send messages while reader is active, then cancel — must not leak."""
    received: list[MailMessage] = []

    async def reader() -> None:
        async for m in mailbox.receive_stream("bob"):
            received.append(m)

    async def sender() -> None:
        for i in range(10):
            await mailbox.send(MailMessage(
                id=f"m{i}", from_agent="alice", to_agent="bob",
                content=f"msg {i}", kind="chat",
            ))
            await anyio.sleep(0.01)

    async with anyio.create_task_group() as tg:
        tg.start_soon(reader)
        tg.start_soon(sender)
        await anyio.sleep(0.15)
        assert len(received) > 0
        tg.cancel_scope.cancel()

    await anyio.sleep(0.05)
    await mailbox.aclose()
