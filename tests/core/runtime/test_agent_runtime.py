"""Tests for AgentRuntime compositor.

Validates that AgentRuntime satisfies all three agent protocols
(WorkflowAgent, ConversationalAgent, DeliberationAgent) and that its
lifecycle (initialize/close) and turn execution work correctly.
"""

from __future__ import annotations

from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import anyio
import pytest

from miniautogen.backends.driver import AgentDriver
from miniautogen.backends.models import (
    AgentEvent,
    BackendCapabilities,
    SendTurnRequest,
    StartSessionRequest,
    StartSessionResponse,
)
from miniautogen.core.contracts.agent import (
    ConversationalAgent,
    DeliberationAgent,
    WorkflowAgent,
)
from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.contracts.memory_provider import MemoryProvider
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.events.types import EventType
from miniautogen.core.runtime.agent_errors import AgentClosedError
from miniautogen.core.runtime.agent_runtime import AgentRuntime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run_context(run_id: str = "test-run") -> RunContext:
    """Build a minimal RunContext for tests."""
    from datetime import datetime, timezone

    return RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id="test-corr",
    )


class FakeDriver(AgentDriver):
    """Minimal fake driver that returns a canned response."""

    def __init__(self, response_text: str = "Hello from driver") -> None:
        self._response_text = response_text
        self._session_started = False
        self._session_closed = False
        self._session_id = "fake-session-1"

    async def start_session(
        self, request: StartSessionRequest
    ) -> StartSessionResponse:
        self._session_started = True
        return StartSessionResponse(
            session_id=self._session_id,
            capabilities=BackendCapabilities(sessions=True, streaming=True),
        )

    async def send_turn(  # type: ignore[override]
        self, request: SendTurnRequest
    ) -> AsyncIterator[AgentEvent]:
        yield AgentEvent(
            type="message_completed",
            session_id=request.session_id,
            turn_id="turn-1",
            payload={"text": self._response_text},
        )

    async def cancel_turn(self, request: Any) -> None:
        pass

    async def list_artifacts(self, session_id: str) -> list:
        return []

    async def close_session(self, session_id: str) -> None:
        self._session_closed = True

    async def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(sessions=True, streaming=True)


class FakeMemoryProvider:
    """Minimal fake MemoryProvider for tests."""

    def __init__(self) -> None:
        self.saved_turns: list[list[dict[str, Any]]] = []
        self.distilled: list[str] = []

    async def get_context(
        self,
        agent_id: str,
        context: RunContext,
        max_tokens: int | None = None,
    ) -> list[dict[str, Any]]:
        return [{"role": "system", "content": "memory context"}]

    async def save_turn(
        self,
        messages: list[dict[str, Any]],
        context: RunContext,
    ) -> None:
        self.saved_turns.append(messages)

    async def distill(self, agent_id: str) -> None:
        self.distilled.append(agent_id)


def _make_runtime(
    *,
    driver: AgentDriver | None = None,
    event_sink: InMemoryEventSink | None = None,
    memory: FakeMemoryProvider | None = None,
    agent_id: str = "test-agent",
    system_prompt: str = "You are a test agent.",
) -> AgentRuntime:
    """Build an AgentRuntime with sensible test defaults."""
    return AgentRuntime(
        agent_id=agent_id,
        driver=driver or FakeDriver(),
        event_sink=event_sink or InMemoryEventSink(),
        run_context=_make_run_context(),
        system_prompt=system_prompt,
        memory=memory,
    )


# ---------------------------------------------------------------------------
# Protocol satisfaction
# ---------------------------------------------------------------------------


class TestProtocolSatisfaction:
    """AgentRuntime must satisfy all three runtime_checkable protocols."""

    def test_satisfies_workflow_agent_protocol(self) -> None:
        rt = _make_runtime()
        assert isinstance(rt, WorkflowAgent)

    def test_satisfies_conversational_agent_protocol(self) -> None:
        rt = _make_runtime()
        assert isinstance(rt, ConversationalAgent)

    def test_satisfies_deliberation_agent_protocol(self) -> None:
        rt = _make_runtime()
        assert isinstance(rt, DeliberationAgent)


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class TestLifecycle:
    """initialize() and close() lifecycle tests."""

    @pytest.mark.anyio()
    async def test_initialize_starts_session(self) -> None:
        driver = FakeDriver()
        rt = _make_runtime(driver=driver)
        await rt.initialize()
        assert driver._session_started is True

    @pytest.mark.anyio()
    async def test_close_closes_session(self) -> None:
        driver = FakeDriver()
        rt = _make_runtime(driver=driver)
        await rt.initialize()
        await rt.close()
        assert driver._session_closed is True

    @pytest.mark.anyio()
    async def test_close_distills_memory(self) -> None:
        memory = FakeMemoryProvider()
        rt = _make_runtime(memory=memory)
        await rt.initialize()
        await rt.close()
        assert "test-agent" in memory.distilled

    @pytest.mark.anyio()
    async def test_closed_agent_raises(self) -> None:
        rt = _make_runtime()
        await rt.initialize()
        await rt.close()
        with pytest.raises(AgentClosedError):
            await rt.process("anything")


# ---------------------------------------------------------------------------
# Turn execution (public methods)
# ---------------------------------------------------------------------------


class TestTurnExecution:
    """Tests for process(), reply(), contribute(), review(), route()."""

    @pytest.mark.anyio()
    async def test_process_returns_output(self) -> None:
        rt = _make_runtime(driver=FakeDriver(response_text="workflow result"))
        await rt.initialize()
        result = await rt.process("do something")
        assert result == "workflow result"

    @pytest.mark.anyio()
    async def test_reply_returns_string(self) -> None:
        rt = _make_runtime(driver=FakeDriver(response_text="conv reply"))
        await rt.initialize()
        result = await rt.reply("hello", {})
        assert result == "conv reply"

    @pytest.mark.anyio()
    async def test_contribute_returns_contribution(self) -> None:
        rt = _make_runtime(
            driver=FakeDriver(response_text='{"title":"My Contribution","content":{"key":"val"}}')
        )
        await rt.initialize()
        contrib = await rt.contribute("some topic")
        assert contrib.participant_id == "test-agent"
        assert contrib.title is not None

    @pytest.mark.anyio()
    async def test_review_returns_review(self) -> None:
        from miniautogen.core.contracts.deliberation import Contribution

        c = Contribution(participant_id="other", title="Other", content={"x": 1})
        rt = _make_runtime(
            driver=FakeDriver(
                response_text='{"strengths":["good"],"concerns":[],"questions":[]}'
            )
        )
        await rt.initialize()
        review = await rt.review("other", c)
        assert review.reviewer_id == "test-agent"

    @pytest.mark.anyio()
    async def test_route_returns_router_decision(self) -> None:
        rt = _make_runtime(
            driver=FakeDriver(
                response_text='{"current_state_summary":"ok","missing_information":"none","next_agent":"agent-b","terminate":false,"stagnation_risk":0.1}'
            )
        )
        await rt.initialize()
        decision = await rt.route([{"role": "user", "content": "hi"}])
        assert decision.next_agent == "agent-b"


# ---------------------------------------------------------------------------
# Event emission
# ---------------------------------------------------------------------------


class TestEventEmission:
    """Verify events are emitted during the turn lifecycle."""

    @pytest.mark.anyio()
    async def test_events_emitted_during_turn(self) -> None:
        sink = InMemoryEventSink()
        rt = _make_runtime(event_sink=sink)
        await rt.initialize()
        await rt.process("test input")

        event_types = [e.type for e in sink.events]
        assert EventType.AGENT_INITIALIZED.value in event_types
        assert EventType.AGENT_TURN_STARTED.value in event_types
        assert EventType.AGENT_TURN_COMPLETED.value in event_types

    @pytest.mark.anyio()
    async def test_close_emits_agent_closed(self) -> None:
        sink = InMemoryEventSink()
        rt = _make_runtime(event_sink=sink)
        await rt.initialize()
        await rt.close()

        event_types = [e.type for e in sink.events]
        assert EventType.AGENT_CLOSED.value in event_types


# ---------------------------------------------------------------------------
# Memory integration
# ---------------------------------------------------------------------------


class TestMemoryIntegration:
    """Verify memory provider is called during turn execution."""

    @pytest.mark.anyio()
    async def test_memory_save_turn_called(self) -> None:
        memory = FakeMemoryProvider()
        rt = _make_runtime(memory=memory)
        await rt.initialize()
        await rt.process("test input")
        assert len(memory.saved_turns) > 0

    @pytest.mark.anyio()
    async def test_memory_context_loaded_on_initialize(self) -> None:
        """Memory load event should be emitted on initialize."""
        sink = InMemoryEventSink()
        memory = FakeMemoryProvider()
        rt = _make_runtime(event_sink=sink, memory=memory)
        await rt.initialize()

        event_types = [e.type for e in sink.events]
        assert EventType.AGENT_MEMORY_LOADED.value in event_types
