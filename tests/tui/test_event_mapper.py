"""Tests for mapping ExecutionEvents to TUI status updates."""

from __future__ import annotations

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.types import EventType
from miniautogen.tui.event_mapper import EventMapper
from miniautogen.tui.status import AgentStatus


def test_run_started_maps_to_active() -> None:
    event = ExecutionEvent(type=EventType.RUN_STARTED.value, run_id="r1")
    result = EventMapper.map_run_status(event)
    assert result == AgentStatus.ACTIVE


def test_run_finished_maps_to_done() -> None:
    event = ExecutionEvent(type=EventType.RUN_FINISHED.value, run_id="r1")
    result = EventMapper.map_run_status(event)
    assert result == AgentStatus.DONE


def test_run_failed_maps_to_failed() -> None:
    event = ExecutionEvent(type=EventType.RUN_FAILED.value, run_id="r1")
    result = EventMapper.map_run_status(event)
    assert result == AgentStatus.FAILED


def test_run_cancelled_maps_to_cancelled() -> None:
    event = ExecutionEvent(type=EventType.RUN_CANCELLED.value, run_id="r1")
    result = EventMapper.map_run_status(event)
    assert result == AgentStatus.CANCELLED


def test_run_timed_out_maps_to_failed() -> None:
    event = ExecutionEvent(type=EventType.RUN_TIMED_OUT.value, run_id="r1")
    result = EventMapper.map_run_status(event)
    assert result == AgentStatus.FAILED


def test_component_started_maps_to_active() -> None:
    event = ExecutionEvent(type=EventType.COMPONENT_STARTED.value, run_id="r1")
    result = EventMapper.map_component_status(event)
    assert result == AgentStatus.ACTIVE


def test_component_finished_maps_to_done() -> None:
    event = ExecutionEvent(type=EventType.COMPONENT_FINISHED.value, run_id="r1")
    result = EventMapper.map_component_status(event)
    assert result == AgentStatus.DONE


def test_approval_requested_maps_to_waiting() -> None:
    event = ExecutionEvent(type=EventType.APPROVAL_REQUESTED.value, run_id="r1")
    result = EventMapper.map_run_status(event)
    assert result == AgentStatus.WAITING


def test_backend_message_delta_maps_to_working() -> None:
    event = ExecutionEvent(type=EventType.BACKEND_MESSAGE_DELTA.value, run_id="r1")
    result = EventMapper.map_agent_status(event)
    assert result == AgentStatus.WORKING


def test_tool_invoked_maps_to_working() -> None:
    event = ExecutionEvent(type=EventType.TOOL_INVOKED.value, run_id="r1")
    result = EventMapper.map_agent_status(event)
    assert result == AgentStatus.WORKING


def test_agent_replied_maps_to_done() -> None:
    event = ExecutionEvent(type=EventType.AGENT_REPLIED.value, run_id="r1")
    result = EventMapper.map_agent_status(event)
    assert result == AgentStatus.DONE


def test_extract_agent_id_from_payload() -> None:
    event = ExecutionEvent(
        type=EventType.AGENT_REPLIED.value,
        run_id="r1",
        payload={"agent_id": "writer"},
    )
    result = EventMapper.extract_agent_id(event)
    assert result == "writer"


def test_extract_agent_id_missing_returns_none() -> None:
    event = ExecutionEvent(type=EventType.RUN_STARTED.value, run_id="r1")
    result = EventMapper.extract_agent_id(event)
    assert result is None
