"""Textual messages for TUI event handling.

These messages bridge ExecutionEvents from the core event system
into Textual's message loop, enabling reactive UI updates.
"""

from __future__ import annotations

from textual.message import Message

from miniautogen.core.contracts.events import ExecutionEvent


class TuiEvent(Message):
    """Wraps a core ExecutionEvent as a Textual Message.

    Posted by the EventBridgeWorker into the Textual message loop.
    Widgets subscribe to this message to update their display.
    """

    def __init__(self, event: ExecutionEvent) -> None:
        super().__init__()
        self.event = event
