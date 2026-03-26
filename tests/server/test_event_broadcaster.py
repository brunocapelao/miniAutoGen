"""Tests for GlobalEventBroadcaster."""
from __future__ import annotations

import asyncio

import pytest

from miniautogen.server.event_broadcaster import GlobalEventBroadcaster


@pytest.mark.anyio
async def test_publish_and_subscribe():
    """Publish event, subscriber receives it."""
    broadcaster = GlobalEventBroadcaster()
    queue = broadcaster.subscribe()

    event = {"type": "run_started", "run_id": "r1"}
    await broadcaster.publish(event)

    received = queue.get_nowait()
    assert received == event


@pytest.mark.anyio
async def test_unsubscribe():
    """Unsubscribed queue stops receiving events."""
    broadcaster = GlobalEventBroadcaster()
    queue = broadcaster.subscribe()
    broadcaster.unsubscribe(queue)

    await broadcaster.publish({"type": "run_started", "run_id": "r1"})

    assert queue.empty()


@pytest.mark.anyio
async def test_get_recent():
    """Returns buffered events."""
    broadcaster = GlobalEventBroadcaster()

    for i in range(5):
        await broadcaster.publish({"type": "step", "index": i})

    recent = broadcaster.get_recent(limit=3)
    assert len(recent) == 3
    assert recent[0]["index"] == 2
    assert recent[2]["index"] == 4

    all_recent = broadcaster.get_recent(limit=100)
    assert len(all_recent) == 5


@pytest.mark.anyio
async def test_buffer_limit():
    """Respects max_buffer size."""
    broadcaster = GlobalEventBroadcaster(max_buffer=3)

    for i in range(5):
        await broadcaster.publish({"type": "step", "index": i})

    recent = broadcaster.get_recent(limit=100)
    assert len(recent) == 3
    assert recent[0]["index"] == 2
    assert recent[2]["index"] == 4


@pytest.mark.anyio
async def test_subscriber_count():
    """subscriber_count tracks active subscribers."""
    broadcaster = GlobalEventBroadcaster()
    assert broadcaster.subscriber_count == 0

    q1 = broadcaster.subscribe()
    q2 = broadcaster.subscribe()
    assert broadcaster.subscriber_count == 2

    broadcaster.unsubscribe(q1)
    assert broadcaster.subscriber_count == 1

    broadcaster.unsubscribe(q2)
    assert broadcaster.subscriber_count == 0


@pytest.mark.anyio
async def test_multiple_subscribers():
    """Multiple subscribers each receive the same event."""
    broadcaster = GlobalEventBroadcaster()
    q1 = broadcaster.subscribe()
    q2 = broadcaster.subscribe()

    event = {"type": "run_started", "run_id": "r1"}
    await broadcaster.publish(event)

    assert q1.get_nowait() == event
    assert q2.get_nowait() == event
