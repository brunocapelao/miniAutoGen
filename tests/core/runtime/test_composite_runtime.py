"""Tests for CompositeRuntime — mode composition."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from miniautogen.core.contracts.coordination import (
    CoordinationKind,
    CoordinationPlan,
    DeliberationPlan,
    WorkflowPlan,
    WorkflowStep,
)
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.run_result import RunResult
from miniautogen.core.runtime.composite_runtime import CompositeRuntime, CompositionStep


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context(run_id: str = "run-1", input_payload: Any = "initial") -> RunContext:
    return RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id="corr-1",
        input_payload=input_payload,
    )


class FakeMode:
    """Fake coordination mode that records calls and returns configurable results."""

    def __init__(
        self,
        kind: CoordinationKind = CoordinationKind.WORKFLOW,
        output: Any = "result",
        fail: bool = False,
    ) -> None:
        self.kind = kind
        self._output = output
        self._fail = fail
        self.calls: list[tuple[RunContext, CoordinationPlan]] = []

    async def run(
        self, agents: list[Any], context: RunContext, plan: CoordinationPlan
    ) -> RunResult:
        self.calls.append((context, plan))
        if self._fail:
            return RunResult(run_id=context.run_id, status="failed", error="mode failed")
        return RunResult(run_id=context.run_id, status="finished", output=self._output)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_plan_returns_input_payload() -> None:
    runtime = CompositeRuntime()
    ctx = _make_context(input_payload="hello")
    result = await runtime.run(agents=[], context=ctx, plan=[])
    assert result.status == "finished"
    assert result.output == "hello"


@pytest.mark.asyncio
async def test_single_step_composition() -> None:
    mode = FakeMode(output="step1-out")
    plan_step = CompositionStep(
        mode=mode,
        plan=WorkflowPlan(steps=[WorkflowStep(component_name="a")]),
        label="step1",
    )
    runtime = CompositeRuntime()
    ctx = _make_context()
    result = await runtime.run(agents=[], context=ctx, plan=[plan_step])
    assert result.status == "finished"
    assert result.output == "step1-out"
    assert len(mode.calls) == 1


@pytest.mark.asyncio
async def test_two_step_composition_threads_output() -> None:
    mode1 = FakeMode(output="from-mode1")
    mode2 = FakeMode(output="from-mode2")

    steps = [
        CompositionStep(
            mode=mode1,
            plan=WorkflowPlan(steps=[WorkflowStep(component_name="a")]),
            label="workflow",
        ),
        CompositionStep(
            mode=mode2,
            plan=DeliberationPlan(topic="review", participants=["a"]),
            label="deliberation",
        ),
    ]
    runtime = CompositeRuntime()
    ctx = _make_context(input_payload="seed")
    result = await runtime.run(agents=[], context=ctx, plan=steps)

    assert result.status == "finished"
    assert result.output == "from-mode2"

    # First mode gets original context
    ctx1, _ = mode1.calls[0]
    assert ctx1.input_payload == "seed"

    # Second mode gets output from first mode via with_previous_result
    ctx2, _ = mode2.calls[0]
    assert ctx2.input_payload == "from-mode1"


@pytest.mark.asyncio
async def test_three_step_workflow_deliberation_workflow() -> None:
    """The core innovation: workflow → deliberation → workflow."""
    mode_w1 = FakeMode(kind=CoordinationKind.WORKFLOW, output="prepared")
    mode_d = FakeMode(kind=CoordinationKind.DELIBERATION, output="deliberated")
    mode_w2 = FakeMode(kind=CoordinationKind.WORKFLOW, output="synthesized")

    steps = [
        CompositionStep(
            mode=mode_w1,
            plan=WorkflowPlan(steps=[WorkflowStep(component_name="prepare")]),
            label="prepare",
        ),
        CompositionStep(
            mode=mode_d,
            plan=DeliberationPlan(topic="analyze", participants=["expert"]),
            label="deliberate",
        ),
        CompositionStep(
            mode=mode_w2,
            plan=WorkflowPlan(steps=[WorkflowStep(component_name="synthesize")]),
            label="synthesize",
        ),
    ]
    runtime = CompositeRuntime()
    ctx = _make_context(input_payload="raw-data")
    result = await runtime.run(agents=[], context=ctx, plan=steps)

    assert result.status == "finished"
    assert result.output == "synthesized"

    # Verify chaining
    assert mode_w1.calls[0][0].input_payload == "raw-data"
    assert mode_d.calls[0][0].input_payload == "prepared"
    assert mode_w2.calls[0][0].input_payload == "deliberated"


@pytest.mark.asyncio
async def test_fail_fast_on_step_failure() -> None:
    mode1 = FakeMode(output="ok")
    mode2 = FakeMode(fail=True)
    mode3 = FakeMode(output="should-not-reach")

    steps = [
        CompositionStep(mode=mode1, plan=WorkflowPlan(steps=[])),
        CompositionStep(mode=mode2, plan=WorkflowPlan(steps=[])),
        CompositionStep(mode=mode3, plan=WorkflowPlan(steps=[])),
    ]
    runtime = CompositeRuntime()
    ctx = _make_context()
    result = await runtime.run(agents=[], context=ctx, plan=steps)

    assert result.status == "failed"
    assert len(mode3.calls) == 0  # mode3 was never called


@pytest.mark.asyncio
async def test_custom_input_mapper() -> None:
    mode1 = FakeMode(output={"data": [1, 2, 3], "meta": "info"})
    mode2 = FakeMode(output="processed")

    def custom_mapper(prev_result: RunResult, ctx: RunContext) -> RunContext:
        """Extract just the data field from previous result."""
        return ctx.model_copy(update={"input_payload": prev_result.output["data"]})

    steps = [
        CompositionStep(mode=mode1, plan=WorkflowPlan(steps=[])),
        CompositionStep(
            mode=mode2,
            plan=WorkflowPlan(steps=[]),
            input_mapper=custom_mapper,
        ),
    ]
    runtime = CompositeRuntime()
    ctx = _make_context()
    result = await runtime.run(agents=[], context=ctx, plan=steps)

    assert result.status == "finished"
    # mode2 should have received just the data list, not the full dict
    ctx2, _ = mode2.calls[0]
    assert ctx2.input_payload == [1, 2, 3]


@pytest.mark.asyncio
async def test_custom_output_mapper() -> None:
    mode1 = FakeMode(output="raw-output")

    def enrich_output(result: RunResult) -> RunResult:
        return result.model_copy(
            update={"metadata": {**result.metadata, "enriched": True}}
        )

    steps = [
        CompositionStep(
            mode=mode1,
            plan=WorkflowPlan(steps=[]),
            output_mapper=enrich_output,
        ),
    ]
    runtime = CompositeRuntime()
    ctx = _make_context()
    result = await runtime.run(agents=[], context=ctx, plan=steps)

    assert result.status == "finished"
    assert result.metadata.get("enriched") is True


@pytest.mark.asyncio
async def test_correlation_id_preserved_across_steps() -> None:
    mode1 = FakeMode(output="a")
    mode2 = FakeMode(output="b")

    steps = [
        CompositionStep(mode=mode1, plan=WorkflowPlan(steps=[])),
        CompositionStep(mode=mode2, plan=WorkflowPlan(steps=[])),
    ]
    runtime = CompositeRuntime()
    ctx = _make_context()
    await runtime.run(agents=[], context=ctx, plan=steps)

    # Both modes should have the same correlation_id
    assert mode1.calls[0][0].correlation_id == "corr-1"
    assert mode2.calls[0][0].correlation_id == "corr-1"
