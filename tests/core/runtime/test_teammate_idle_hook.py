"""Tests for TeammateIdle hook — teammate idle detection."""

from __future__ import annotations

import anyio
import pytest

from miniautogen.core.contracts.team_message import MailMessage
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.events.types import EventType
from miniautogen.core.runtime.team_mailbox import InMemoryMailboxStore


class IdleTracker:
    """Simple TeamHook-like tracker that records idle/message events."""

    def __init__(self) -> None:
        self.idle_teammates: list[str] = []
        self.received_messages: list[MailMessage] = []

    async def on_teammate_idle(self, teammate: str, context: object = None) -> None:
        self.idle_teammates.append(teammate)

    async def on_message_received(self, message: MailMessage, context: object = None) -> None:
        self.received_messages.append(message)


@pytest.fixture
def idle_tracker() -> IdleTracker:
    return IdleTracker()


@pytest.mark.anyio
async def test_idle_when_inbox_empty(idle_tracker: IdleTracker) -> None:
    sink = InMemoryEventSink()
    mailbox = InMemoryMailboxStore(
        agents=["alice"],
        team_run_id="test-idle",
        event_sink=sink,
    )

    assert await mailbox.pending_count("alice") == 0
    await idle_tracker.on_teammate_idle("alice")
    assert "alice" in idle_tracker.idle_teammates


@pytest.mark.anyio
async def test_not_idle_when_message_arrives(idle_tracker: IdleTracker) -> None:
    sink = InMemoryEventSink()
    mailbox = InMemoryMailboxStore(
        agents=["alice", "bob"],
        team_run_id="test-busy",
        event_sink=sink,
    )

    await mailbox.send(MailMessage(
        id="m1", from_agent="bob", to_agent="alice",
        content="work to do", kind="chat",
    ))

    assert await mailbox.pending_count("alice") == 1

    if await mailbox.pending_count("alice") == 0:
        await idle_tracker.on_teammate_idle("alice")
    assert "alice" not in idle_tracker.idle_teammates


@pytest.mark.anyio
async def test_idle_after_inbox_drained(idle_tracker: IdleTracker) -> None:
    sink = InMemoryEventSink()
    mailbox = InMemoryMailboxStore(
        agents=["alice", "bob"],
        team_run_id="test-drained",
        event_sink=sink,
    )

    await mailbox.send(MailMessage(
        id="m1", from_agent="bob", to_agent="alice",
        content="hello", kind="chat",
    ))

    received = []
    async for m in mailbox.receive_stream("alice"):
        received.append(m)
        break

    assert await mailbox.pending_count("alice") == 0
    await idle_tracker.on_teammate_idle("alice")
    assert "alice" in idle_tracker.idle_teammates


@pytest.mark.anyio
async def test_message_received_hook_fires(idle_tracker: IdleTracker) -> None:
    sink = InMemoryEventSink()
    mailbox = InMemoryMailboxStore(
        agents=["alice", "bob"],
        team_run_id="test-hook",
        event_sink=sink,
    )

    msg = MailMessage(
        id="m1", from_agent="bob", to_agent="alice",
        content="ping", kind="chat",
    )
    await mailbox.send(msg)

    received = []
    async for m in mailbox.receive_stream("alice"):
        received.append(m)
        await idle_tracker.on_message_received(m)
        break

    assert len(idle_tracker.received_messages) == 1
    assert idle_tracker.received_messages[0].content == "ping"
