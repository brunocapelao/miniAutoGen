"""Integration test for AgentRuntime compositor — full end-to-end flow.

Proves that AgentRuntime wires all components (driver, memory, tool_registry,
event_sink) correctly and satisfies the WorkflowAgent, ConversationalAgent,
and DeliberationAgent protocols via duck typing.

Test matrix:
  1. Full lifecycle: initialize → process → close
  2. Tools registered: echo tool visible in list_tools
  3. Memory works: save_turn called for each process() invocation
  4. Events emitted: AGENT_INITIALIZED, AGENT_TURN_STARTED,
                     AGENT_TURN_COMPLETED, AGENT_CLOSED
  5. Protocol satisfaction: isinstance checks for all 3 protocols
  6. Closed agent raises: AgentClosedError after close()
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, AsyncIterator

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
from miniautogen.core.contracts.memory_provider import InMemoryMemoryProvider
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.tool import ToolResult
from miniautogen.core.contracts.tool_registry import ToolDefinition
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.events.types import EventType
from miniautogen.core.runtime.agent_errors import AgentClosedError
from miniautogen.core.runtime.agent_runtime import AgentRuntime
from miniautogen.core.runtime.tool_registry import InMemoryToolRegistry


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


def _make_run_context(run_id: str = "integration-run") -> RunContext:
    return RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id="integration-corr",
    )


class EchoDriver(AgentDriver):
    """Driver that echoes the last user message back as message_completed."""

    def __init__(self) -> None:
        self.session_started = False
        self.session_closed = False
        self._session_id = "echo-session-1"

    async def start_session(
        self, request: StartSessionRequest
    ) -> StartSessionResponse:
        self.session_started = True
        return StartSessionResponse(
            session_id=self._session_id,
            capabilities=BackendCapabilities(sessions=True, streaming=True),
        )

    async def send_turn(  # type: ignore[override]
        self, request: SendTurnRequest
    ) -> AsyncIterator[AgentEvent]:
        # Echo the last user message content back
        last_content = ""
        for msg in reversed(request.messages):
            if msg.get("role") == "user":
                last_content = msg.get("content", "")
                break
        yield AgentEvent(
            type="message_completed",
            session_id=request.session_id,
            turn_id="turn-1",
            payload={"text": f"echo: {last_content}"},
        )

    async def cancel_turn(self, request: Any) -> None:
        pass

    async def list_artifacts(self, session_id: str) -> list:
        return []

    async def close_session(self, session_id: str) -> None:
        self.session_closed = True

    async def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(sessions=True, streaming=True)


def _make_runtime(
    *,
    driver: AgentDriver | None = None,
    event_sink: InMemoryEventSink | None = None,
    memory: InMemoryMemoryProvider | None = None,
    tool_registry: InMemoryToolRegistry | None = None,
    agent_id: str = "integration-agent",
) -> AgentRuntime:
    return AgentRuntime(
        agent_id=agent_id,
        driver=driver or EchoDriver(),
        run_context=_make_run_context(),
        event_sink=event_sink or InMemoryEventSink(),
        system_prompt="You are an integration test agent.",
        memory=memory,
        tool_registry=tool_registry,
    )


# ---------------------------------------------------------------------------
# 1. Full lifecycle
# ---------------------------------------------------------------------------


class TestFullLifecycle:
    """End-to-end: initialize → process → close with all components."""

    @pytest.mark.anyio
    async def test_initialize_then_process_then_close(self) -> None:
        driver = EchoDriver()
        sink = InMemoryEventSink()
        memory = InMemoryMemoryProvider()

        rt = _make_runtime(driver=driver, event_sink=sink, memory=memory)

        # Initialize
        await rt.initialize()
        assert driver.session_started is True
        assert rt.is_closed is False

        # Process — driver echoes input back
        result = await rt.process("hello world")
        assert result is not None
        assert "hello world" in result

        # Close
        await rt.close()
        assert driver.session_closed is True
        assert rt.is_closed is True

    @pytest.mark.anyio
    async def test_process_before_initialize_raises(self) -> None:
        """process() without initialize() should raise (session_id assertion)."""
        rt = _make_runtime()
        with pytest.raises((AssertionError, Exception)):
            await rt.process("premature")


# ---------------------------------------------------------------------------
# 2. Tools registered
# ---------------------------------------------------------------------------


class TestToolsRegistered:
    """Registered tools are visible and injected into the driver turn."""

    @pytest.mark.anyio
    async def test_echo_tool_in_list_tools(self) -> None:
        registry = InMemoryToolRegistry()
        td = ToolDefinition(name="echo", description="Echo the input text")

        async def echo_handler(params: dict[str, Any]) -> ToolResult:
            return ToolResult(success=True, output=params.get("text", ""))

        registry.register(td, handler=echo_handler)

        rt = _make_runtime(tool_registry=registry)
        assert registry.has_tool("echo")
        assert len(registry.list_tools()) == 1
        assert registry.list_tools()[0].name == "echo"

    @pytest.mark.anyio
    async def test_tool_definitions_injected_into_turn(self) -> None:
        """Tool definitions must appear in the messages sent to the driver."""
        registry = InMemoryToolRegistry()
        td = ToolDefinition(name="lookup", description="Look up information")

        async def lookup_handler(params: dict[str, Any]) -> ToolResult:
            return ToolResult(success=True, output="found")

        registry.register(td, handler=lookup_handler)

        captured_requests: list[SendTurnRequest] = []

        class CapturingDriver(EchoDriver):
            async def send_turn(  # type: ignore[override]
                self, request: SendTurnRequest
            ) -> AsyncIterator[AgentEvent]:
                captured_requests.append(request)
                async for event in super().send_turn(request):
                    yield event

        rt = _make_runtime(
            driver=CapturingDriver(),
            tool_registry=registry,
        )
        await rt.initialize()
        await rt.process("use a tool please")

        assert len(captured_requests) == 1
        # Tools are injected as a system message at position 0
        messages = captured_requests[0].messages
        system_messages = [m for m in messages if m.get("role") == "system"]
        tool_content = " ".join(m.get("content", "") for m in system_messages)
        assert "lookup" in tool_content

    @pytest.mark.anyio
    async def test_multiple_tools_all_listed(self) -> None:
        registry = InMemoryToolRegistry()
        for name in ("tool_a", "tool_b", "tool_c"):
            registry.register(
                ToolDefinition(name=name, description=f"Does {name}"),
                handler=lambda p: ToolResult(success=True, output="ok"),
            )
        assert len(registry.list_tools()) == 3
        names = {t.name for t in registry.list_tools()}
        assert names == {"tool_a", "tool_b", "tool_c"}


# ---------------------------------------------------------------------------
# 3. Memory works
# ---------------------------------------------------------------------------


class TestMemoryIntegration:
    """Memory provider's save_turn is called for every process() invocation."""

    @pytest.mark.anyio
    async def test_save_turn_called_once_per_process(self) -> None:
        memory = InMemoryMemoryProvider()
        rt = _make_runtime(memory=memory)
        await rt.initialize()
        await rt.process("first input")

        assert len(memory._store) > 0
        all_messages: list = []
        for msgs in memory._store.values():
            all_messages.extend(msgs)
        assert len(all_messages) > 0

    @pytest.mark.anyio
    async def test_save_turn_called_for_each_process_invocation(self) -> None:
        """Two process() calls → two save_turn accumulations in the store."""
        memory = InMemoryMemoryProvider()
        rt = _make_runtime(memory=memory)
        await rt.initialize()

        await rt.process("first")
        count_after_one = sum(len(v) for v in memory._store.values())

        await rt.process("second")
        count_after_two = sum(len(v) for v in memory._store.values())

        assert count_after_two > count_after_one

    @pytest.mark.anyio
    async def test_memory_context_prepended_to_messages(self) -> None:
        """Memory context messages must be prepended before each turn."""
        memory = InMemoryMemoryProvider()
        # Seed memory with a prior turn
        ctx = _make_run_context()
        await memory.save_turn(
            [{"role": "assistant", "content": "prior context"}],
            ctx,
        )

        captured: list[SendTurnRequest] = []

        class CapturingDriver(EchoDriver):
            async def send_turn(  # type: ignore[override]
                self, request: SendTurnRequest
            ) -> AsyncIterator[AgentEvent]:
                captured.append(request)
                async for event in super().send_turn(request):
                    yield event

        rt = AgentRuntime(
            agent_id="mem-agent",
            driver=CapturingDriver(),
            run_context=ctx,
            event_sink=InMemoryEventSink(),
            memory=memory,
        )
        await rt.initialize()
        await rt.process("new input")

        assert len(captured) == 1
        messages = captured[0].messages
        contents = [m.get("content", "") for m in messages]
        assert "prior context" in contents


# ---------------------------------------------------------------------------
# 4. Events emitted
# ---------------------------------------------------------------------------


class TestEventsEmitted:
    """Verify canonical events are published in the correct sequence."""

    @pytest.mark.anyio
    async def test_agent_initialized_emitted(self) -> None:
        sink = InMemoryEventSink()
        rt = _make_runtime(event_sink=sink)
        await rt.initialize()

        types = [e.type for e in sink.events]
        assert EventType.AGENT_INITIALIZED.value in types

    @pytest.mark.anyio
    async def test_turn_started_and_completed_emitted(self) -> None:
        sink = InMemoryEventSink()
        rt = _make_runtime(event_sink=sink)
        await rt.initialize()
        await rt.process("trigger events")

        types = [e.type for e in sink.events]
        assert EventType.AGENT_TURN_STARTED.value in types
        assert EventType.AGENT_TURN_COMPLETED.value in types

    @pytest.mark.anyio
    async def test_agent_closed_emitted(self) -> None:
        sink = InMemoryEventSink()
        rt = _make_runtime(event_sink=sink)
        await rt.initialize()
        await rt.close()

        types = [e.type for e in sink.events]
        assert EventType.AGENT_CLOSED.value in types

    @pytest.mark.anyio
    async def test_full_event_sequence(self) -> None:
        """Complete lifecycle emits events in the right order."""
        sink = InMemoryEventSink()
        rt = _make_runtime(event_sink=sink)

        await rt.initialize()
        await rt.process("event sequence test")
        await rt.close()

        types = [e.type for e in sink.events]
        # Verify all four canonical lifecycle events are present
        assert EventType.AGENT_INITIALIZED.value in types
        assert EventType.AGENT_TURN_STARTED.value in types
        assert EventType.AGENT_TURN_COMPLETED.value in types
        assert EventType.AGENT_CLOSED.value in types

        # Verify ordering: INITIALIZED before TURN_STARTED before TURN_COMPLETED before CLOSED
        idx_init = types.index(EventType.AGENT_INITIALIZED.value)
        idx_started = types.index(EventType.AGENT_TURN_STARTED.value)
        idx_completed = types.index(EventType.AGENT_TURN_COMPLETED.value)
        idx_closed = types.index(EventType.AGENT_CLOSED.value)

        assert idx_init < idx_started < idx_completed < idx_closed

    @pytest.mark.anyio
    async def test_memory_events_emitted_when_memory_present(self) -> None:
        sink = InMemoryEventSink()
        memory = InMemoryMemoryProvider()
        rt = _make_runtime(event_sink=sink, memory=memory)

        await rt.initialize()
        await rt.process("memory event test")

        types = [e.type for e in sink.events]
        assert EventType.AGENT_MEMORY_LOADED.value in types
        # AGENT_MEMORY_SAVED only emitted in close() for PersistableMemory
        assert EventType.AGENT_MEMORY_SAVED.value not in types

    @pytest.mark.anyio
    async def test_events_carry_agent_id_payload(self) -> None:
        sink = InMemoryEventSink()
        rt = _make_runtime(event_sink=sink, agent_id="payload-agent")
        await rt.initialize()

        init_events = [
            e for e in sink.events
            if e.type == EventType.AGENT_INITIALIZED.value
        ]
        assert len(init_events) == 1
        assert init_events[0].get_payload("agent_id") == "payload-agent"


# ---------------------------------------------------------------------------
# 5. Protocol satisfaction
# ---------------------------------------------------------------------------


class TestProtocolSatisfaction:
    """AgentRuntime satisfies all three runtime_checkable agent protocols."""

    def test_satisfies_workflow_agent(self) -> None:
        rt = _make_runtime()
        assert isinstance(rt, WorkflowAgent)

    def test_satisfies_conversational_agent(self) -> None:
        rt = _make_runtime()
        assert isinstance(rt, ConversationalAgent)

    def test_satisfies_deliberation_agent(self) -> None:
        rt = _make_runtime()
        assert isinstance(rt, DeliberationAgent)

    def test_satisfies_all_three_simultaneously(self) -> None:
        rt = _make_runtime()
        assert isinstance(rt, WorkflowAgent)
        assert isinstance(rt, ConversationalAgent)
        assert isinstance(rt, DeliberationAgent)


# ---------------------------------------------------------------------------
# 6. Closed agent raises AgentClosedError
# ---------------------------------------------------------------------------


class TestClosedAgentRaises:
    """After close(), all turn methods must raise AgentClosedError."""

    @pytest.mark.anyio
    async def test_process_raises_after_close(self) -> None:
        rt = _make_runtime()
        await rt.initialize()
        await rt.close()

        with pytest.raises(AgentClosedError):
            await rt.process("should fail")

    @pytest.mark.anyio
    async def test_reply_raises_after_close(self) -> None:
        rt = _make_runtime()
        await rt.initialize()
        await rt.close()

        with pytest.raises(AgentClosedError):
            await rt.reply("should fail", {})

    @pytest.mark.anyio
    async def test_contribute_raises_after_close(self) -> None:
        rt = _make_runtime()
        await rt.initialize()
        await rt.close()

        with pytest.raises(AgentClosedError):
            await rt.contribute("some topic")

    @pytest.mark.anyio
    async def test_is_closed_flag_set(self) -> None:
        rt = _make_runtime()
        assert rt.is_closed is False
        await rt.initialize()
        assert rt.is_closed is False
        await rt.close()
        assert rt.is_closed is True
