"""Contract tests verifying all 3 runtimes satisfy CoordinationMode.

Parametrized tests ensure WorkflowRuntime, AgenticLoopRuntime, and
DeliberationRuntime all conform to the CoordinationMode protocol:
they return RunResult with a RunStatus, and publish lifecycle events.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from miniautogen.core.contracts.agentic_loop import (
    ConversationPolicy,
    RouterDecision,
)
from miniautogen.core.contracts.coordination import (
    AgenticLoopPlan,
    CoordinationMode,
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
from miniautogen.core.contracts.enums import RunStatus
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.run_result import RunResult
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.runtime.agentic_loop_runtime import (
    AgenticLoopRuntime,
)
from miniautogen.core.runtime.deliberation_runtime import (
    DeliberationRuntime,
)
from miniautogen.core.runtime.pipeline_runner import PipelineRunner
from miniautogen.core.runtime.workflow_runtime import WorkflowRuntime

# ------------------------------------------------------------------
# Shared helpers
# ------------------------------------------------------------------


def _make_context(run_id: str = "contract-run-1") -> RunContext:
    return RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id="contract-corr-1",
        input_payload="contract-input",
    )


def _make_runner(
    sink: InMemoryEventSink | None = None,
) -> tuple[PipelineRunner, InMemoryEventSink]:
    event_sink = sink or InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    return runner, event_sink


# ------------------------------------------------------------------
# Fake agents — Workflow
# ------------------------------------------------------------------


class _WorkflowFakeAgent:
    """Minimal WorkflowAgent fake with async process()."""

    def __init__(self, suffix: str = "W") -> None:
        self.suffix = suffix

    async def process(self, input_data: Any) -> Any:
        return f"{input_data}-{self.suffix}"


# ------------------------------------------------------------------
# Fake agents — Agentic Loop
# ------------------------------------------------------------------


class _LoopFakeRouter:
    """Router that terminates immediately on first call."""

    async def route(
        self, conversation_history: list[Any],
    ) -> RouterDecision:
        return RouterDecision(
            current_state_summary="done",
            missing_information="none",
            terminate=True,
        )


class _LoopFakeAgent:
    """Conversational agent that echoes a reply."""

    def __init__(self, name: str = "loop-agent") -> None:
        self.name = name

    async def reply(
        self, message: str, context: dict[str, Any],
    ) -> str:
        return f"{self.name}-reply"


# ------------------------------------------------------------------
# Fake agents — Deliberation
# ------------------------------------------------------------------


class _DeliberationFakeAgent:
    """Minimal deliberation agent supporting the full cycle."""

    def __init__(self, role_name: str) -> None:
        self.role_name = role_name

    async def contribute(self, topic: str) -> ResearchOutput:
        return ResearchOutput(
            role_name=self.role_name,
            section_title=f"{self.role_name} findings",
            findings=[f"Finding from {self.role_name}"],
            facts=[f"Fact from {self.role_name}"],
            recommendation=f"Recommendation from {self.role_name}",
        )

    async def review(
        self, target_role: str, output: ResearchOutput,
    ) -> PeerReview:
        return PeerReview(
            reviewer_role=self.role_name,
            target_role=target_role,
            target_section_title=output.section_title,
            strengths=["ok"],
            concerns=[],
            questions=[],
        )

    async def consolidate(
        self,
        topic: str,
        contributions: list[ResearchOutput],
        reviews: list[PeerReview] | None = None,
    ) -> DeliberationState:
        return DeliberationState(
            review_cycle=1,
            accepted_facts=["fact"],
            leader_decision="proceed",
            is_sufficient=True,
        )

    async def produce_final_document(
        self,
        state: DeliberationState,
        contributions: list[ResearchOutput],
    ) -> FinalDocument:
        return FinalDocument(
            executive_summary="Summary",
            accepted_facts=["fact"],
            open_conflicts=[],
            pending_decisions=[],
            recommendations=["rec"],
            decision_summary="Decision",
            body_markdown="# Body",
        )


# ------------------------------------------------------------------
# Runtime factory: builds (runtime, agents_list, plan, event_sink)
# ------------------------------------------------------------------

_RUNTIME_IDS = ["workflow", "agentic_loop", "deliberation"]


def _build_workflow() -> (
    tuple[WorkflowRuntime, list[Any], WorkflowPlan, InMemoryEventSink]
):
    agent = _WorkflowFakeAgent("W")
    registry: dict[str, Any] = {"w": agent}
    runner, sink = _make_runner()
    runtime = WorkflowRuntime(runner=runner, agent_registry=registry)
    plan = WorkflowPlan(
        steps=[WorkflowStep(component_name="s1", agent_id="w")],
    )
    return runtime, [], plan, sink


def _build_agentic_loop() -> (
    tuple[
        AgenticLoopRuntime,
        list[Any],
        AgenticLoopPlan,
        InMemoryEventSink,
    ]
):
    router = _LoopFakeRouter()
    agent = _LoopFakeAgent("a")
    registry: dict[str, Any] = {"router": router, "a": agent}
    runner, sink = _make_runner()
    runtime = AgenticLoopRuntime(
        runner=runner, agent_registry=registry,
    )
    plan = AgenticLoopPlan(
        router_agent="router",
        participants=["a"],
        policy=ConversationPolicy(max_turns=5),
    )
    return runtime, [], plan, sink


def _build_deliberation() -> (
    tuple[
        DeliberationRuntime,
        list[Any],
        DeliberationPlan,
        InMemoryEventSink,
    ]
):
    agent_a = _DeliberationFakeAgent("alpha")
    agent_b = _DeliberationFakeAgent("beta")
    registry: dict[str, Any] = {"alpha": agent_a, "beta": agent_b}
    runner, sink = _make_runner()
    runtime = DeliberationRuntime(
        runner=runner, agent_registry=registry,
    )
    plan = DeliberationPlan(
        topic="Contract test topic",
        participants=["alpha", "beta"],
        leader_agent="alpha",
        max_rounds=1,
    )
    return runtime, [], plan, sink


_BUILDERS = {
    "workflow": _build_workflow,
    "agentic_loop": _build_agentic_loop,
    "deliberation": _build_deliberation,
}


# ------------------------------------------------------------------
# Contract test 1: protocol conformance
# ------------------------------------------------------------------


@pytest.mark.parametrize("runtime_id", _RUNTIME_IDS)
def test_runtime_satisfies_coordination_protocol(
    runtime_id: str,
) -> None:
    """Each runtime must be recognized as a CoordinationMode.

    CoordinationMode is decorated with @runtime_checkable, so
    isinstance checks work at runtime.
    """
    runtime, _agents, _plan, _sink = _BUILDERS[runtime_id]()
    assert isinstance(runtime, CoordinationMode), (
        f"{type(runtime).__name__} does not satisfy "
        f"CoordinationMode protocol"
    )


# ------------------------------------------------------------------
# Contract test 2: run returns RunResult with a RunStatus
# ------------------------------------------------------------------


@pytest.mark.parametrize("runtime_id", _RUNTIME_IDS)
@pytest.mark.anyio
async def test_runtime_returns_run_result(
    runtime_id: str,
) -> None:
    """run() must return a RunResult whose status is a valid RunStatus."""
    runtime, agents, plan, _sink = _BUILDERS[runtime_id]()
    ctx = _make_context()

    result = await runtime.run(
        agents=agents, context=ctx, plan=plan,
    )

    assert isinstance(result, RunResult), (
        f"{type(runtime).__name__}.run() returned "
        f"{type(result).__name__}, expected RunResult"
    )
    assert result.status in list(RunStatus), (
        f"Unexpected status {result.status!r}"
    )
    assert result.run_id == ctx.run_id


# ------------------------------------------------------------------
# Contract test 3: lifecycle events published
# ------------------------------------------------------------------


@pytest.mark.parametrize("runtime_id", _RUNTIME_IDS)
@pytest.mark.anyio
async def test_runtime_publishes_lifecycle_events(
    runtime_id: str,
) -> None:
    """run() must publish at least a 'started' and 'finished/stopped'
    event via InMemoryEventSink.

    Each runtime uses slightly different event names:
    - Workflow: run_started / run_finished
    - AgenticLoop: agentic_loop_started / agentic_loop_stopped
    - Deliberation: deliberation_started / deliberation_finished
    """
    runtime, agents, plan, sink = _BUILDERS[runtime_id]()
    ctx = _make_context()

    result = await runtime.run(
        agents=agents, context=ctx, plan=plan,
    )
    assert result.status == RunStatus.FINISHED

    event_types = [e.type for e in sink.events]

    assert any("started" in t for t in event_types), (
        f"{type(runtime).__name__} did not emit a 'started' event. "
        f"Events: {event_types}"
    )
    assert any(
        "finished" in t or "stopped" in t for t in event_types
    ), (
        f"{type(runtime).__name__} did not emit a "
        f"'finished' or 'stopped' event. Events: {event_types}"
    )
