"""Tests for TUI-specific Textual messages."""

from __future__ import annotations

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.types import EventType
from miniautogen.tui.messages import TuiEvent


def test_tui_event_wraps_execution_event() -> None:
    """TuiEvent must wrap an ExecutionEvent."""
    event = ExecutionEvent(
        type=EventType.RUN_STARTED.value,
        run_id="run-1",
    )
    msg = TuiEvent(event)
    assert msg.event is event
    assert msg.event.type == EventType.RUN_STARTED.value


def test_tui_event_is_textual_message() -> None:
    """TuiEvent must be a Textual Message."""
    from textual.message import Message

    event = ExecutionEvent(
        type=EventType.AGENT_REPLIED.value,
        run_id="run-1",
        payload={"agent_id": "writer", "content": "hello"},
    )
    msg = TuiEvent(event)
    assert isinstance(msg, Message)
