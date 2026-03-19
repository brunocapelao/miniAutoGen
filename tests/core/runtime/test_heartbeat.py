"""Tests for HeartbeatToken and heartbeat watchdog."""

from __future__ import annotations

import anyio
import pytest

from miniautogen.core.runtime.heartbeat import HeartbeatToken, run_heartbeat_watchdog

pytestmark = pytest.mark.anyio


async def test_beat_resets_timer() -> None:
    """Calling beat() resets the internal timer."""
    token = HeartbeatToken(interval_seconds=1.0)
    # Advance a bit, then beat
    await anyio.sleep(0.3)
    await token.beat()
    assert token.is_alive()


async def test_is_alive_true_within_interval() -> None:
    """is_alive returns True immediately after creation."""
    token = HeartbeatToken(interval_seconds=1.0)
    assert token.is_alive()


async def test_is_alive_false_after_interval() -> None:
    """is_alive returns False after interval elapses without beat."""
    token = HeartbeatToken(interval_seconds=0.1)
    await anyio.sleep(0.15)
    assert not token.is_alive()


async def test_watchdog_cancels_scope_when_no_beats() -> None:
    """Watchdog cancels the scope when heartbeat lapses."""
    token = HeartbeatToken(interval_seconds=0.1)

    with anyio.CancelScope() as scope:
        async with anyio.create_task_group() as tg:
            tg.start_soon(run_heartbeat_watchdog, token, scope)
            # Don't beat -- let watchdog detect lapse
            await anyio.sleep(0.5)

    assert scope.cancel_called


async def test_watchdog_does_not_cancel_when_beats_arrive() -> None:
    """Watchdog keeps running when beats arrive on time."""
    token = HeartbeatToken(interval_seconds=0.2)
    beat_count = 0

    async def keep_beating() -> None:
        nonlocal beat_count
        for _ in range(5):
            await token.beat()
            beat_count += 1
            await anyio.sleep(0.05)

    async with anyio.create_task_group() as tg:
        scope = tg.cancel_scope
        tg.start_soon(run_heartbeat_watchdog, token, scope)
        tg.start_soon(keep_beating)
        # Wait for beats to finish, then cancel watchdog cleanly
        await anyio.sleep(0.35)
        scope.cancel()

    assert beat_count == 5
    # Scope was cancelled by us, not by watchdog
