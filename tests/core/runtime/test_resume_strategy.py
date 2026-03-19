"""Tests for RESUME supervision strategy with CheckpointManager integration."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from miniautogen.core.contracts.coordination import WorkflowPlan, WorkflowStep
from miniautogen.core.contracts.enums import ErrorCategory, SupervisionStrategy
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.supervision import StepSupervision
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.runtime.checkpoint_manager import CheckpointManager
from miniautogen.core.runtime.pipeline_runner import PipelineRunner
from miniautogen.core.runtime.supervisors import StepSupervisor
from miniautogen.core.runtime.workflow_runtime import WorkflowRuntime
from miniautogen.stores.in_memory_checkpoint_store import InMemoryCheckpointStore
from miniautogen.stores.in_memory_event_store import InMemoryEventStore

# ---------- Helpers ----------


def _make_context(run_id: str = "run-1") -> RunContext:
    return RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id="corr-1",
        input_payload="initial-input",
    )


class _FakeAgent:
    """Agent that transforms input by appending suffix."""

    def __init__(self, suffix: str) -> None:
        self.suffix = suffix
        self.call_count = 0

    async def process(self, input_data: Any) -> Any:
        self.call_count += 1
        return f"{input_data}-{self.suffix}"


class _FailOnceAgent:
    """Agent that fails on first call with a transient error, then succeeds."""

    def __init__(self, suffix: str) -> None:
        self.suffix = suffix
        self.call_count = 0

    async def process(self, input_data: Any) -> Any:
        self.call_count += 1
        if self.call_count == 1:
            raise ConnectionError("transient failure")
        return f"{input_data}-{self.suffix}"


class _FailNTimesAgent:
    """Agent that fails N times with transient errors then succeeds."""

    def __init__(self, suffix: str, fail_count: int = 1) -> None:
        self.suffix = suffix
        self.fail_count = fail_count
        self.call_count = 0

    async def process(self, input_data: Any) -> Any:
        self.call_count += 1
        if self.call_count <= self.fail_count:
            raise ConnectionError(f"transient failure #{self.call_count}")
        return f"{input_data}-{self.suffix}"


# ---------- StepSupervisor RESUME tests ----------


class TestStepSupervisorResume:
    """StepSupervisor returns RESUME decision with should_checkpoint=True."""

    @pytest.mark.asyncio
    async def test_resume_returns_decision_with_checkpoint_flag(self) -> None:
        """RESUME returns decision with action=RESUME, should_checkpoint=True."""
        sink = InMemoryEventSink()
        sv = StepSupervisor(event_sink=sink)
        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESUME,
            max_restarts=5,
            circuit_breaker_threshold=100,
        )

        decision = await sv.handle_failure(
            child_id="step-1",
            error=ConnectionError("transient"),
            error_category=ErrorCategory.TRANSIENT,
            supervision=supervision,
            restart_count=0,
        )

        assert decision.action == SupervisionStrategy.RESUME
        assert decision.should_checkpoint is True

    @pytest.mark.asyncio
    async def test_resume_emits_restart_started_event(self) -> None:
        """RESUME emits SUPERVISION_RESTART_STARTED event like RESTART does."""
        sink = InMemoryEventSink()
        sv = StepSupervisor(event_sink=sink)
        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESUME,
            max_restarts=5,
            circuit_breaker_threshold=100,
        )

        await sv.handle_failure(
            child_id="step-1",
            error=ConnectionError("transient"),
            error_category=ErrorCategory.TRANSIENT,
            supervision=supervision,
            restart_count=0,
        )

        event_types = [e.type for e in sink.events]
        assert "supervision_restart_started" in event_types

    @pytest.mark.asyncio
    async def test_resume_records_restart_timestamp(self) -> None:
        """RESUME records timestamp for windowed restart budget tracking."""
        sink = InMemoryEventSink()
        sv = StepSupervisor(event_sink=sink)
        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESUME,
            max_restarts=2,
            restart_window_seconds=60.0,
            circuit_breaker_threshold=100,
        )

        # First RESUME: ok
        decision = await sv.handle_failure(
            child_id="step-1",
            error=ConnectionError("transient"),
            error_category=ErrorCategory.TRANSIENT,
            supervision=supervision,
            restart_count=0,
        )
        assert decision.action == SupervisionStrategy.RESUME

        # Second RESUME: ok
        decision = await sv.handle_failure(
            child_id="step-1",
            error=ConnectionError("transient"),
            error_category=ErrorCategory.TRANSIENT,
            supervision=supervision,
            restart_count=1,
        )
        assert decision.action == SupervisionStrategy.RESUME

        # Third: budget exhausted -> ESCALATE
        decision = await sv.handle_failure(
            child_id="step-1",
            error=ConnectionError("transient"),
            error_category=ErrorCategory.TRANSIENT,
            supervision=supervision,
            restart_count=2,
        )
        assert decision.action == SupervisionStrategy.ESCALATE

    @pytest.mark.asyncio
    async def test_resume_forced_overrides_still_apply(self) -> None:
        """Forced overrides (e.g., PERMANENT -> STOP) take precedence over RESUME."""
        sink = InMemoryEventSink()
        sv = StepSupervisor(event_sink=sink)
        supervision = StepSupervision(strategy=SupervisionStrategy.RESUME)

        decision = await sv.handle_failure(
            child_id="step-1",
            error=RuntimeError("bug"),
            error_category=ErrorCategory.PERMANENT,
            supervision=supervision,
            restart_count=0,
        )

        assert decision.action == SupervisionStrategy.STOP


# ---------- WorkflowRuntime RESUME tests ----------


class TestWorkflowRuntimeResume:
    """WorkflowRuntime handles RESUME decisions with CheckpointManager."""

    @pytest.mark.asyncio
    async def test_resume_saves_checkpoint_and_retries(self) -> None:
        """RESUME saves checkpoint and re-executes the failed step."""
        fail_once = _FailOnceAgent("B")
        agent_a = _FakeAgent("A")

        registry: dict[str, Any] = {"a": agent_a, "b": fail_once}
        event_sink = InMemoryEventSink()
        runner = PipelineRunner(event_sink=event_sink)
        cp_store = InMemoryCheckpointStore()
        ev_store = InMemoryEventStore()
        cp_manager = CheckpointManager(cp_store, ev_store, event_sink)

        runtime = WorkflowRuntime(
            runner=runner,
            agent_registry=registry,
            checkpoint_manager=cp_manager,
        )

        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESUME,
            max_restarts=3,
            circuit_breaker_threshold=100,
        )
        plan = WorkflowPlan(
            steps=[
                WorkflowStep(component_name="step1", agent_id="a"),
                WorkflowStep(component_name="step2", agent_id="b"),
            ],
            default_supervision=supervision,
        )
        ctx = _make_context()
        result = await runtime.run(agents=[], context=ctx, plan=plan)

        assert result.status == "finished"
        assert result.output == "initial-input-A-B"
        # Agent B was called twice (first failed, second succeeded)
        assert fail_once.call_count == 2
        # Checkpoint was saved (at least for step 0 after A succeeded)
        cp = await cp_store.get_checkpoint("run-1")
        assert cp is not None

    @pytest.mark.asyncio
    async def test_resume_with_existing_checkpoint_skips_completed_steps(self) -> None:
        """When resuming from checkpoint, already-completed steps are skipped."""
        agent_a = _FakeAgent("A")
        agent_b = _FakeAgent("B")

        registry: dict[str, Any] = {"a": agent_a, "b": agent_b}
        event_sink = InMemoryEventSink()
        runner = PipelineRunner(event_sink=event_sink)
        cp_store = InMemoryCheckpointStore()
        ev_store = InMemoryEventStore()
        cp_manager = CheckpointManager(cp_store, ev_store, event_sink)

        # Pre-seed checkpoint: step 0 completed, output was "initial-input-A"
        await cp_store.save_checkpoint(
            "run-1",
            {"state": "initial-input-A", "step_index": 1},
        )

        runtime = WorkflowRuntime(
            runner=runner,
            agent_registry=registry,
            checkpoint_manager=cp_manager,
        )

        plan = WorkflowPlan(
            steps=[
                WorkflowStep(component_name="step1", agent_id="a"),
                WorkflowStep(component_name="step2", agent_id="b"),
            ],
        )
        ctx = _make_context()
        result = await runtime.run(agents=[], context=ctx, plan=plan)

        assert result.status == "finished"
        # Step A should NOT have been called (skipped via checkpoint)
        assert agent_a.call_count == 0
        # Step B should have been called with the checkpoint state
        assert agent_b.call_count == 1
        assert result.output == "initial-input-A-B"

    @pytest.mark.asyncio
    async def test_resume_without_checkpoint_manager_falls_back_to_restart(self) -> None:
        """When no CheckpointManager is provided, RESUME behaves like RESTART."""
        fail_once = _FailOnceAgent("B")
        agent_a = _FakeAgent("A")

        registry: dict[str, Any] = {"a": agent_a, "b": fail_once}
        event_sink = InMemoryEventSink()
        runner = PipelineRunner(event_sink=event_sink)

        # No checkpoint_manager -- graceful degradation
        runtime = WorkflowRuntime(
            runner=runner,
            agent_registry=registry,
        )

        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESUME,
            max_restarts=3,
            circuit_breaker_threshold=100,
        )
        plan = WorkflowPlan(
            steps=[
                WorkflowStep(component_name="step1", agent_id="a"),
                WorkflowStep(component_name="step2", agent_id="b"),
            ],
            default_supervision=supervision,
        )
        ctx = _make_context()
        result = await runtime.run(agents=[], context=ctx, plan=plan)

        # Should still succeed (falls back to RESTART behavior)
        assert result.status == "finished"
        assert result.output == "initial-input-A-B"
        assert fail_once.call_count == 2

    @pytest.mark.asyncio
    async def test_resume_saves_checkpoint_after_each_successful_step(self) -> None:
        """After each successful step, checkpoint is saved with step_index."""
        agent_a = _FakeAgent("A")
        agent_b = _FakeAgent("B")
        agent_c = _FakeAgent("C")

        registry: dict[str, Any] = {"a": agent_a, "b": agent_b, "c": agent_c}
        event_sink = InMemoryEventSink()
        runner = PipelineRunner(event_sink=event_sink)
        cp_store = InMemoryCheckpointStore()
        ev_store = InMemoryEventStore()
        cp_manager = CheckpointManager(cp_store, ev_store, event_sink)

        runtime = WorkflowRuntime(
            runner=runner,
            agent_registry=registry,
            checkpoint_manager=cp_manager,
        )

        plan = WorkflowPlan(
            steps=[
                WorkflowStep(component_name="step1", agent_id="a"),
                WorkflowStep(component_name="step2", agent_id="b"),
                WorkflowStep(component_name="step3", agent_id="c"),
            ],
        )
        ctx = _make_context()
        result = await runtime.run(agents=[], context=ctx, plan=plan)

        assert result.status == "finished"
        # Final checkpoint should reflect last step
        cp = await cp_store.get_checkpoint("run-1")
        assert cp is not None
        assert cp["step_index"] == 3  # After all 3 steps
        assert cp["state"] == "initial-input-A-B-C"
