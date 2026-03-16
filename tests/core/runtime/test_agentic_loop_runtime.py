"""Tests for AgenticLoopRuntime and agentic loop helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from miniautogen.core.contracts.agentic_loop import (
    AgenticLoopState,
    ConversationPolicy,
    RouterDecision,
)
from miniautogen.core.contracts.coordination import (
    AgenticLoopPlan,
    CoordinationKind,
    CoordinationMode,
)
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.runtime.agentic_loop import detect_stagnation, should_stop_loop
from miniautogen.core.runtime.agentic_loop_runtime import AgenticLoopRuntime
from miniautogen.core.runtime.pipeline_runner import PipelineRunner


# ---------- Existing helper tests ----------


def test_detect_stagnation_when_same_agent_repeats_without_change() -> None:
    history = [
        RouterDecision(
            current_state_summary="A",
            missing_information="B",
            next_agent="QA",
            terminate=False,
            stagnation_risk=0.1,
        ),
        RouterDecision(
            current_state_summary="A",
            missing_information="B",
            next_agent="QA",
            terminate=False,
            stagnation_risk=0.1,
        ),
    ]
    assert detect_stagnation(history, window=2) is True


def test_should_stop_loop_when_max_turns_is_reached() -> None:
    policy = ConversationPolicy(max_turns=3, timeout_seconds=120.0)
    state = AgenticLoopState(active_agent="Planner", turn_count=3)
    stop, reason = should_stop_loop(state, policy)
    assert stop is True
    assert reason == "max_turns"


# ---------- Test helpers ----------


def _make_context(run_id: str = "run-1") -> RunContext:
    return RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id="corr-1",
        input_payload="initial-input",
    )


class _FakeRouter:
    """Router that returns decisions from a predefined list."""

    def __init__(self, decisions: list[RouterDecision]) -> None:
        self._decisions = list(decisions)
        self._call_count = 0
        self.received_histories: list[list[dict[str, str]]] = []

    async def route(self, conversation_history: list[dict[str, str]]) -> RouterDecision:
        self.received_histories.append(list(conversation_history))
        if self._call_count < len(self._decisions):
            decision = self._decisions[self._call_count]
        else:
            decision = RouterDecision(
                current_state_summary="done",
                missing_information="none",
                terminate=True,
            )
        self._call_count += 1
        return decision


class _FakeAgent:
    """Agent that replies with a predictable message."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.call_count = 0

    async def reply(self, last_message: str, context: dict[str, Any]) -> str:
        self.call_count += 1
        return f"{self.name}-reply-{self.call_count}"


class _FailingAgent:
    """Agent whose reply always raises."""

    async def reply(self, last_message: str, context: dict[str, Any]) -> str:
        raise RuntimeError("agent exploded")


class _FailingRouter:
    """Router whose route method always raises."""

    async def route(self, conversation_history: list[dict[str, str]]) -> RouterDecision:
        raise RuntimeError("router exploded")


# ---------- AgenticLoopRuntime tests ----------


def test_runtime_satisfies_coordination_mode_protocol() -> None:
    """AgenticLoopRuntime must satisfy the CoordinationMode protocol."""
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    runtime = AgenticLoopRuntime(runner=runner)
    assert isinstance(runtime, CoordinationMode)
    assert runtime.kind == CoordinationKind.AGENTIC_LOOP


@pytest.mark.asyncio
async def test_simple_2_turn_conversation() -> None:
    """Router selects agent_a, then agent_b, then terminates."""
    router = _FakeRouter([
        RouterDecision(
            current_state_summary="start",
            missing_information="need a",
            next_agent="agent_a",
        ),
        RouterDecision(
            current_state_summary="got a",
            missing_information="need b",
            next_agent="agent_b",
        ),
        RouterDecision(
            current_state_summary="done",
            missing_information="none",
            terminate=True,
        ),
    ])
    agent_a = _FakeAgent("a")
    agent_b = _FakeAgent("b")

    registry: dict[str, Any] = {
        "router": router,
        "agent_a": agent_a,
        "agent_b": agent_b,
    }
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    runtime = AgenticLoopRuntime(runner=runner, agent_registry=registry)

    plan = AgenticLoopPlan(
        router_agent="router",
        participants=["agent_a", "agent_b"],
        policy=ConversationPolicy(max_turns=10),
    )
    result = await runtime.run(agents=[], context=_make_context(), plan=plan)

    assert result.status == "finished"
    assert agent_a.call_count == 1
    assert agent_b.call_count == 1
    assert len(result.output) == 2
    assert result.metadata["stop_reason"] == "router_terminated"


@pytest.mark.asyncio
async def test_max_turns_enforcement() -> None:
    """Loop stops at max_turns even if router never terminates."""
    decisions = [
        RouterDecision(
            current_state_summary=f"turn-{i}",
            missing_information=f"working-{i}",
            next_agent="agent_a",
        )
        for i in range(20)
    ]
    router = _FakeRouter(decisions)
    agent_a = _FakeAgent("a")

    registry: dict[str, Any] = {"router": router, "agent_a": agent_a}
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    runtime = AgenticLoopRuntime(runner=runner, agent_registry=registry)

    plan = AgenticLoopPlan(
        router_agent="router",
        participants=["agent_a"],
        policy=ConversationPolicy(max_turns=3),
    )
    result = await runtime.run(agents=[], context=_make_context(), plan=plan)

    assert result.status == "finished"
    assert agent_a.call_count == 3
    assert result.metadata["stop_reason"] == "max_turns"


@pytest.mark.asyncio
async def test_stagnation_detection_stops_loop() -> None:
    """Loop stops when stagnation is detected (same routing repeated)."""
    decisions = [
        RouterDecision(
            current_state_summary="stuck",
            missing_information="same",
            next_agent="agent_a",
        )
        for _ in range(10)
    ]
    router = _FakeRouter(decisions)
    agent_a = _FakeAgent("a")

    registry: dict[str, Any] = {"router": router, "agent_a": agent_a}
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    runtime = AgenticLoopRuntime(runner=runner, agent_registry=registry)

    plan = AgenticLoopPlan(
        router_agent="router",
        participants=["agent_a"],
        policy=ConversationPolicy(max_turns=10, stagnation_window=2),
    )
    result = await runtime.run(agents=[], context=_make_context(), plan=plan)

    assert result.status == "finished"
    assert result.metadata["stop_reason"] == "stagnation"
    # Stagnation detected after window identical decisions; agent called once
    # before the second identical decision triggers stagnation
    assert agent_a.call_count >= 1


@pytest.mark.asyncio
async def test_router_terminates_immediately() -> None:
    """Router terminates on first call — no agents invoked."""
    router = _FakeRouter([
        RouterDecision(
            current_state_summary="done",
            missing_information="none",
            terminate=True,
        ),
    ])
    agent_a = _FakeAgent("a")

    registry: dict[str, Any] = {"router": router, "agent_a": agent_a}
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    runtime = AgenticLoopRuntime(runner=runner, agent_registry=registry)

    plan = AgenticLoopPlan(
        router_agent="router",
        participants=["agent_a"],
        policy=ConversationPolicy(max_turns=10),
    )
    result = await runtime.run(agents=[], context=_make_context(), plan=plan)

    assert result.status == "finished"
    assert agent_a.call_count == 0
    assert result.metadata["stop_reason"] == "router_terminated"


@pytest.mark.asyncio
async def test_unknown_participant_returns_error() -> None:
    """Referencing an unknown participant returns failed result."""
    router = _FakeRouter([])
    registry: dict[str, Any] = {"router": router}
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    runtime = AgenticLoopRuntime(runner=runner, agent_registry=registry)

    plan = AgenticLoopPlan(
        router_agent="router",
        participants=["nonexistent_agent"],
        policy=ConversationPolicy(max_turns=5),
    )
    result = await runtime.run(agents=[], context=_make_context(), plan=plan)

    assert result.status == "failed"
    assert "nonexistent_agent" in result.error


@pytest.mark.asyncio
async def test_unknown_router_returns_error() -> None:
    """Referencing an unknown router returns failed result."""
    agent_a = _FakeAgent("a")
    registry: dict[str, Any] = {"agent_a": agent_a}
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    runtime = AgenticLoopRuntime(runner=runner, agent_registry=registry)

    plan = AgenticLoopPlan(
        router_agent="missing_router",
        participants=["agent_a"],
        policy=ConversationPolicy(max_turns=5),
    )
    result = await runtime.run(agents=[], context=_make_context(), plan=plan)

    assert result.status == "failed"
    assert "missing_router" in result.error


@pytest.mark.asyncio
async def test_agent_failure_returns_error() -> None:
    """Agent raising an exception returns failed result."""
    router = _FakeRouter([
        RouterDecision(
            current_state_summary="start",
            missing_information="need reply",
            next_agent="failing_agent",
        ),
    ])
    failing_agent = _FailingAgent()

    registry: dict[str, Any] = {"router": router, "failing_agent": failing_agent}
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    runtime = AgenticLoopRuntime(runner=runner, agent_registry=registry)

    plan = AgenticLoopPlan(
        router_agent="router",
        participants=["failing_agent"],
        policy=ConversationPolicy(max_turns=5),
    )
    result = await runtime.run(agents=[], context=_make_context(), plan=plan)

    assert result.status == "failed"
    assert "agent exploded" in result.error


@pytest.mark.asyncio
async def test_events_emitted_during_loop() -> None:
    """Correct events are emitted during the agentic loop."""
    router = _FakeRouter([
        RouterDecision(
            current_state_summary="start",
            missing_information="need a",
            next_agent="agent_a",
        ),
        RouterDecision(
            current_state_summary="done",
            missing_information="none",
            terminate=True,
        ),
    ])
    agent_a = _FakeAgent("a")

    registry: dict[str, Any] = {"router": router, "agent_a": agent_a}
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    runtime = AgenticLoopRuntime(runner=runner, agent_registry=registry)

    plan = AgenticLoopPlan(
        router_agent="router",
        participants=["agent_a"],
        policy=ConversationPolicy(max_turns=10),
    )
    await runtime.run(agents=[], context=_make_context(), plan=plan)

    event_types = [e.type for e in event_sink.events]
    assert "agentic_loop_started" in event_types
    assert "router_decision" in event_types
    assert "agent_replied" in event_types
    assert "agentic_loop_stopped" in event_types


@pytest.mark.asyncio
async def test_conversation_history_grows_and_passed_to_router() -> None:
    """Conversation history grows with each reply and is passed to router."""
    router = _FakeRouter([
        RouterDecision(
            current_state_summary="start",
            missing_information="need a",
            next_agent="agent_a",
        ),
        RouterDecision(
            current_state_summary="got a",
            missing_information="need more",
            next_agent="agent_a",
        ),
        RouterDecision(
            current_state_summary="done",
            missing_information="none",
            terminate=True,
        ),
    ])
    agent_a = _FakeAgent("a")

    registry: dict[str, Any] = {"router": router, "agent_a": agent_a}
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    runtime = AgenticLoopRuntime(runner=runner, agent_registry=registry)

    plan = AgenticLoopPlan(
        router_agent="router",
        participants=["agent_a"],
        policy=ConversationPolicy(max_turns=10),
        initial_message="Hello, start working",
    )
    result = await runtime.run(agents=[], context=_make_context(), plan=plan)

    # First router call should have just the initial message
    assert len(router.received_histories[0]) == 1
    assert router.received_histories[0][0]["sender"] == "system"

    # Second router call should have initial + first reply
    assert len(router.received_histories[1]) == 2

    # Third router call should have initial + two replies
    assert len(router.received_histories[2]) == 3


@pytest.mark.asyncio
async def test_result_contains_conversation_history_as_output() -> None:
    """RunResult.output is the full conversation history."""
    router = _FakeRouter([
        RouterDecision(
            current_state_summary="start",
            missing_information="need a",
            next_agent="agent_a",
        ),
        RouterDecision(
            current_state_summary="done",
            missing_information="none",
            terminate=True,
        ),
    ])
    agent_a = _FakeAgent("a")

    registry: dict[str, Any] = {"router": router, "agent_a": agent_a}
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    runtime = AgenticLoopRuntime(runner=runner, agent_registry=registry)

    plan = AgenticLoopPlan(
        router_agent="router",
        participants=["agent_a"],
        policy=ConversationPolicy(max_turns=10),
        initial_message="Start",
    )
    result = await runtime.run(agents=[], context=_make_context(), plan=plan)

    assert result.status == "finished"
    history = result.output
    assert isinstance(history, list)
    # initial message + 1 agent reply
    assert len(history) == 2
    assert history[0] == {"sender": "system", "content": "Start"}
    assert history[1]["sender"] == "agent_a"
    assert "a-reply" in history[1]["content"]


@pytest.mark.asyncio
async def test_timeout_enforcement() -> None:
    """Loop stops when timeout_seconds is exceeded."""
    import asyncio

    class _SlowAgent:
        async def reply(self, last_message: str, context: dict[str, Any]) -> str:
            await asyncio.sleep(5.0)  # Way longer than timeout
            return "slow-reply"

    router = _FakeRouter([
        RouterDecision(
            current_state_summary="start",
            missing_information="need a",
            next_agent="slow_agent",
        )
        for _ in range(10)
    ])
    slow_agent = _SlowAgent()

    registry: dict[str, Any] = {"router": router, "slow_agent": slow_agent}
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    runtime = AgenticLoopRuntime(runner=runner, agent_registry=registry)

    plan = AgenticLoopPlan(
        router_agent="router",
        participants=["slow_agent"],
        policy=ConversationPolicy(max_turns=10, timeout_seconds=0.1),  # Very short timeout
    )
    result = await runtime.run(agents=[], context=_make_context(), plan=plan)

    assert result.status == "finished"
    assert result.metadata["stop_reason"] == "timeout"


@pytest.mark.asyncio
async def test_router_selecting_agent_outside_participants_returns_error() -> None:
    """Router selecting an agent not in the plan's participants list should fail."""
    secret_agent = _FakeAgent("secret")
    agent_a = _FakeAgent("a")
    router = _FakeRouter([
        RouterDecision(
            current_state_summary="start",
            missing_information="need input",
            next_agent="secret",
            stagnation_risk=0.0,
        ),
    ])

    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)
    runtime = AgenticLoopRuntime(
        runner=runner,
        agent_registry={"agent_a": agent_a, "secret": secret_agent, "router": router},
    )

    plan = AgenticLoopPlan(
        participants=["agent_a"],  # "secret" is NOT a participant
        router_agent="router",
        initial_message="go",
    )
    ctx = _make_context()
    result = await runtime.run(agents=[], context=ctx, plan=plan)

    assert result.status == "failed"
    assert "secret" in result.error
    assert "not a declared participant" in result.error
    assert secret_agent.call_count == 0  # secret agent was NOT called


@pytest.mark.asyncio
async def test_timeout_emits_run_timed_out_event() -> None:
    """When the loop times out, a RUN_TIMED_OUT event must be emitted."""
    import asyncio

    class _SlowAgent:
        async def reply(self, last_message: str, context: dict[str, Any]) -> str:
            await asyncio.sleep(5.0)
            return "slow-reply"

    router = _FakeRouter([
        RouterDecision(
            current_state_summary="start",
            missing_information="need a",
            next_agent="slow_agent",
        )
        for _ in range(10)
    ])
    slow_agent = _SlowAgent()

    registry: dict[str, Any] = {"router": router, "slow_agent": slow_agent}
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    runtime = AgenticLoopRuntime(runner=runner, agent_registry=registry)

    plan = AgenticLoopPlan(
        router_agent="router",
        participants=["slow_agent"],
        policy=ConversationPolicy(max_turns=10, timeout_seconds=0.1),
    )
    result = await runtime.run(agents=[], context=_make_context(), plan=plan)

    assert result.status == "finished"
    assert result.metadata["stop_reason"] == "timeout"

    event_types = [e.type for e in event_sink.events]
    assert "run_timed_out" in event_types

    timed_out_events = [e for e in event_sink.events if e.type == "run_timed_out"]
    assert len(timed_out_events) == 1
    assert timed_out_events[0].payload["timeout_seconds"] == 0.1
