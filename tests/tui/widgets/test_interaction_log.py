"""Tests for the InteractionLog widget -- the main work panel."""

from __future__ import annotations

import pytest

from textual.widget import Widget

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.types import EventType
from miniautogen.tui.widgets.interaction_log import InteractionLog


def test_interaction_log_is_widget() -> None:
    assert issubclass(InteractionLog, Widget)


def test_interaction_log_starts_empty() -> None:
    log = InteractionLog()
    assert log.entry_count == 0


def test_interaction_log_add_agent_message() -> None:
    log = InteractionLog()
    log.add_agent_message(
        agent_id="writer",
        agent_name="Writer",
        content="Hello, I will write the code.",
    )
    assert log.entry_count == 1


def test_interaction_log_add_tool_call() -> None:
    log = InteractionLog()
    log.add_tool_call(
        agent_id="writer",
        tool_name="file_write",
        status="executing",
    )
    assert log.entry_count == 1


def test_interaction_log_add_step_header() -> None:
    log = InteractionLog()
    log.add_step_header(
        step_number=1,
        step_label="Planning",
        agent_name="Planner",
    )
    assert log.entry_count == 1


def test_interaction_log_add_streaming_indicator() -> None:
    log = InteractionLog()
    log.add_streaming_indicator(
        agent_id="writer",
        state="thinking",
    )
    assert log.entry_count == 1


def test_interaction_log_handles_agent_replied_event() -> None:
    log = InteractionLog()
    event = ExecutionEvent(
        type=EventType.AGENT_REPLIED.value,
        run_id="r1",
        payload={"agent_id": "writer", "content": "Done."},
    )
    log.handle_event(event)
    assert log.entry_count >= 1


def test_interaction_log_handles_component_started_event() -> None:
    log = InteractionLog()
    event = ExecutionEvent(
        type=EventType.COMPONENT_STARTED.value,
        run_id="r1",
        payload={"component_name": "Planning", "step_number": 1},
    )
    log.handle_event(event)
    assert log.entry_count >= 1


def test_interaction_log_handles_tool_invoked_event() -> None:
    log = InteractionLog()
    event = ExecutionEvent(
        type=EventType.TOOL_INVOKED.value,
        run_id="r1",
        payload={"agent_id": "writer", "tool_name": "file_write"},
    )
    log.handle_event(event)
    assert log.entry_count >= 1


def test_interaction_log_handles_streaming_event() -> None:
    log = InteractionLog()
    event = ExecutionEvent(
        type=EventType.BACKEND_MESSAGE_DELTA.value,
        run_id="r1",
        payload={"agent_id": "writer"},
    )
    log.handle_event(event)
    assert log.entry_count >= 1
