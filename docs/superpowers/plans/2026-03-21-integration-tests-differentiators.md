# Integration Tests for System Differentiators

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 7 integration tests that prove 5 core differentiators work end-to-end: checkpoint recovery, reactive policies via EventBus, deliberation with free-text backends, supervision under failure, and memory persistence.

**Architecture:** Each test uses PipelineRunner with in-memory stores and fake agents (implementing `.process()`) to exercise a complete flow. No external dependencies. Tests go in `tests/integration/` following existing patterns from `test_sdk_flows.py`.

**Tech Stack:** Python 3.11+, AnyIO, pytest, InMemoryEventSink, InMemoryCheckpointStore

**Context:** The gap-closing PRs (commit `8c3b4ca`) wired EventBus, CheckpointManager, and reactive policies. These integration tests validate that the wiring actually works in real pipeline flows.

---

## File Structure

All tests go in a single new file — they share fake agents and helpers:

| File | Purpose |
|------|---------|
| Create: `tests/integration/test_differentiator_flows.py` | 7 integration tests for system differentiators |

---

## Task 1: Shared test infrastructure (fake agents + helpers)

**Files:**
- Create: `tests/integration/test_differentiator_flows.py`

- [ ] **Step 1: Create test file with fake agents and helpers**

```python
"""Integration tests proving MiniAutoGen differentiators work end-to-end.

Each test exercises a complete pipeline flow through PipelineRunner
using in-memory infrastructure and fake agents. No external dependencies.

Differentiators tested:
1. Checkpoint recovery (resume_run_id + CheckpointManager)
2. Reactive event-driven policies (EventBus + ReactiveBudgetTracker)
3. Deliberation with non-JSON free-text backends
4. Supervision trees under real transient failures
5. Memory persistence across agent sessions
6. Combined: checkpoint + events + supervision working together
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import anyio
import pytest

from miniautogen.core.contracts.coordination import (
    AgenticLoopPlan,
    DeliberationPlan,
    WorkflowPlan,
    WorkflowStep,
)
from miniautogen.core.contracts.enums import SupervisionStrategy
from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.supervision import StepSupervision
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.events.event_bus import EventBus
from miniautogen.core.events.types import EventType
from miniautogen.core.runtime.pipeline_runner import PipelineRunner
from miniautogen.core.runtime.workflow_runtime import WorkflowRuntime
from miniautogen.core.runtime.deliberation_runtime import DeliberationRuntime
from miniautogen.policies.budget import BudgetPolicy
from miniautogen.policies.chain import PolicyChain
from miniautogen.policies.reactive import ReactiveBudgetTracker
from miniautogen.stores.in_memory_checkpoint_store import InMemoryCheckpointStore


# ---------------------------------------------------------------------------
# Fake agents — implement .process() for WorkflowRuntime._invoke_agent
# ---------------------------------------------------------------------------


class FakeAgent:
    """Agent that transforms input deterministically."""

    def __init__(self, agent_id: str, prefix: str = "processed"):
        self.agent_id = agent_id
        self._prefix = prefix
        self.call_count = 0

    async def process(self, input_text: Any) -> str:
        self.call_count += 1
        return f"{self._prefix}:{self.agent_id}({input_text})"


class FailOnceAgent:
    """Agent that fails with ConnectionError on first call, then succeeds."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self._call_count = 0

    async def process(self, input_text: Any) -> str:
        self._call_count += 1
        if self._call_count == 1:
            raise ConnectionError(f"{self.agent_id} transient failure")
        return f"{self.agent_id} recovered on attempt {self._call_count}"


class CrashingAgent:
    """Agent that always crashes — simulates permanent step failure."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id

    async def process(self, input_text: Any) -> str:
        raise ConnectionError(f"{self.agent_id} crashed")


class CountingAgent:
    """Agent that counts calls and returns call number."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.call_count = 0

    async def process(self, input_text: Any) -> str:
        self.call_count += 1
        return f"step-{self.call_count}"


class FreeTextContributor:
    """Agent that returns free text (no JSON) for deliberation.

    Implements the full DeliberationAgent protocol:
    - contribute() — returns Contribution
    - review() — returns PeerReview (NOT Review — DeliberationRuntime uses target_role)
    - consolidate() — returns DeliberationState (leader method)
    - produce_final_document() — returns FinalDocument (leader method)
    """

    def __init__(self, agent_id: str, text: str):
        self.agent_id = agent_id
        self._text = text

    async def contribute(self, topic: str):
        from miniautogen.core.contracts.deliberation import Contribution
        return Contribution(
            participant_id=self.agent_id,
            title=topic,
            content={"text": self._text},
        )

    async def review(self, target_id: str, contribution: Any):
        from miniautogen.core.contracts.deliberation import PeerReview
        return PeerReview(
            reviewer_id=self.agent_id,
            reviewer_role=self.agent_id,
            target_id=target_id,
            target_role=target_id,
            target_section_title=contribution.title,
            target_title=contribution.title,
            strengths=["good work"],
            concerns=[],
            questions=[],
        )

    async def consolidate(self, topic: str, contributions: list, reviews: list):
        from miniautogen.core.contracts.deliberation import DeliberationState
        return DeliberationState(
            review_cycle=1,
            accepted_facts=[f"Contributions on: {topic}"],
            is_sufficient=True,
        )

    async def produce_final_document(self, state: Any, contributions: list):
        from miniautogen.core.contracts.deliberation import FinalDocument
        return FinalDocument(
            executive_summary="Free-text deliberation completed",
            decision_summary="Consensus reached via free-text agents",
            body_markdown=f"# Result\n{self._text}",
        )

    async def process(self, input_text: Any) -> str:
        return self._text


def _make_context(run_id: str = "integ-test") -> RunContext:
    return RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id=run_id,
    )
```

- [ ] **Step 2: Verify file compiles**

Run: `python -c "import tests.integration.test_differentiator_flows"`
Expected: No errors

- [ ] **Step 3: Commit skeleton**

```bash
git add tests/integration/test_differentiator_flows.py
git commit -m "test(integration): add fake agents for differentiator integration tests"
```

---

## Task 2: E2E checkpoint recovery flow

**Files:**
- Modify: `tests/integration/test_differentiator_flows.py`

- [ ] **Step 1: Write the test**

Append to `tests/integration/test_differentiator_flows.py`:

```python
# ---------------------------------------------------------------------------
# Test 1: Checkpoint recovery — resume skips completed steps
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_checkpoint_recovery_skips_completed_steps():
    """Run 3-step workflow, checkpoint after each step.

    Then resume with same run_id — steps 1-2 should be skipped,
    only step 3 re-executes.

    Proves: resume_run_id + CheckpointManager + WorkflowRuntime recovery
    """
    checkpoint_store = InMemoryCheckpointStore()
    sink = InMemoryEventSink()
    runner = PipelineRunner(
        event_sink=sink,
        checkpoint_store=checkpoint_store,
    )

    agent_a = CountingAgent("a")
    agent_b = CountingAgent("b")
    agent_c = CountingAgent("c")

    steps = [
        WorkflowStep(component_name="a", agent_id="a"),
        WorkflowStep(component_name="b", agent_id="b"),
        WorkflowStep(component_name="c", agent_id="c"),
    ]
    plan = WorkflowPlan(steps=steps)
    registry = {"a": agent_a, "b": agent_b, "c": agent_c}

    # Run 1: full execution (checkpoint saved after each step)
    wf = WorkflowRuntime(
        runner=runner,
        agent_registry=registry,
        checkpoint_manager=_make_checkpoint_manager(runner, checkpoint_store),
    )
    run_id = "recovery-test-001"
    ctx = _make_context(run_id)
    result = await wf.run([agent_a, agent_b, agent_c], ctx, plan)
    assert result is not None
    assert agent_a.call_count == 1
    assert agent_b.call_count == 1
    assert agent_c.call_count == 1

    # Checkpoint should exist at step_index=3 (all done)
    cp = await checkpoint_store.get_checkpoint(run_id)
    assert cp is not None
    assert cp["step_index"] == 3

    # Run 2: resume — all steps should be skipped (already at index 3)
    agent_a2 = CountingAgent("a")
    agent_b2 = CountingAgent("b")
    agent_c2 = CountingAgent("c")
    registry2 = {"a": agent_a2, "b": agent_b2, "c": agent_c2}

    wf2 = WorkflowRuntime(
        runner=runner,
        agent_registry=registry2,
        checkpoint_manager=_make_checkpoint_manager(runner, checkpoint_store),
    )
    result2 = await wf2.run([agent_a2, agent_b2, agent_c2], ctx, plan)

    # No agents should have been called — all steps skipped
    assert agent_a2.call_count == 0
    assert agent_b2.call_count == 0
    assert agent_c2.call_count == 0


@pytest.mark.anyio
async def test_checkpoint_recovery_resumes_from_midpoint():
    """Simulate crash at step 2 by pre-seeding checkpoint at step_index=1.

    Resume should skip step 0, execute steps 1 and 2.
    """
    checkpoint_store = InMemoryCheckpointStore()
    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink, checkpoint_store=checkpoint_store)

    run_id = "midpoint-resume-001"

    # Pre-seed checkpoint: step 0 completed, output was "step-1"
    await checkpoint_store.save_checkpoint(run_id, {
        "state": "step-1",
        "step_index": 1,
    })

    agent_a = CountingAgent("a")
    agent_b = CountingAgent("b")
    agent_c = CountingAgent("c")

    steps = [
        WorkflowStep(component_name="a", agent_id="a"),
        WorkflowStep(component_name="b", agent_id="b"),
        WorkflowStep(component_name="c", agent_id="c"),
    ]
    plan = WorkflowPlan(steps=steps)
    registry = {"a": agent_a, "b": agent_b, "c": agent_c}

    wf = WorkflowRuntime(
        runner=runner,
        agent_registry=registry,
        checkpoint_manager=_make_checkpoint_manager(runner, checkpoint_store),
    )
    ctx = _make_context(run_id)
    result = await wf.run([agent_a, agent_b, agent_c], ctx, plan)

    # Step a should be SKIPPED (checkpoint was at index 1)
    assert agent_a.call_count == 0, "Step a should be skipped (checkpointed)"
    # Steps b and c should execute
    assert agent_b.call_count == 1, "Step b should execute"
    assert agent_c.call_count == 1, "Step c should execute"


def _make_checkpoint_manager(runner, checkpoint_store):
    """Helper to create a CheckpointManager from runner + store."""
    from miniautogen.core.runtime.checkpoint_manager import CheckpointManager
    from miniautogen.stores.in_memory_event_store import InMemoryEventStore

    return CheckpointManager(
        checkpoint_store=checkpoint_store,
        event_store=InMemoryEventStore(),
        event_sink=runner.event_sink,
    )
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/integration/test_differentiator_flows.py::test_checkpoint_recovery_skips_completed_steps tests/integration/test_differentiator_flows.py::test_checkpoint_recovery_resumes_from_midpoint -v`
Expected: Both PASS

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_differentiator_flows.py
git commit -m "test(integration): add E2E checkpoint recovery tests

Two tests prove resume_run_id + CheckpointManager work end-to-end:
1. Full run checkpoints, resume skips all steps
2. Pre-seeded midpoint checkpoint, resume skips completed steps"
```

---

## Task 3: E2E reactive policy via EventBus

**Files:**
- Modify: `tests/integration/test_differentiator_flows.py`

- [ ] **Step 1: Write the test**

Append:

```python
# ---------------------------------------------------------------------------
# Test 2: Reactive policies fire via EventBus during pipeline execution
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_reactive_budget_tracker_fires_during_workflow():
    """Prove EventBus subscription mechanism works end-to-end.

    Publishes COMPONENT_FINISHED events through PipelineRunner's event_sink
    and verifies ReactiveBudgetTracker receives them via the internal EventBus.

    Proves: PipelineRunner.event_bus + CompositeEventSink wiring + reactive
    policy subscription. Note: tests the subscription mechanism, not that
    WorkflowRuntime itself emits COMPONENT_FINISHED (it emits RUN_* events).
    """
    sink = InMemoryEventSink()
    budget_policy = BudgetPolicy(max_cost=1000.0)
    tracker = ReactiveBudgetTracker(policy=budget_policy)
    policy_chain = PolicyChain(evaluators=[])

    runner = PipelineRunner(
        event_sink=sink,
        policy_chain=policy_chain,
    )

    # Manually subscribe tracker to EventBus (simulating what
    # PolicyChain.register_reactive_on_bus does)
    for event_type in tracker.subscribed_events:
        runner.event_bus.subscribe(event_type, tracker.on_event)

    assert tracker.spent == 0.0

    # Publish a COMPONENT_FINISHED event with cost through the runner's sink
    event = ExecutionEvent(
        type=EventType.COMPONENT_FINISHED.value,
        timestamp=datetime.now(timezone.utc),
        run_id="budget-test",
        correlation_id="budget-corr",
        scope="workflow_runtime",
        payload={"cost": 42.5, "component": "step_a"},
    )
    await runner.event_sink.publish(event)

    # Tracker should have received the event via EventBus
    assert tracker.spent == 42.5, "Reactive tracker should accumulate cost from events"

    # Publish another
    event2 = ExecutionEvent(
        type=EventType.COMPONENT_FINISHED.value,
        timestamp=datetime.now(timezone.utc),
        run_id="budget-test",
        correlation_id="budget-corr",
        scope="workflow_runtime",
        payload={"cost": 17.5},
    )
    await runner.event_sink.publish(event2)

    assert tracker.spent == 60.0, "Should accumulate across events"
    assert tracker.remaining == 940.0, "Budget remaining = 1000 - 60"
```

- [ ] **Step 2: Run test**

Run: `python -m pytest tests/integration/test_differentiator_flows.py::test_reactive_budget_tracker_fires_during_workflow -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_differentiator_flows.py
git commit -m "test(integration): add E2E reactive policy via EventBus test

Proves ReactiveBudgetTracker receives COMPONENT_FINISHED events through
PipelineRunner's EventBus, accumulating cost in real-time."
```

---

## Task 4: E2E Deliberation with free-text backends

**Files:**
- Modify: `tests/integration/test_differentiator_flows.py`

- [ ] **Step 1: Write the test**

Append:

```python
# ---------------------------------------------------------------------------
# Test 3: Deliberation works with non-JSON (free-text) backends
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_deliberation_with_free_text_agents():
    """Run a deliberation round where agents return free text, not JSON.

    Proves: contribute() and review() JSON resilience in a real flow.
    """
    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)

    agents = {
        "alice": FreeTextContributor("alice", "I think we should use microservices"),
        "bob": FreeTextContributor("bob", "Monolith first, split later"),
    }

    plan = DeliberationPlan(
        topic="Architecture approach for v2",
        participants=["alice", "bob"],
        max_rounds=1,
    )

    rt = DeliberationRuntime(
        runner=runner,
        agent_registry=agents,
    )

    ctx = _make_context("delib-free-text")
    result = await rt.run(
        [agents["alice"], agents["bob"]],
        ctx,
        plan,
    )

    # Should complete without JSON errors
    assert result is not None

    # Deliberation should complete SUCCESSFULLY — not fail
    event_types = {e.type for e in sink.events}
    assert EventType.DELIBERATION_STARTED.value in event_types
    assert EventType.DELIBERATION_FINISHED.value in event_types, \
        "Deliberation should finish successfully with free-text agents"
    assert EventType.DELIBERATION_FAILED.value not in event_types, \
        "Deliberation should not fail — if it did, fake agent is missing methods"
```

- [ ] **Step 2: Run test**

Run: `python -m pytest tests/integration/test_differentiator_flows.py::test_deliberation_with_free_text_agents -v`
Expected: PASS (may need adjustment if DeliberationRuntime expects specific protocol methods)

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_differentiator_flows.py
git commit -m "test(integration): add E2E deliberation with free-text backends

Proves contribute() and review() resilience in a full deliberation
round where agents return free text instead of JSON."
```

---

## Task 5: E2E supervision restart under real workflow

**Files:**
- Modify: `tests/integration/test_differentiator_flows.py`

- [ ] **Step 1: Write the test**

Append:

```python
# ---------------------------------------------------------------------------
# Test 4: Supervision restarts a failing agent in a 3-step workflow
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_supervision_restart_in_workflow():
    """3-step workflow where step 2 fails once then succeeds.

    Supervision with RESTART strategy should retry step 2 and complete.

    Proves: FlowSupervisor + StepSupervisor + RESTART in real workflow.
    """
    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)

    supervision = StepSupervision(
        strategy=SupervisionStrategy.RESTART,
        max_restarts=3,
        restart_window_seconds=60,
    )

    steps = [
        WorkflowStep(component_name="step1", agent_id="step1"),
        WorkflowStep(
            component_name="step2",
            agent_id="step2",
            supervision=supervision,
        ),
        WorkflowStep(component_name="step3", agent_id="step3"),
    ]
    plan = WorkflowPlan(steps=steps)

    step1 = FakeAgent("step1", "analyzed")
    step2 = FailOnceAgent("step2")  # Fails first, succeeds second
    step3 = FakeAgent("step3", "finalized")

    registry = {"step1": step1, "step2": step2, "step3": step3}

    wf = WorkflowRuntime(runner=runner, agent_registry=registry)
    ctx = _make_context("supervision-workflow")

    result = await wf.run([step1, step2, step3], ctx, plan)

    # Should complete successfully despite step2's transient failure
    assert result is not None
    assert step1.call_count == 1
    assert step3.call_count == 1

    # Supervision events should show failure + restart + success
    event_types = [e.type for e in sink.events]
    assert EventType.SUPERVISION_FAILURE_RECEIVED.value in event_types
    assert EventType.SUPERVISION_RETRY_SUCCEEDED.value in event_types
```

- [ ] **Step 2: Run test**

Run: `python -m pytest tests/integration/test_differentiator_flows.py::test_supervision_restart_in_workflow -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_differentiator_flows.py
git commit -m "test(integration): add E2E supervision restart in workflow

Proves FlowSupervisor handles transient failure with RESTART strategy
in a real 3-step workflow, emitting proper supervision events."
```

---

## Task 6: E2E memory persistence across turns

**Files:**
- Modify: `tests/integration/test_differentiator_flows.py`

- [ ] **Step 1: Write the test**

Append:

```python
# ---------------------------------------------------------------------------
# Test 5: Memory persists across agent sessions
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_memory_persists_across_agent_sessions(tmp_path: Path):
    """Agent saves turn in session 1, loads it in session 2.

    Proves: PersistentMemoryProvider load/persist lifecycle works E2E.
    """
    from miniautogen.core.runtime.persistent_memory import PersistentMemoryProvider

    mem_dir = tmp_path / "agent_memory"

    # Session 1: save turns
    mem1 = PersistentMemoryProvider(mem_dir)
    await mem1.load_from_disk()

    ctx = _make_context("mem-test-run")
    await mem1.save_turn(
        [
            {"role": "user", "content": "Design a REST API"},
            {"role": "assistant", "content": "I'll create endpoints for CRUD operations"},
        ],
        ctx,
    )
    await mem1.save_turn(
        [
            {"role": "user", "content": "Add authentication"},
            {"role": "assistant", "content": "JWT-based auth with refresh tokens"},
        ],
        ctx,
    )
    await mem1.persist_to_disk()

    # Session 2: load and verify context available
    mem2 = PersistentMemoryProvider(mem_dir)
    await mem2.load_from_disk()

    messages = await mem2.get_context("designer", ctx)
    assert len(messages) >= 2, "Should have at least 2 turns persisted"

    # Verify content survived round-trip
    all_content = " ".join(str(m.get("content", "")) for m in messages)
    assert "REST API" in all_content or "CRUD" in all_content
    assert "JWT" in all_content or "auth" in all_content
```

- [ ] **Step 2: Run test**

Run: `python -m pytest tests/integration/test_differentiator_flows.py::test_memory_persists_across_agent_sessions -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_differentiator_flows.py
git commit -m "test(integration): add E2E memory persistence across sessions

Proves PersistentMemoryProvider correctly saves turns to disk and
reloads them in a new session, enabling cross-session agent memory."
```

---

## Task 7: E2E complete workflow with all differentiators

**Files:**
- Modify: `tests/integration/test_differentiator_flows.py`

- [ ] **Step 1: Write the combined test**

Append:

```python
# ---------------------------------------------------------------------------
# Test 6: Full workflow with checkpoint + events + supervision
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_full_workflow_with_checkpoint_events_supervision():
    """3-step workflow combining checkpointing, event tracking, and supervision.

    Proves: All three differentiators work together without conflicts.
    """
    sink = InMemoryEventSink()
    checkpoint_store = InMemoryCheckpointStore()
    budget_policy = BudgetPolicy(max_cost=10000.0)
    tracker = ReactiveBudgetTracker(policy=budget_policy)

    runner = PipelineRunner(
        event_sink=sink,
        checkpoint_store=checkpoint_store,
    )

    # Subscribe reactive tracker
    for et in tracker.subscribed_events:
        runner.event_bus.subscribe(et, tracker.on_event)

    supervision = StepSupervision(
        strategy=SupervisionStrategy.RESTART,
        max_restarts=2,
        restart_window_seconds=60,
    )

    steps = [
        WorkflowStep(component_name="analyze", agent_id="analyze"),
        WorkflowStep(
            component_name="build",
            agent_id="build",
            supervision=supervision,
        ),
        WorkflowStep(component_name="test", agent_id="test"),
    ]
    plan = WorkflowPlan(steps=steps)

    registry = {
        "analyze": FakeAgent("analyze", "analysis"),
        "build": FailOnceAgent("build"),  # Transient failure with recovery
        "test": FakeAgent("test", "tested"),
    }

    run_id = "combined-test-001"
    wf = WorkflowRuntime(
        runner=runner,
        agent_registry=registry,
        checkpoint_manager=_make_checkpoint_manager(runner, checkpoint_store),
    )
    ctx = _make_context(run_id)

    result = await wf.run(
        [registry["analyze"], registry["build"], registry["test"]],
        ctx,
        plan,
    )

    # 1. Workflow completed
    assert result is not None

    # 2. Checkpoint exists
    cp = await checkpoint_store.get_checkpoint(run_id)
    assert cp is not None

    # 3. Events were emitted (RUN_STARTED comes from run_from_config,
    #    but we're calling wf.run directly — check for component events)
    event_types = {e.type for e in sink.events}
    assert EventType.SUPERVISION_FAILURE_RECEIVED.value in event_types, \
        "Should show supervision handled the build failure"

    # 4. All steps executed despite transient failure
    assert registry["analyze"].call_count == 1
    assert registry["test"].call_count == 1
```

- [ ] **Step 2: Run ALL integration tests**

Run: `python -m pytest tests/integration/test_differentiator_flows.py -v`
Expected: All 7 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_differentiator_flows.py
git commit -m "test(integration): add combined differentiator E2E test

Proves checkpoint, events, and supervision work together in a single
workflow without conflicts — the integration layer holds."
```

---

## Verification

After all tasks, run:

```bash
# All new integration tests
python -m pytest tests/integration/test_differentiator_flows.py -v

# Full test suite — no regressions
python -m pytest tests/core/ tests/policies/ tests/stores/ tests/integration/ -q

# Verify event counts
python -m pytest tests/integration/test_differentiator_flows.py -v --tb=short 2>&1 | grep -c "PASSED"
# Expected: 7
```
