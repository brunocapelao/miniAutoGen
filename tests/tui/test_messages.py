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


def test_run_completed_message_exists() -> None:
    """RunCompleted message must be importable and carry pipeline name."""
    from textual.message import Message

    from miniautogen.tui.messages import RunCompleted
    msg = RunCompleted(pipeline_name="main", status="completed")
    assert isinstance(msg, Message)
    assert msg.pipeline_name == "main"
    assert msg.status == "completed"


def test_sidebar_refresh_message_exists() -> None:
    """SidebarRefresh message must be importable."""
    from textual.message import Message

    from miniautogen.tui.messages import SidebarRefresh
    msg = SidebarRefresh()
    assert isinstance(msg, Message)


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


def test_tab_changed_message() -> None:
    """TabChanged message must carry tab_name."""
    from textual.message import Message

    from miniautogen.tui.messages import TabChanged

    msg = TabChanged(tab_name="flows")
    assert isinstance(msg, Message)
    assert msg.tab_name == "flows"


def test_run_started_message() -> None:
    """RunStarted message must carry flow_name and run_id."""
    from textual.message import Message

    from miniautogen.tui.messages import RunStarted

    msg = RunStarted(flow_name="research-flow", run_id="abc123")
    assert isinstance(msg, Message)
    assert msg.flow_name == "research-flow"
    assert msg.run_id == "abc123"


def test_run_stopped_message() -> None:
    """RunStopped message must carry run_id and final_status."""
    from textual.message import Message

    from miniautogen.tui.messages import RunStopped

    msg = RunStopped(run_id="abc123", final_status="completed")
    assert isinstance(msg, Message)
    assert msg.run_id == "abc123"
    assert msg.final_status == "completed"
