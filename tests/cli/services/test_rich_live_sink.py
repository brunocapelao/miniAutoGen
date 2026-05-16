"""Tests for RichLiveEventSink internal state management.

These tests verify that the sink correctly updates its internal state
from canonical ExecutionEvents without entering the Rich Live context
(headless test mode). All must fail initially because RichLiveEventSink
does not exist yet.
"""

from __future__ import annotations

import pytest

from miniautogen.api import ExecutionEvent
from miniautogen.cli.services.rich_live_sink import RichLiveEventSink


@pytest.mark.anyio
async def test_run_started_sets_flow_and_run_id() -> None:
    """run_started event sets _flow and truncates _run_id to 8 chars."""
    sink = RichLiveEventSink()
    await sink.publish(
        ExecutionEvent(
            type="run_started",
            payload={"flow_name": "demo", "run_id": "abc12345xx"},
        )
    )
    assert sink._flow == "demo"
    assert sink._run_id == "abc12345"


@pytest.mark.anyio
async def test_agent_turn_started_sets_agent_and_round() -> None:
    """agent_turn_started event sets _agent, _action, and _round."""
    sink = RichLiveEventSink()
    await sink.publish(
        ExecutionEvent(
            type="agent_turn_started",
            payload={
                "agent_id": "Engineer",
                "action": "Contribute",
                "round": 2,
                "max_rounds": 5,
            },
        )
    )
    assert sink._agent == "Engineer"
    assert sink._action == "Contribute"
    assert sink._round == "Round 2/5"


@pytest.mark.anyio
async def test_agent_thought_appends_to_thoughts() -> None:
    """agent_thought events append truncated text to _thoughts deque."""
    sink = RichLiveEventSink()
    await sink.publish(
        ExecutionEvent(
            type="agent_thought",
            payload={"text": "First thought"},
        )
    )
    await sink.publish(
        ExecutionEvent(
            type="agent_thought",
            payload={"text": "Second thought"},
        )
    )
    await sink.publish(
        ExecutionEvent(
            type="agent_thought",
            payload={"text": "Third thought"},
        )
    )
    assert len(sink._thoughts) == 3
    assert sink._thoughts[0] == "First thought"


@pytest.mark.anyio
async def test_agent_thought_maxlen_truncates() -> None:
    """Only the last 3 thoughts are kept (maxlen=3)."""
    sink = RichLiveEventSink(thought_lines=3)
    for i in range(5):
        await sink.publish(
            ExecutionEvent(
                type="agent_thought",
                payload={"text": f"Thought {i}"},
            )
        )
    assert len(sink._thoughts) == 3
    assert sink._thoughts[-1] == "Thought 4"


@pytest.mark.anyio
async def test_run_cancelled_sets_saving_checkpoint() -> None:
    """run_cancelled event sets _action to 'Saving checkpoint...'."""
    sink = RichLiveEventSink()
    await sink.publish(
        ExecutionEvent(
            type="run_cancelled",
            payload={"reason": "user interrupt"},
        )
    )
    assert sink._action == "Saving checkpoint..."


@pytest.mark.anyio
async def test_events_total_increments() -> None:
    """_events_total increments on each publish."""
    sink = RichLiveEventSink()
    for i in range(3):
        await sink.publish(
            ExecutionEvent(
                type="agent_thought",
                payload={"text": f"event {i}"},
            )
        )
    assert sink._events_total == 3
