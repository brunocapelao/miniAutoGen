"""Tests for WorkflowRuntime — coordination mode for structured workflows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest

from miniautogen.core.contracts.coordination import (
    CoordinationKind,
    CoordinationMode,
    WorkflowPlan,
    WorkflowStep,
)
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.run_result import RunResult
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.runtime.pipeline_runner import PipelineRunner
from miniautogen.core.runtime.workflow_runtime import WorkflowRuntime


def _make_context(run_id: str = "run-1") -> RunContext:
    return RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id="corr-1",
        input_payload="initial-input",
    )


class _FakeAgent:
    """Agent with an async process method that transforms input."""

    def __init__(self, suffix: str) -> None:
        self.suffix = suffix
        self.received_input: Any = None

    async def process(self, input_data: Any) -> Any:
        self.received_input = input_data
        return f"{input_data}-{self.suffix}"


class _FailingAgent:
    """Agent whose process method always raises."""

    async def process(self, input_data: Any) -> Any:
        raise RuntimeError("step exploded")


class _CallableAgent:
    """Agent that is a callable (no process method)."""

    def __init__(self, suffix: str) -> None:
        self.suffix = suffix

    async def __call__(self, input_data: Any) -> Any:
        return f"{input_data}-{self.suffix}"


class _SynthesisAgent:
    """Agent used for synthesis — receives list of outputs."""

    def __init__(self) -> None:
        self.received_input: Any = None

    async def process(self, input_data: Any) -> Any:
        self.received_input = input_data
        if isinstance(input_data, list):
            return "+".join(str(x) for x in input_data)
        return str(input_data)


# ---------- Tests ----------


def test_workflow_runtime_satisfies_protocol() -> None:
    """WorkflowRuntime must be a CoordinationMode."""
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    runtime = WorkflowRuntime(runner=runner)
    assert isinstance(runtime, CoordinationMode)
    assert runtime.kind == CoordinationKind.WORKFLOW


@pytest.mark.asyncio
async def test_sequential_execution_3_steps() -> None:
    """Three sequential steps execute in order; output chains through."""
    agent_a = _FakeAgent("A")
    agent_b = _FakeAgent("B")
    agent_c = _FakeAgent("C")

    registry: dict[str, Any] = {"a": agent_a, "b": agent_b, "c": agent_c}
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    runtime = WorkflowRuntime(runner=runner, agent_registry=registry)

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
    # Chain: initial-input -> initial-input-A -> initial-input-A-B -> initial-input-A-B-C
    assert result.output == "initial-input-A-B-C"
    # Verify ordering
    assert agent_a.received_input == "initial-input"
    assert agent_b.received_input == "initial-input-A"
    assert agent_c.received_input == "initial-input-A-B"


@pytest.mark.asyncio
async def test_fan_out_parallel_execution() -> None:
    """fan_out=True executes steps in parallel; results collected as list."""
    agent_a = _FakeAgent("A")
    agent_b = _FakeAgent("B")
    agent_c = _FakeAgent("C")

    registry: dict[str, Any] = {"a": agent_a, "b": agent_b, "c": agent_c}
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    runtime = WorkflowRuntime(runner=runner, agent_registry=registry)

    plan = WorkflowPlan(
        steps=[
            WorkflowStep(component_name="step1", agent_id="a"),
            WorkflowStep(component_name="step2", agent_id="b"),
            WorkflowStep(component_name="step3", agent_id="c"),
        ],
        fan_out=True,
    )
    ctx = _make_context()
    result = await runtime.run(agents=[], context=ctx, plan=plan)

    assert result.status == "finished"
    # All branches receive the same initial input
    outputs = result.output
    assert isinstance(outputs, list)
    assert len(outputs) == 3
    assert set(outputs) == {"initial-input-A", "initial-input-B", "initial-input-C"}


@pytest.mark.asyncio
async def test_synthesis_agent_runs_after_steps() -> None:
    """When synthesis_agent is set, it receives all step outputs and produces final output."""
    agent_a = _FakeAgent("A")
    agent_b = _FakeAgent("B")
    synth = _SynthesisAgent()

    registry: dict[str, Any] = {"a": agent_a, "b": agent_b, "synth": synth}
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    runtime = WorkflowRuntime(runner=runner, agent_registry=registry)

    plan = WorkflowPlan(
        steps=[
            WorkflowStep(component_name="step1", agent_id="a"),
            WorkflowStep(component_name="step2", agent_id="b"),
        ],
        fan_out=True,
        synthesis_agent="synth",
    )
    ctx = _make_context()
    result = await runtime.run(agents=[], context=ctx, plan=plan)

    assert result.status == "finished"
    # Synthesis agent receives list of outputs and joins them
    assert synth.received_input is not None
    assert isinstance(synth.received_input, list)
    # Output is the synthesis result
    parts = set(result.output.split("+"))
    assert parts == {"initial-input-A", "initial-input-B"}


@pytest.mark.asyncio
async def test_step_failure_returns_error_result() -> None:
    """When a sequential step raises, run returns status='failed' with error."""
    agent_a = _FakeAgent("A")
    failing = _FailingAgent()

    registry: dict[str, Any] = {"a": agent_a, "fail": failing}
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    runtime = WorkflowRuntime(runner=runner, agent_registry=registry)

    plan = WorkflowPlan(
        steps=[
            WorkflowStep(component_name="step1", agent_id="a"),
            WorkflowStep(component_name="step2", agent_id="fail"),
        ],
    )
    ctx = _make_context()
    result = await runtime.run(agents=[], context=ctx, plan=plan)

    assert result.status == "failed"
    assert result.error is not None
    assert "step exploded" in result.error


@pytest.mark.asyncio
async def test_fan_out_one_branch_fails() -> None:
    """When one parallel branch fails, run returns status='failed'."""
    agent_a = _FakeAgent("A")
    failing = _FailingAgent()

    registry: dict[str, Any] = {"a": agent_a, "fail": failing}
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    runtime = WorkflowRuntime(runner=runner, agent_registry=registry)

    plan = WorkflowPlan(
        steps=[
            WorkflowStep(component_name="step1", agent_id="a"),
            WorkflowStep(component_name="step2", agent_id="fail"),
        ],
        fan_out=True,
    )
    ctx = _make_context()
    result = await runtime.run(agents=[], context=ctx, plan=plan)

    assert result.status == "failed"
    assert result.error is not None
    assert "step exploded" in result.error


@pytest.mark.asyncio
async def test_validates_agent_ids_exist() -> None:
    """Referencing an unknown agent_id returns status='failed' immediately."""
    registry: dict[str, Any] = {"a": _FakeAgent("A")}
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    runtime = WorkflowRuntime(runner=runner, agent_registry=registry)

    plan = WorkflowPlan(
        steps=[
            WorkflowStep(component_name="step1", agent_id="a"),
            WorkflowStep(component_name="step2", agent_id="nonexistent"),
        ],
    )
    ctx = _make_context()
    result = await runtime.run(agents=[], context=ctx, plan=plan)

    assert result.status == "failed"
    assert result.error is not None
    assert "nonexistent" in result.error


@pytest.mark.asyncio
async def test_callable_agent_support() -> None:
    """Agents that are async callables (no process method) work as steps."""
    agent = _CallableAgent("X")
    registry: dict[str, Any] = {"x": agent}
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    runtime = WorkflowRuntime(runner=runner, agent_registry=registry)

    plan = WorkflowPlan(
        steps=[WorkflowStep(component_name="step1", agent_id="x")],
    )
    ctx = _make_context()
    result = await runtime.run(agents=[], context=ctx, plan=plan)

    assert result.status == "finished"
    assert result.output == "initial-input-X"


@pytest.mark.asyncio
async def test_events_emitted_for_sequential_run() -> None:
    """Workflow emits RUN_STARTED and RUN_FINISHED events."""
    agent_a = _FakeAgent("A")
    registry: dict[str, Any] = {"a": agent_a}
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    runtime = WorkflowRuntime(runner=runner, agent_registry=registry)

    plan = WorkflowPlan(
        steps=[WorkflowStep(component_name="step1", agent_id="a")],
    )
    ctx = _make_context()
    await runtime.run(agents=[], context=ctx, plan=plan)

    event_types = [e.type for e in event_sink.events]
    assert "run_started" in event_types
    assert "run_finished" in event_types
