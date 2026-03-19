"""Tests for EventEmitterHook -- emits AGENT_TURN_STARTED/COMPLETED events."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from miniautogen.core.contracts.agent_hook import AgentHook
from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.events.types import EventType
from miniautogen.core.runtime.agent_hooks import EventEmitterHook


def _make_context(run_id: str = "run-1") -> RunContext:
    return RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id="corr-1",
    )


def test_event_emitter_hook_satisfies_protocol() -> None:
    sink = InMemoryEventSink()
    hook = EventEmitterHook(event_sink=sink, agent_id="agent-1")
    assert isinstance(hook, AgentHook)


@pytest.mark.anyio
async def test_event_emitter_emits_turn_started_on_before_turn() -> None:
    sink = InMemoryEventSink()
    hook = EventEmitterHook(event_sink=sink, agent_id="agent-1")
    messages: list[dict[str, Any]] = [{"role": "user", "content": "hello"}]
    ctx = _make_context()

    result = await hook.before_turn(messages, ctx)

    assert result == messages  # pass-through
    assert len(sink.events) == 1
    assert sink.events[0].type == EventType.AGENT_TURN_STARTED.value
    assert sink.events[0].run_id == "run-1"
    assert sink.events[0].get_payload("agent_id") == "agent-1"


@pytest.mark.anyio
async def test_event_emitter_emits_turn_completed_on_after_event() -> None:
    sink = InMemoryEventSink()
    hook = EventEmitterHook(event_sink=sink, agent_id="agent-1")
    event = ExecutionEvent(type="backend_message_completed", run_id="run-1")
    ctx = _make_context()

    result = await hook.after_event(event, ctx)

    assert result.type == "backend_message_completed"  # pass-through
    assert len(sink.events) == 1
    assert sink.events[0].type == EventType.AGENT_HOOK_EXECUTED.value


@pytest.mark.anyio
async def test_event_emitter_on_error_returns_none() -> None:
    sink = InMemoryEventSink()
    hook = EventEmitterHook(event_sink=sink, agent_id="agent-1")
    ctx = _make_context()

    result = await hook.on_error(RuntimeError("test"), ctx)
    assert result is None
