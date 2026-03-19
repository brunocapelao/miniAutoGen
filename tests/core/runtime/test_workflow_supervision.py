"""Integration tests for supervision in WorkflowRuntime.

Verifies that WorkflowRuntime correctly integrates with FlowSupervisor to
restart, stop, or escalate on step failures -- while preserving backward
compatibility for workflows without supervision configured.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from miniautogen.core.contracts.coordination import WorkflowPlan, WorkflowStep
from miniautogen.core.contracts.enums import RunStatus, SupervisionStrategy
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.supervision import StepSupervision
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.events.types import EventType
from miniautogen.core.runtime.pipeline_runner import PipelineRunner
from miniautogen.core.runtime.workflow_runtime import WorkflowRuntime

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context(run_id: str = "run-1", input_payload: Any = "input") -> RunContext:
    return RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id="corr-1",
        input_payload=input_payload,
    )


class _CountingAgent:
    """Agent that fails N times with a given exception, then succeeds."""

    def __init__(self, fail_times: int, exc: Exception, success_value: str = "ok") -> None:
        self._fail_times = fail_times
        self._exc = exc
        self._success_value = success_value
        self.call_count = 0

    async def process(self, input_data: Any) -> Any:
        self.call_count += 1
        if self.call_count <= self._fail_times:
            raise self._exc
        return self._success_value


class _AlwaysFailAgent:
    """Agent that always raises the given exception."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc
        self.call_count = 0

    async def process(self, input_data: Any) -> Any:
        self.call_count += 1
        raise self._exc


class _OkAgent:
    """Agent that always succeeds."""

    def __init__(self, value: str = "ok") -> None:
        self._value = value

    async def process(self, input_data: Any) -> Any:
        return self._value


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSequentialSupervisionRestarts:
    """Test restart behaviour in _run_sequential."""

    @pytest.mark.asyncio
    async def test_transient_error_restarts_up_to_max_then_escalates(self) -> None:
        """Step with max_restarts=2 restarts transient errors 2 times then escalates."""
        agent = _AlwaysFailAgent(ConnectionError("transient"))
        registry: dict[str, Any] = {"a": agent}
        event_sink = InMemoryEventSink()
        runner = PipelineRunner(event_sink=event_sink)
        runtime = WorkflowRuntime(runner=runner, agent_registry=registry)

        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESTART,
            max_restarts=2,
            restart_window_seconds=60.0,
        )
        plan = WorkflowPlan(
            steps=[WorkflowStep(component_name="step1", agent_id="a", supervision=supervision)],
        )

        result = await runtime.run(agents=[], context=_make_context(), plan=plan)

        assert result.status == RunStatus.FAILED
        # 1 initial + 2 restarts = 3 calls total, then escalate on 3rd failure
        assert agent.call_count == 3

    @pytest.mark.asyncio
    async def test_restart_succeeds_after_transient_failures(self) -> None:
        """Step fails twice then succeeds on third attempt."""
        agent = _CountingAgent(
            fail_times=2, exc=ConnectionError("flaky"), success_value="recovered",
        )
        registry: dict[str, Any] = {"a": agent}
        event_sink = InMemoryEventSink()
        runner = PipelineRunner(event_sink=event_sink)
        runtime = WorkflowRuntime(runner=runner, agent_registry=registry)

        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESTART,
            max_restarts=3,
            restart_window_seconds=60.0,
        )
        plan = WorkflowPlan(
            steps=[WorkflowStep(component_name="step1", agent_id="a", supervision=supervision)],
        )

        result = await runtime.run(agents=[], context=_make_context(), plan=plan)

        assert result.status == RunStatus.FINISHED
        assert result.output == "recovered"
        assert agent.call_count == 3


class TestPermanentErrorForcesStop:
    """PERMANENT errors force STOP regardless of configured strategy."""

    @pytest.mark.asyncio
    async def test_permanent_error_forces_stop_sequential(self) -> None:
        agent = _AlwaysFailAgent(KeyError("missing-key"))
        registry: dict[str, Any] = {"a": agent}
        event_sink = InMemoryEventSink()
        runner = PipelineRunner(event_sink=event_sink)
        runtime = WorkflowRuntime(runner=runner, agent_registry=registry)

        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESTART,
            max_restarts=5,
        )
        plan = WorkflowPlan(
            steps=[WorkflowStep(component_name="step1", agent_id="a", supervision=supervision)],
        )

        result = await runtime.run(agents=[], context=_make_context(), plan=plan)

        assert result.status == RunStatus.FAILED
        # PERMANENT forces STOP on first failure -- no restarts
        assert agent.call_count == 1


class TestCircuitBreaker:
    """Circuit breaker opens at threshold."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_at_threshold(self) -> None:
        """Flow-level circuit breaker triggers when total failures reach threshold."""
        # Use a very low flow circuit breaker threshold (2)
        # and a high max_restarts so step-level never exhausts budget
        agent = _AlwaysFailAgent(ConnectionError("transient"))
        registry: dict[str, Any] = {"a": agent}
        event_sink = InMemoryEventSink()
        runner = PipelineRunner(event_sink=event_sink)
        runtime = WorkflowRuntime(runner=runner, agent_registry=registry)

        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESTART,
            max_restarts=100,
            circuit_breaker_threshold=100,
            restart_window_seconds=60.0,
        )
        plan = WorkflowPlan(
            steps=[WorkflowStep(component_name="step1", agent_id="a", supervision=supervision)],
        )

        result = await runtime.run(agents=[], context=_make_context(), plan=plan)

        assert result.status == RunStatus.FAILED
        # Verify circuit breaker event was emitted
        circuit_events = [
            e for e in event_sink.events
            if e.type == EventType.SUPERVISION_CIRCUIT_OPENED.value
        ]
        assert len(circuit_events) >= 1


class TestBackwardCompatibility:
    """No supervision field = fail-fast (backward compatible)."""

    @pytest.mark.asyncio
    async def test_no_supervision_fails_fast_sequential(self) -> None:
        """Without supervision, a failing step immediately fails the workflow."""
        agent = _AlwaysFailAgent(RuntimeError("boom"))
        registry: dict[str, Any] = {"a": agent}
        event_sink = InMemoryEventSink()
        runner = PipelineRunner(event_sink=event_sink)
        runtime = WorkflowRuntime(runner=runner, agent_registry=registry)

        plan = WorkflowPlan(
            steps=[WorkflowStep(component_name="step1", agent_id="a")],
        )

        result = await runtime.run(agents=[], context=_make_context(), plan=plan)

        assert result.status == RunStatus.FAILED
        assert "boom" in (result.error or "")
        # Only called once -- no retry
        assert agent.call_count == 1

    @pytest.mark.asyncio
    async def test_no_supervision_fails_fast_fan_out(self) -> None:
        """Without supervision, a failing fan-out branch fails the workflow."""
        ok_agent = _OkAgent("fine")
        fail_agent = _AlwaysFailAgent(RuntimeError("branch-fail"))
        registry: dict[str, Any] = {"ok": ok_agent, "fail": fail_agent}
        event_sink = InMemoryEventSink()
        runner = PipelineRunner(event_sink=event_sink)
        runtime = WorkflowRuntime(runner=runner, agent_registry=registry)

        plan = WorkflowPlan(
            steps=[
                WorkflowStep(component_name="s1", agent_id="ok"),
                WorkflowStep(component_name="s2", agent_id="fail"),
            ],
            fan_out=True,
        )

        result = await runtime.run(agents=[], context=_make_context(), plan=plan)

        assert result.status == RunStatus.FAILED
        assert "branch-fail" in (result.error or "")
        assert fail_agent.call_count == 1


class TestFanOutSupervision:
    """Fan-out with different supervision strategies."""

    @pytest.mark.asyncio
    async def test_fan_out_branch_restarts_then_succeeds(self) -> None:
        """A fan-out branch that fails once then succeeds produces correct output."""
        ok_agent = _OkAgent("branch-a-ok")
        flaky_agent = _CountingAgent(
            fail_times=1, exc=ConnectionError("flaky"), success_value="branch-b-recovered"
        )
        registry: dict[str, Any] = {"ok": ok_agent, "flaky": flaky_agent}
        event_sink = InMemoryEventSink()
        runner = PipelineRunner(event_sink=event_sink)
        runtime = WorkflowRuntime(runner=runner, agent_registry=registry)

        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESTART,
            max_restarts=3,
            restart_window_seconds=60.0,
        )
        plan = WorkflowPlan(
            steps=[
                WorkflowStep(component_name="s1", agent_id="ok"),
                WorkflowStep(component_name="s2", agent_id="flaky", supervision=supervision),
            ],
            fan_out=True,
        )

        result = await runtime.run(agents=[], context=_make_context(), plan=plan)

        assert result.status == RunStatus.FINISHED
        assert isinstance(result.output, list)
        assert "branch-a-ok" in result.output
        assert "branch-b-recovered" in result.output

    @pytest.mark.asyncio
    async def test_fan_out_permanent_error_stops_branch(self) -> None:
        """A permanent error in a fan-out branch stops that branch immediately."""
        ok_agent = _OkAgent("ok")
        perm_agent = _AlwaysFailAgent(KeyError("perm-fail"))
        registry: dict[str, Any] = {"ok": ok_agent, "perm": perm_agent}
        event_sink = InMemoryEventSink()
        runner = PipelineRunner(event_sink=event_sink)
        runtime = WorkflowRuntime(runner=runner, agent_registry=registry)

        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESTART,
            max_restarts=5,
        )
        plan = WorkflowPlan(
            steps=[
                WorkflowStep(component_name="s1", agent_id="ok"),
                WorkflowStep(component_name="s2", agent_id="perm", supervision=supervision),
            ],
            fan_out=True,
        )

        result = await runtime.run(agents=[], context=_make_context(), plan=plan)

        assert result.status == RunStatus.FAILED
        assert perm_agent.call_count == 1


class TestRetrySucceededEvent:
    """SUPERVISION_RETRY_SUCCEEDED emitted after successful retry."""

    @pytest.mark.asyncio
    async def test_retry_succeeded_event_emitted(self) -> None:
        agent = _CountingAgent(fail_times=1, exc=ConnectionError("flaky"), success_value="ok")
        registry: dict[str, Any] = {"a": agent}
        event_sink = InMemoryEventSink()
        runner = PipelineRunner(event_sink=event_sink)
        runtime = WorkflowRuntime(runner=runner, agent_registry=registry)

        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESTART,
            max_restarts=3,
            restart_window_seconds=60.0,
        )
        plan = WorkflowPlan(
            steps=[WorkflowStep(component_name="step1", agent_id="a", supervision=supervision)],
        )

        result = await runtime.run(agents=[], context=_make_context(), plan=plan)

        assert result.status == RunStatus.FINISHED

        retry_events = [
            e for e in event_sink.events
            if e.type == EventType.SUPERVISION_RETRY_SUCCEEDED.value
        ]
        assert len(retry_events) == 1
        assert retry_events[0].get_payload("step_id") == "step1"
        assert retry_events[0].get_payload("total_attempts") == 2


class TestWorkflowStepDeserialization:
    """WorkflowStep deserialized without supervision field produces supervision=None."""

    def test_workflow_step_without_supervision_is_none(self) -> None:
        step = WorkflowStep(component_name="s1", agent_id="a")
        assert step.supervision is None

    def test_workflow_step_with_supervision(self) -> None:
        sup = StepSupervision(strategy=SupervisionStrategy.RESTART, max_restarts=2)
        step = WorkflowStep(component_name="s1", agent_id="a", supervision=sup)
        assert step.supervision is not None
        assert step.supervision.strategy == SupervisionStrategy.RESTART
        assert step.supervision.max_restarts == 2

    def test_workflow_plan_default_supervision_none(self) -> None:
        plan = WorkflowPlan(
            steps=[WorkflowStep(component_name="s1", agent_id="a")],
        )
        assert plan.default_supervision is None


class TestDefaultSupervisionFromPlan:
    """Plan-level default_supervision applies to steps without step-level supervision."""

    @pytest.mark.asyncio
    async def test_plan_default_supervision_used_when_step_has_none(self) -> None:
        agent = _CountingAgent(fail_times=1, exc=ConnectionError("flaky"), success_value="ok")
        registry: dict[str, Any] = {"a": agent}
        event_sink = InMemoryEventSink()
        runner = PipelineRunner(event_sink=event_sink)
        runtime = WorkflowRuntime(runner=runner, agent_registry=registry)

        plan = WorkflowPlan(
            steps=[WorkflowStep(component_name="step1", agent_id="a")],
            default_supervision=StepSupervision(
                strategy=SupervisionStrategy.RESTART,
                max_restarts=3,
                restart_window_seconds=60.0,
            ),
        )

        result = await runtime.run(agents=[], context=_make_context(), plan=plan)

        assert result.status == RunStatus.FINISHED
        assert result.output == "ok"
        assert agent.call_count == 2
