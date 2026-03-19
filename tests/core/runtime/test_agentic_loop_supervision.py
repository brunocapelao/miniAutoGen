"""Integration tests for supervision in AgenticLoopRuntime.

Verifies that AgenticLoopRuntime correctly integrates with FlowSupervisor to
restart, stop, or escalate on agent.reply() failures -- while preserving
backward compatibility for plans without supervision configured.
Router failures are NOT supervised (routing failures = PERMANENT).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from miniautogen.core.contracts.agentic_loop import ConversationPolicy, RouterDecision
from miniautogen.core.contracts.coordination import AgenticLoopPlan
from miniautogen.core.contracts.enums import RunStatus, SupervisionStrategy
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.supervision import StepSupervision
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.events.types import EventType
from miniautogen.core.runtime.agentic_loop_runtime import AgenticLoopRuntime
from miniautogen.core.runtime.pipeline_runner import PipelineRunner

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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

    async def route(
        self, conversation_history: list[dict[str, str]]
    ) -> RouterDecision:
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


class _CountingReplyAgent:
    """Agent that fails N times then succeeds."""

    def __init__(
        self, name: str, fail_times: int, exc: Exception
    ) -> None:
        self.name = name
        self._fail_times = fail_times
        self._exc = exc
        self.call_count = 0

    async def reply(self, last_message: str, context: dict[str, Any]) -> str:
        self.call_count += 1
        if self.call_count <= self._fail_times:
            raise self._exc
        return f"{self.name}-recovered-{self.call_count}"


class _AlwaysFailAgent:
    """Agent whose reply always raises."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc
        self.call_count = 0

    async def reply(self, last_message: str, context: dict[str, Any]) -> str:
        self.call_count += 1
        raise self._exc


def _one_turn_plan(
    supervision: StepSupervision | None = None,
) -> AgenticLoopPlan:
    return AgenticLoopPlan(
        router_agent="router",
        participants=["agent_a"],
        policy=ConversationPolicy(max_turns=5, timeout_seconds=10.0),
        default_supervision=supervision,
    )


def _one_turn_router() -> _FakeRouter:
    return _FakeRouter([
        RouterDecision(
            current_state_summary="start",
            missing_information="need a",
            next_agent="agent_a",
        ),
    ])


# ---------------------------------------------------------------------------
# Tests: Backward compatibility
# ---------------------------------------------------------------------------


class TestAgenticLoopBackwardCompatibility:
    """No supervision = fail-fast (existing behaviour preserved)."""

    @pytest.mark.asyncio
    async def test_agent_failure_without_supervision_fails_fast(self) -> None:
        router = _one_turn_router()
        agent = _AlwaysFailAgent(RuntimeError("boom"))
        registry: dict[str, Any] = {
            "router": router, "agent_a": agent,
        }
        event_sink = InMemoryEventSink()
        runner = PipelineRunner(event_sink=event_sink)
        runtime = AgenticLoopRuntime(runner=runner, agent_registry=registry)

        plan = _one_turn_plan(supervision=None)
        result = await runtime.run(
            agents=[], context=_make_context(), plan=plan,
        )

        assert result.status == RunStatus.FAILED
        assert "boom" in (result.error or "")
        assert agent.call_count == 1


# ---------------------------------------------------------------------------
# Tests: Reply supervision with restarts
# ---------------------------------------------------------------------------


class TestAgenticLoopReplySupervision:
    """Supervision restarts on agent.reply() failures."""

    @pytest.mark.asyncio
    async def test_transient_reply_failure_restarts_and_succeeds(self) -> None:
        router = _one_turn_router()
        agent = _CountingReplyAgent(
            "agent_a", fail_times=2, exc=ConnectionError("transient"),
        )
        registry: dict[str, Any] = {
            "router": router, "agent_a": agent,
        }
        event_sink = InMemoryEventSink()
        runner = PipelineRunner(event_sink=event_sink)
        runtime = AgenticLoopRuntime(runner=runner, agent_registry=registry)

        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESTART,
            max_restarts=3,
            restart_window_seconds=60.0,
        )
        plan = _one_turn_plan(supervision=supervision)
        result = await runtime.run(
            agents=[], context=_make_context(), plan=plan,
        )

        assert result.status == RunStatus.FINISHED
        assert agent.call_count == 3  # 2 failures + 1 success

    @pytest.mark.asyncio
    async def test_permanent_reply_error_stops_immediately(self) -> None:
        router = _one_turn_router()
        agent = _AlwaysFailAgent(KeyError("missing"))
        registry: dict[str, Any] = {
            "router": router, "agent_a": agent,
        }
        event_sink = InMemoryEventSink()
        runner = PipelineRunner(event_sink=event_sink)
        runtime = AgenticLoopRuntime(runner=runner, agent_registry=registry)

        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESTART,
            max_restarts=5,
        )
        plan = _one_turn_plan(supervision=supervision)
        result = await runtime.run(
            agents=[], context=_make_context(), plan=plan,
        )

        assert result.status == RunStatus.FAILED
        assert agent.call_count == 1

    @pytest.mark.asyncio
    async def test_always_failing_agent_exhausts_budget(self) -> None:
        router = _one_turn_router()
        agent = _AlwaysFailAgent(ConnectionError("transient"))
        registry: dict[str, Any] = {
            "router": router, "agent_a": agent,
        }
        event_sink = InMemoryEventSink()
        runner = PipelineRunner(event_sink=event_sink)
        runtime = AgenticLoopRuntime(runner=runner, agent_registry=registry)

        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESTART,
            max_restarts=2,
            restart_window_seconds=60.0,
        )
        plan = _one_turn_plan(supervision=supervision)
        result = await runtime.run(
            agents=[], context=_make_context(), plan=plan,
        )

        assert result.status == RunStatus.FAILED
        # 1 initial + 2 restarts = 3 total, then escalate
        assert agent.call_count == 3


# ---------------------------------------------------------------------------
# Tests: Router NOT supervised
# ---------------------------------------------------------------------------


class TestRouterNotSupervised:
    """Router failures are not supervised; they fail the loop immediately."""

    @pytest.mark.asyncio
    async def test_router_failure_not_supervised(self) -> None:
        class _FailingRouter:
            async def route(
                self, history: list[dict[str, str]]
            ) -> RouterDecision:
                raise RuntimeError("router exploded")

        agent = _FakeAgent("agent_a")
        registry: dict[str, Any] = {
            "router": _FailingRouter(), "agent_a": agent,
        }
        event_sink = InMemoryEventSink()
        runner = PipelineRunner(event_sink=event_sink)
        runtime = AgenticLoopRuntime(runner=runner, agent_registry=registry)

        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESTART,
            max_restarts=5,
        )
        plan = _one_turn_plan(supervision=supervision)
        result = await runtime.run(
            agents=[], context=_make_context(), plan=plan,
        )

        assert result.status == RunStatus.FAILED
        assert "router exploded" in (result.error or "")


# ---------------------------------------------------------------------------
# Tests: Retry events
# ---------------------------------------------------------------------------


class TestAgenticLoopRetryEvents:
    """Verify supervision events are emitted on retry."""

    @pytest.mark.asyncio
    async def test_retry_succeeded_event_emitted(self) -> None:
        router = _one_turn_router()
        agent = _CountingReplyAgent(
            "agent_a", fail_times=1, exc=ConnectionError("flaky"),
        )
        registry: dict[str, Any] = {
            "router": router, "agent_a": agent,
        }
        event_sink = InMemoryEventSink()
        runner = PipelineRunner(event_sink=event_sink)
        runtime = AgenticLoopRuntime(runner=runner, agent_registry=registry)

        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESTART,
            max_restarts=3,
            restart_window_seconds=60.0,
        )
        plan = _one_turn_plan(supervision=supervision)
        result = await runtime.run(
            agents=[], context=_make_context(), plan=plan,
        )

        assert result.status == RunStatus.FINISHED
        retry_events = [
            e for e in event_sink.events
            if e.type == EventType.SUPERVISION_RETRY_SUCCEEDED.value
        ]
        assert len(retry_events) >= 1
