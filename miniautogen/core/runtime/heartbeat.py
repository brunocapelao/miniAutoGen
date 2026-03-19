"""HeartbeatToken and watchdog for zombie agent detection.

HeartbeatToken provides a liveness signal for long-running agent operations.
The watchdog task cancels an AnyIO scope if heartbeat lapses, preventing
zombie agents from consuming resources indefinitely.
"""

from __future__ import annotations

import time

import anyio


class HeartbeatToken:
    """Liveness signal for long-running agent operations.

    Agents call beat() periodically to signal they are still alive.
    The watchdog checks is_alive() and cancels the scope if the
    heartbeat interval has been exceeded.
    """

    def __init__(self, interval_seconds: float) -> None:
        self._interval = interval_seconds
        self._last_beat: float = time.monotonic()

    async def beat(self) -> None:
        """Signal liveness. Call periodically from agent code."""
        self._last_beat = time.monotonic()

    def is_alive(self) -> bool:
        """Check if last beat is within interval."""
        return (time.monotonic() - self._last_beat) < self._interval


async def run_heartbeat_watchdog(
    token: HeartbeatToken, cancel_scope: anyio.CancelScope
) -> None:
    """Watchdog task that cancels scope if heartbeat stops.

    Checks at Nyquist frequency (half the interval).
    Runs as sibling task in a TaskGroup.

    Args:
        token: The heartbeat token to monitor.
        cancel_scope: The AnyIO cancel scope to cancel on lapse.
    """
    check_interval = token._interval / 2
    while not cancel_scope.cancel_called:
        await anyio.sleep(check_interval)
        if not token.is_alive():
            cancel_scope.cancel()
            return
