"""E2E tests proving supervision trees handle agent failures in WorkflowRuntime.

These tests exercise the full supervision path:
WorkflowRuntime -> FlowSupervisor -> StepSupervisor -> SupervisionDecision
with real agents that fail and recover, verifying events are emitted correctly.

Key insight: The error classifier maps exception types to ErrorCategory values,
and StepSupervisor has forced overrides for PERMANENT/VALIDATION/CONFIGURATION/
STATE_CONSISTENCY categories. We use ConnectionError (TRANSIENT) for restartable
failures and RuntimeError (PERMANENT, forced->STOP) for non-restartable ones.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from miniautogen.core.contracts.coordination import WorkflowPlan, WorkflowStep
from miniautogen.core.contracts.enums import SupervisionStrategy
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.supervision import StepSupervision
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.events.types import EventType
from miniautogen.core.runtime.pipeline_runner import PipelineRunner
from miniautogen.core.runtime.workflow_runtime import WorkflowRuntime


# ---------------------------------------------------------------------------
# Test agents
# ---------------------------------------------------------------------------


class FailOnceAgent:
    """Agent that raises ConnectionError on first call, succeeds on retry.

    Uses ConnectionError because it classifies as TRANSIENT, which does NOT
    trigger forced override in StepSupervisor (only PERMANENT, VALIDATION,
    CONFIGURATION, STATE_CONSISTENCY do).
    """

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self._call_count = 0

    async def process(self, input_text: object) -> str:
        self._call_count += 1
        if self._call_count == 1:
            raise ConnectionError(f"{self.agent_id} transient failure")
        return f"{self.agent_id} succeeded on attempt {self._call_count}"


class ReliableAgent:
    """Agent that always succeeds."""

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id

    async def process(self, input_text: object) -> str:
        return f"{self.agent_id} done"


class AlwaysFailTransientAgent:
    """Agent that always raises a transient (ConnectionError) failure.

    Used to test restart budget exhaustion without triggering forced overrides.
    """

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id

    async def process(self, input_text: object) -> str:
        raise ConnectionError(f"{self.agent_id} transient failure")


class AlwaysFailPermanentAgent:
    """Agent that always raises a permanent (RuntimeError) failure.

    RuntimeError classifies as PERMANENT, which triggers forced STOP override
    in StepSupervisor regardless of configured strategy.
    """

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id

    async def process(self, input_text: object) -> str:
        raise RuntimeError(f"{self.agent_id} permanent failure")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx(run_id: str, correlation_id: str) -> RunContext:
    return RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id=correlation_id,
    )


def _event_type_values(sink: InMemoryEventSink) -> list[str]:
    return [e.type for e in sink.events]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_supervision_restarts_failed_step() -> None:
    """RESTART strategy retries a transiently-failing agent and succeeds on second attempt."""
    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)

    supervision = StepSupervision(
        strategy=SupervisionStrategy.RESTART,
        max_restarts=3,
        restart_window_seconds=60,
    )
    steps = [
        WorkflowStep(component_name="flaky", agent_id="flaky", supervision=supervision),
        WorkflowStep(component_name="stable", agent_id="stable"),
    ]
    plan = WorkflowPlan(steps=steps)

    flaky_agent = FailOnceAgent("flaky")
    stable_agent = ReliableAgent("stable")

    wf = WorkflowRuntime(
        runner=runner,
        agent_registry={"flaky": flaky_agent, "stable": stable_agent},
    )
    ctx = _make_ctx("sup-restart", "sup-restart-corr")

    result = await wf.run([flaky_agent, stable_agent], ctx, plan)

    # Workflow should complete successfully after restart
    assert result is not None
    assert result.status.value == "finished"

    # Verify supervision events were emitted
    event_types = _event_type_values(sink)
    assert EventType.SUPERVISION_FAILURE_RECEIVED.value in event_types
    assert EventType.SUPERVISION_DECISION_MADE.value in event_types
    assert EventType.SUPERVISION_RESTART_STARTED.value in event_types
    assert EventType.SUPERVISION_RETRY_SUCCEEDED.value in event_types


@pytest.mark.anyio
async def test_supervision_escalates_after_max_restarts() -> None:
    """Agent that always fails transiently should be escalated after max_restarts exhausted."""
    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)

    supervision = StepSupervision(
        strategy=SupervisionStrategy.RESTART,
        max_restarts=2,
        restart_window_seconds=60,
        circuit_breaker_threshold=10,  # High enough to not trigger
    )
    steps = [
        WorkflowStep(component_name="bad", agent_id="bad", supervision=supervision),
    ]
    plan = WorkflowPlan(steps=steps)

    bad_agent = AlwaysFailTransientAgent("bad")

    wf = WorkflowRuntime(
        runner=runner,
        agent_registry={"bad": bad_agent},
    )
    ctx = _make_ctx("sup-escalate", "sup-escalate-corr")

    # After max_restarts, StepSupervisor returns ESCALATE which workflow_runtime
    # treats as re-raise (line 264)
    result = await wf.run([bad_agent], ctx, plan)
    assert result.status.value == "failed"

    event_types = _event_type_values(sink)
    assert EventType.SUPERVISION_FAILURE_RECEIVED.value in event_types
    assert EventType.SUPERVISION_ESCALATED.value in event_types


@pytest.mark.anyio
async def test_permanent_error_forces_stop() -> None:
    """PERMANENT errors trigger forced STOP override regardless of configured strategy."""
    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)

    # Even with RESTART strategy, PERMANENT errors force STOP
    supervision = StepSupervision(
        strategy=SupervisionStrategy.RESTART,
        max_restarts=5,
        restart_window_seconds=60,
    )
    steps = [
        WorkflowStep(component_name="bad", agent_id="bad", supervision=supervision),
    ]
    plan = WorkflowPlan(steps=steps)

    bad_agent = AlwaysFailPermanentAgent("bad")

    wf = WorkflowRuntime(
        runner=runner,
        agent_registry={"bad": bad_agent},
    )
    ctx = _make_ctx("sup-permanent", "sup-permanent-corr")

    # STOP decision causes re-raise, caught by run() as FAILED
    result = await wf.run([bad_agent], ctx, plan)
    assert result.status.value == "failed"

    # Should see failure received but only one attempt (no restarts)
    event_types = _event_type_values(sink)
    assert EventType.SUPERVISION_FAILURE_RECEIVED.value in event_types
    assert EventType.SUPERVISION_DECISION_MADE.value in event_types
    # No restart should have been attempted
    assert EventType.SUPERVISION_RESTART_STARTED.value not in event_types


@pytest.mark.anyio
async def test_no_supervision_fails_fast() -> None:
    """Without supervision config, a failing agent should raise immediately."""
    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)

    steps = [
        WorkflowStep(component_name="bad", agent_id="bad"),  # No supervision
    ]
    plan = WorkflowPlan(steps=steps)

    bad_agent = AlwaysFailPermanentAgent("bad")

    wf = WorkflowRuntime(
        runner=runner,
        agent_registry={"bad": bad_agent},
    )
    ctx = _make_ctx("no-sup", "no-sup-corr")

    result = await wf.run([bad_agent], ctx, plan)
    assert result.status.value == "failed"

    # No supervision events should be emitted (fail-fast path, line 234-235)
    sup_events = [
        e
        for e in sink.events
        if "supervision" in e.type.lower()
    ]
    assert len(sup_events) == 0


@pytest.mark.anyio
async def test_default_supervision_applies_to_all_steps() -> None:
    """WorkflowPlan.default_supervision applies to steps without explicit supervision."""
    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)

    default_sup = StepSupervision(
        strategy=SupervisionStrategy.RESTART,
        max_restarts=3,
        restart_window_seconds=60,
    )
    steps = [
        WorkflowStep(component_name="flaky", agent_id="flaky"),  # No per-step supervision
    ]
    plan = WorkflowPlan(steps=steps, default_supervision=default_sup)

    flaky_agent = FailOnceAgent("flaky")

    wf = WorkflowRuntime(
        runner=runner,
        agent_registry={"flaky": flaky_agent},
    )
    ctx = _make_ctx("def-sup", "def-sup-corr")

    result = await wf.run([flaky_agent], ctx, plan)

    # Should succeed because default supervision restarts the transient failure
    assert result is not None
    assert result.status.value == "finished"

    event_types = _event_type_values(sink)
    assert EventType.SUPERVISION_FAILURE_RECEIVED.value in event_types
    assert EventType.SUPERVISION_RESTART_STARTED.value in event_types
    assert EventType.SUPERVISION_RETRY_SUCCEEDED.value in event_types
