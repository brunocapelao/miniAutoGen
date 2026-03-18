"""Desktop notifications via OSC 9/99 escape sequences.

Supports three notification levels: all, failures-only, none.
Falls back to terminal bell when OSC is unsupported.
"""

from __future__ import annotations

import sys
from enum import Enum

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.types import EventType

# Events that always trigger notifications
_NOTIFY_EVENTS: set[str] = {
    EventType.APPROVAL_REQUESTED.value,
    EventType.RUN_FINISHED.value,
    EventType.RUN_FAILED.value,
    EventType.RUN_TIMED_OUT.value,
    EventType.RUN_CANCELLED.value,
}

# Events considered failures
_FAILURE_EVENTS: set[str] = {
    EventType.RUN_FAILED.value,
    EventType.RUN_TIMED_OUT.value,
    EventType.APPROVAL_REQUESTED.value,
}


class NotificationLevel(str, Enum):
    ALL = "all"
    FAILURES_ONLY = "failures-only"
    NONE = "none"


def should_notify(
    event: ExecutionEvent,
    level: NotificationLevel = NotificationLevel.ALL,
) -> bool:
    """Determine if an event warrants a desktop notification."""
    if level == NotificationLevel.NONE:
        return False
    if event.type not in _NOTIFY_EVENTS:
        return False
    if level == NotificationLevel.FAILURES_ONLY:
        return event.type in _FAILURE_EVENTS
    return True


class TerminalNotifier:
    """Sends desktop notifications via OSC 9/99 escape sequences."""

    @staticmethod
    def format_event(event: ExecutionEvent) -> tuple[str, str]:
        """Format an event into (title, body) for notification."""
        agent_id = event.payload.get("agent_id", "Agent")
        etype = event.type

        if etype == EventType.APPROVAL_REQUESTED.value:
            return ("Approval Needed", f"{agent_id} needs your approval")
        if etype == EventType.RUN_FINISHED.value:
            return ("Pipeline Completed", f"Run {event.run_id or 'unknown'} finished")
        if etype == EventType.RUN_FAILED.value:
            return ("Pipeline Failed", f"Run {event.run_id or 'unknown'} failed")
        if etype == EventType.RUN_TIMED_OUT.value:
            return ("Pipeline Timed Out", f"Run {event.run_id or 'unknown'} timed out")
        if etype == EventType.RUN_CANCELLED.value:
            return ("Pipeline Cancelled", f"Run {event.run_id or 'unknown'} cancelled")
        return ("MiniAutoGen", f"Event: {etype}")

    def build_osc9(self, title: str, body: str) -> str:
        """Build an OSC 9/99 notification escape sequence.

        OSC 99 (kitty/modern): ``ESC ] 99 ; title ST body``
        OSC 9 (iTerm2/older): ``ESC ] 9 ; text ST``
        Falls back to OSC 9 which is more widely supported.
        """
        text = f"{title}: {body}" if body else title
        return f"\x1b]9;{text}\x1b\\"

    def send(self, event: ExecutionEvent) -> None:
        """Send a desktop notification for an event."""
        title, body = self.format_event(event)
        seq = self.build_osc9(title, body)
        try:
            sys.stderr.write(seq)
            sys.stderr.flush()
        except OSError:
            # Terminal doesn't support OSC; send bell as fallback
            try:
                sys.stderr.write("\a")
                sys.stderr.flush()
            except OSError:
                pass
