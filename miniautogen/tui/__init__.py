"""MiniAutoGen Dash -- TUI dashboard for multi-agent pipeline monitoring.

Optional dependency: install with ``pip install miniautogen[tui]``.

This package has ZERO coupling to miniautogen.core internals.
It only imports protocols (EventSink) and data models (ExecutionEvent, EventType).
"""

from miniautogen.tui.app import MiniAutoGenDash
from miniautogen.tui.event_sink import TuiEventSink
from miniautogen.tui.messages import TuiEvent
from miniautogen.tui.status import AgentStatus, StatusVocab

__all__ = [
    "MiniAutoGenDash",
    "TuiEventSink",
    "TuiEvent",
    "AgentStatus",
    "StatusVocab",
]
