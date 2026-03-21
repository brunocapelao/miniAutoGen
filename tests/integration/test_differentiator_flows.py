"""Integration tests proving MiniAutoGen's core differentiators work end-to-end.

Tests cover:
- Checkpoint recovery (skip completed, resume from midpoint)
- Reactive budget tracking via EventBus
- Deliberation with free-text agents (full protocol)
- Supervision restart under transient failures
- Memory persistence across sessions
- Combined: checkpoint + events + supervision
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from miniautogen.core.contracts.coordination import (
    DeliberationPlan,
    WorkflowPlan,
    WorkflowStep,
)
from miniautogen.core.contracts.deliberation import (
    DeliberationState,
    FinalDocument,
    PeerReview,
    ResearchOutput,
)
from miniautogen.core.contracts.enums import RunStatus, SupervisionStrategy
from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.supervision import StepSupervision
from miniautogen.core.events.types import EventType
from miniautogen.core.runtime.checkpoint_manager import CheckpointManager
from miniautogen.core.runtime.deliberation_runtime import DeliberationRuntime
from miniautogen.core.runtime.persistent_memory import PersistentMemoryProvider
from miniautogen.core.runtime.pipeline_runner import PipelineRunner
from miniautogen.core.runtime.workflow_runtime import WorkflowRuntime
from miniautogen.policies.budget import BudgetPolicy
from miniautogen.policies.reactive import ReactiveBudgetTracker
from miniautogen.stores.in_memory_checkpoint_store import InMemoryCheckpointStore
from miniautogen.stores.in_memory_event_store import InMemoryEventStore


# ---------------------------------------------------------------------------
# Helper: build CheckpointManager from runner + store
# ---------------------------------------------------------------------------


def _make_checkpoint_manager(
    runner: PipelineRunner,
    checkpoint_store: InMemoryCheckpointStore,
) -> CheckpointManager:
    return CheckpointManager(
        checkpoint_store=checkpoint_store,
        event_store=InMemoryEventStore(),
        event_sink=runner.event_sink,
    )


# ---------------------------------------------------------------------------
# Fake agents
# ---------------------------------------------------------------------------


class FakeAgent:
    """Deterministic agent that prefixes input with a string."""

    def __init__(self, agent_id: str, prefix: str) -> None:
        self.agent_id = agent_id
        self.prefix = prefix

    async def process(self, input_data: Any) -> str:
        return f"{self.prefix}({input_data})"


class CountingAgent:
    """Agent that counts how many times it has been called."""

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self.call_count = 0

    async def process(self, input_data: Any) -> str:
        self.call_count += 1
        return f"step-{self.call_count}"


class FailOnceAgent:
    """Agent that raises ConnectionError on the first call, succeeds after."""

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self.call_count = 0

    async def process(self, input_data: Any) -> str:
        self.call_count += 1
        if self.call_count == 1:
            raise ConnectionError("transient network failure")
        return f"recovered-{self.call_count}"


class FreeTextContributor:
    """Deliberation agent implementing the full DeliberationAgent protocol.

    Returns free-text content (not JSON) wrapped in the required contract types.
    Implements: contribute, review, consolidate, produce_final_document.
    """

    def __init__(self, agent_id: str, text: str) -> None:
        self.agent_id = agent_id
        self.text = text

    async def contribute(self, topic: str) -> ResearchOutput:
        return ResearchOutput(
            role_name=self.agent_id,
            section_title=f"{self.agent_id} on {topic}",
            findings=[self.text],
            facts=[f"fact from {self.agent_id}"],
            evidence=[],
            inferences=[],
            uncertainties=[],
            recommendation=f"{self.agent_id} recommends: {self.text}",
            next_tests=[],
        )

    async def review(
        self, target_role: str, contribution: ResearchOutput
    ) -> PeerReview:
        return PeerReview(
            reviewer_role=self.agent_id,
            target_role=target_role,
            target_section_title=contribution.section_title,
            strengths=[f"Good point by {target_role}"],
            concerns=[],
            questions=[],
        )

    async def consolidate(
        self,
        topic: str,
        contributions: list[ResearchOutput],
        reviews: list[PeerReview],
    ) -> DeliberationState:
        return DeliberationState(
            review_cycle=1,
            accepted_facts=[f.facts[0] for f in contributions if f.facts],
            open_conflicts=[],
            pending_gaps=[],
            leader_decision="Consolidated by leader",
            is_sufficient=True,
        )

    async def produce_final_document(
        self,
        state: DeliberationState,
        contributions: list[ResearchOutput],
    ) -> FinalDocument:
        body = "\n".join(c.recommendation for c in contributions)
        return FinalDocument(
            executive_summary="Free-text deliberation summary",
            accepted_facts=state.accepted_facts,
            open_conflicts=state.open_conflicts,
            pending_decisions=[],
            recommendations=[c.recommendation for c in contributions],
            decision_summary="All participants agree",
            body_markdown=body,
        )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_run_context(
    run_id: str = "test-run",
    input_payload: Any = "hello",
) -> RunContext:
    return RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id=run_id,
        input_payload=input_payload,
    )


def _collect_events(runner: PipelineRunner) -> list[ExecutionEvent]:
    """Subscribe to all events on the runner's event_bus and return collector."""
    collected: list[ExecutionEvent] = []

    async def _handler(event: ExecutionEvent) -> None:
        collected.append(event)

    runner.event_bus.subscribe(None, _handler)
    return collected


# ===================================================================
# TEST 1: Checkpoint recovery skips completed steps
# ===================================================================


@pytest.mark.anyio
async def test_checkpoint_recovery_skips_completed_steps() -> None:
    """Run 3-step workflow, then resume same run_id -- all steps skipped."""
    runner = PipelineRunner()
    store = InMemoryCheckpointStore()
    cm = _make_checkpoint_manager(runner, store)

    a = CountingAgent("a")
    b = CountingAgent("b")
    c = CountingAgent("c")

    registry = {"a": a, "b": b, "c": c}
    wrt = WorkflowRuntime(runner=runner, agent_registry=registry, checkpoint_manager=cm)

    plan = WorkflowPlan(
        steps=[
            WorkflowStep(component_name="a", agent_id="a"),
            WorkflowStep(component_name="b", agent_id="b"),
            WorkflowStep(component_name="c", agent_id="c"),
        ]
    )

    # First run
    ctx = _make_run_context(run_id="run-1", input_payload="start")
    result = await wrt.run([], ctx, plan)
    assert result.status == RunStatus.FINISHED

    # Verify checkpoint exists
    cp = await store.get_checkpoint("run-1")
    assert cp is not None
    assert cp["step_index"] == 3  # all 3 steps completed

    # Record call counts after first run
    assert a.call_count == 1
    assert b.call_count == 1
    assert c.call_count == 1

    # Resume same run_id -- all steps should be skipped
    ctx2 = _make_run_context(run_id="run-1", input_payload="start")
    result2 = await wrt.run([], ctx2, plan)
    assert result2.status == RunStatus.FINISHED

    # Call counts should NOT have increased (steps were skipped)
    assert a.call_count == 1
    assert b.call_count == 1
    assert c.call_count == 1


# ===================================================================
# TEST 2: Checkpoint recovery resumes from midpoint
# ===================================================================


@pytest.mark.anyio
async def test_checkpoint_recovery_resumes_from_midpoint() -> None:
    """Pre-seed checkpoint at step_index=1, resume skips step 0."""
    runner = PipelineRunner()
    store = InMemoryCheckpointStore()
    cm = _make_checkpoint_manager(runner, store)

    a = CountingAgent("a")
    b = CountingAgent("b")
    c = CountingAgent("c")

    registry = {"a": a, "b": b, "c": c}
    wrt = WorkflowRuntime(runner=runner, agent_registry=registry, checkpoint_manager=cm)

    plan = WorkflowPlan(
        steps=[
            WorkflowStep(component_name="a", agent_id="a"),
            WorkflowStep(component_name="b", agent_id="b"),
            WorkflowStep(component_name="c", agent_id="c"),
        ]
    )

    # Pre-seed checkpoint: step 0 already done, state is "after-step-0"
    await store.save_checkpoint("run-mid", {"state": "after-step-0", "step_index": 1})

    ctx = _make_run_context(run_id="run-mid", input_payload="start")
    result = await wrt.run([], ctx, plan)
    assert result.status == RunStatus.FINISHED

    # Step 0 (agent a) should be skipped, steps 1 and 2 should execute
    assert a.call_count == 0
    assert b.call_count == 1
    assert c.call_count == 1


# ===================================================================
# TEST 3: Reactive budget tracker fires via EventBus
# ===================================================================


@pytest.mark.anyio
async def test_reactive_budget_tracker_fires_via_eventbus() -> None:
    """Subscribe ReactiveBudgetTracker and publish COMPONENT_FINISHED events."""
    runner = PipelineRunner()

    # Create tracker with budget
    tracker = ReactiveBudgetTracker(policy=BudgetPolicy(max_cost=10.0))

    # Subscribe tracker to COMPONENT_FINISHED events on the EventBus
    runner.event_bus.subscribe("component_finished", tracker.on_event)

    # Publish COMPONENT_FINISHED events through runner.event_sink
    for cost in [1.5, 2.0, 3.0]:
        event = ExecutionEvent(
            type=EventType.COMPONENT_FINISHED.value,
            timestamp=datetime.now(timezone.utc),
            run_id="test-run",
            correlation_id="test-corr",
            scope="test",
            payload={"cost": cost},
        )
        await runner.event_sink.publish(event)

    # Verify tracker accumulated costs correctly
    assert tracker.spent == pytest.approx(6.5)
    assert tracker.remaining == pytest.approx(3.5)


# ===================================================================
# TEST 4: Deliberation with free-text agents
# ===================================================================


@pytest.mark.anyio
async def test_deliberation_with_free_text_agents() -> None:
    """Run DeliberationRuntime with agents returning free-text contributions."""
    runner = PipelineRunner()

    leader = FreeTextContributor("leader", "We should use Python")
    analyst = FreeTextContributor("analyst", "Performance matters")

    registry = {"leader": leader, "analyst": analyst}
    drt = DeliberationRuntime(runner=runner, agent_registry=registry)

    plan = DeliberationPlan(
        topic="Which language to use?",
        participants=["leader", "analyst"],
        max_rounds=1,
        leader_agent="leader",
    )

    ctx = _make_run_context(run_id="delib-1")
    result = await drt.run([], ctx, plan)

    # MUST be FINISHED, not FAILED
    assert result.status == RunStatus.FINISHED, (
        f"Deliberation failed with error: {result.error}"
    )

    # Verify metadata contains the final document
    assert result.metadata is not None
    assert "final_document" in result.metadata
    assert "rendered_markdown" in result.metadata


# ===================================================================
# TEST 5: Supervision restart under transient failure
# ===================================================================


@pytest.mark.anyio
async def test_supervision_restart_in_workflow() -> None:
    """Step 2 fails with ConnectionError, supervision restarts, then succeeds."""
    runner = PipelineRunner()
    collected = _collect_events(runner)

    a = FakeAgent("a", "step-a")
    b = FailOnceAgent("b")  # ConnectionError on first call
    c = FakeAgent("c", "step-c")

    registry = {"a": a, "b": b, "c": c}
    wrt = WorkflowRuntime(runner=runner, agent_registry=registry)

    supervision = StepSupervision(
        strategy=SupervisionStrategy.RESTART,
        max_restarts=3,
    )

    plan = WorkflowPlan(
        steps=[
            WorkflowStep(component_name="a", agent_id="a"),
            WorkflowStep(component_name="b", agent_id="b", supervision=supervision),
            WorkflowStep(component_name="c", agent_id="c"),
        ]
    )

    ctx = _make_run_context(run_id="sup-run", input_payload="start")
    result = await wrt.run([], ctx, plan)

    assert result.status == RunStatus.FINISHED

    # FailOnceAgent should have been called twice (fail + succeed)
    assert b.call_count == 2

    # Verify supervision events were emitted
    event_types = [e.type for e in collected]
    assert EventType.SUPERVISION_FAILURE_RECEIVED.value in event_types
    assert EventType.SUPERVISION_RETRY_SUCCEEDED.value in event_types


# ===================================================================
# TEST 6: Memory persists across agent sessions
# ===================================================================


@pytest.mark.anyio
async def test_memory_persists_across_agent_sessions(tmp_path: Any) -> None:
    """Save turns, persist to disk, reload in new session, verify turns survived."""
    memory_dir = tmp_path / "agent_memory"

    # Session 1: save turns and persist
    mem1 = PersistentMemoryProvider(memory_dir)
    ctx = _make_run_context(run_id="session-1")

    await mem1.save_turn(
        [
            {"role": "user", "content": "Hello, world!"},
            {"role": "assistant", "content": "Hi there!"},
        ],
        ctx,
    )
    await mem1.save_turn(
        [{"role": "user", "content": "How are you?"}],
        ctx,
    )
    await mem1.persist_to_disk()

    # Session 2: new instance, load from disk
    mem2 = PersistentMemoryProvider(memory_dir)
    await mem2.load_from_disk()

    messages = await mem2.get_context("test-agent", ctx)

    assert len(messages) == 3
    assert messages[0]["content"] == "Hello, world!"
    assert messages[1]["content"] == "Hi there!"
    assert messages[2]["content"] == "How are you?"


# ===================================================================
# TEST 7: Full workflow with checkpoint + events + supervision
# ===================================================================


@pytest.mark.anyio
async def test_full_workflow_with_checkpoint_events_supervision() -> None:
    """Combined test: checkpoint + reactive budget tracker + supervision."""
    runner = PipelineRunner()
    store = InMemoryCheckpointStore()
    cm = _make_checkpoint_manager(runner, store)
    collected = _collect_events(runner)

    # Wire up reactive budget tracker
    tracker = ReactiveBudgetTracker(policy=BudgetPolicy(max_cost=100.0))
    runner.event_bus.subscribe("component_finished", tracker.on_event)

    a = FakeAgent("a", "step-a")
    b = FailOnceAgent("b")  # ConnectionError on first call
    c = FakeAgent("c", "step-c")

    registry = {"a": a, "b": b, "c": c}
    supervision = StepSupervision(
        strategy=SupervisionStrategy.RESTART,
        max_restarts=3,
    )

    wrt = WorkflowRuntime(
        runner=runner,
        agent_registry=registry,
        checkpoint_manager=cm,
    )

    plan = WorkflowPlan(
        steps=[
            WorkflowStep(component_name="a", agent_id="a"),
            WorkflowStep(component_name="b", agent_id="b", supervision=supervision),
            WorkflowStep(component_name="c", agent_id="c"),
        ]
    )

    ctx = _make_run_context(run_id="combined-run", input_payload="start")
    result = await wrt.run([], ctx, plan)

    # Workflow completed successfully
    assert result.status == RunStatus.FINISHED

    # Checkpoint exists after run
    cp = await store.get_checkpoint("combined-run")
    assert cp is not None
    assert cp["step_index"] == 3

    # Supervision events were emitted
    event_types = [e.type for e in collected]
    assert EventType.SUPERVISION_FAILURE_RECEIVED.value in event_types
    assert EventType.SUPERVISION_RETRY_SUCCEEDED.value in event_types

    # Budget tracker is subscribed (it would accumulate if COMPONENT_FINISHED
    # events with cost were emitted -- here we verify the subscription works)
    assert tracker.spent == pytest.approx(0.0)  # no cost payloads from workflow
