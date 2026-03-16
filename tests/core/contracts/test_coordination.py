"""Tests for coordination contracts: CoordinationMode, Plans, and structural subtyping."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from miniautogen.core.contracts.coordination import (
    CoordinationKind,
    CoordinationMode,
    CoordinationPlan,
    DeliberationPlan,
    WorkflowPlan,
    WorkflowStep,
)
from miniautogen.core.contracts.agentic_loop import ConversationPolicy
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.run_result import RunResult


# --- CoordinationKind ---


def test_coordination_kind_has_workflow_and_deliberation() -> None:
    assert CoordinationKind.WORKFLOW == "workflow"
    assert CoordinationKind.DELIBERATION == "deliberation"


def test_coordination_kind_only_has_two_members() -> None:
    assert len(CoordinationKind) == 2


# --- CoordinationPlan ---


def test_coordination_plan_is_base_model() -> None:
    plan = CoordinationPlan()
    assert isinstance(plan, CoordinationPlan)


# --- WorkflowPlan ---


def test_workflow_plan_inherits_coordination_plan() -> None:
    plan = WorkflowPlan(steps=[WorkflowStep(component_name="step1")])
    assert isinstance(plan, CoordinationPlan)


def test_workflow_plan_requires_steps() -> None:
    with pytest.raises(ValidationError):
        WorkflowPlan()  # type: ignore[call-arg]


def test_workflow_plan_models_fan_out_and_synthesis() -> None:
    plan = WorkflowPlan(
        steps=[
            WorkflowStep(component_name="research", agent_id="agent_a"),
            WorkflowStep(component_name="review", agent_id="agent_b"),
        ],
        fan_out=True,
        synthesis_agent="leader",
    )
    assert plan.fan_out is True
    assert plan.synthesis_agent == "leader"
    assert len(plan.steps) == 2


def test_workflow_step_defaults() -> None:
    step = WorkflowStep(component_name="test")
    assert step.agent_id is None
    assert step.config == {}


def test_workflow_plan_serialization_roundtrip() -> None:
    plan = WorkflowPlan(
        steps=[WorkflowStep(component_name="a", config={"key": "val"})],
        fan_out=True,
    )
    data = plan.model_dump()
    restored = WorkflowPlan.model_validate(data)
    assert restored == plan


# --- DeliberationPlan ---


def test_deliberation_plan_inherits_coordination_plan() -> None:
    plan = DeliberationPlan(topic="test", participants=["a", "b"])
    assert isinstance(plan, CoordinationPlan)


def test_deliberation_plan_requires_topic_and_participants() -> None:
    with pytest.raises(ValidationError):
        DeliberationPlan()  # type: ignore[call-arg]

    with pytest.raises(ValidationError):
        DeliberationPlan(topic="test")  # type: ignore[call-arg]


def test_deliberation_plan_defaults() -> None:
    plan = DeliberationPlan(topic="test", participants=["a"])
    assert plan.max_rounds == 3
    assert plan.leader_agent is None
    assert isinstance(plan.policy, ConversationPolicy)


def test_deliberation_plan_custom_policy() -> None:
    plan = DeliberationPlan(
        topic="architecture review",
        participants=["architect", "reviewer", "qa"],
        max_rounds=5,
        leader_agent="architect",
        policy=ConversationPolicy(max_turns=10, timeout_seconds=300.0),
    )
    assert plan.policy.max_turns == 10
    assert plan.policy.timeout_seconds == 300.0


def test_deliberation_plan_serialization_roundtrip() -> None:
    plan = DeliberationPlan(
        topic="test",
        participants=["a", "b"],
        max_rounds=2,
        leader_agent="a",
    )
    data = plan.model_dump()
    restored = DeliberationPlan.model_validate(data)
    assert restored == plan


# --- CoordinationMode protocol (structural subtyping) ---


class _FakeWorkflowMode:
    """Fake that satisfies CoordinationMode[WorkflowPlan] structurally."""

    kind = CoordinationKind.WORKFLOW

    async def run(
        self, agents: list[Any], context: RunContext, plan: WorkflowPlan
    ) -> RunResult:
        return RunResult(run_id="test", status="finished")


class _FakeDeliberationMode:
    """Fake that satisfies CoordinationMode[DeliberationPlan] structurally."""

    kind = CoordinationKind.DELIBERATION

    async def run(
        self, agents: list[Any], context: RunContext, plan: DeliberationPlan
    ) -> RunResult:
        return RunResult(run_id="test", status="finished")


def test_fake_workflow_mode_satisfies_protocol() -> None:
    mode = _FakeWorkflowMode()
    assert isinstance(mode, CoordinationMode)
    assert mode.kind == CoordinationKind.WORKFLOW


def test_fake_deliberation_mode_satisfies_protocol() -> None:
    mode = _FakeDeliberationMode()
    assert isinstance(mode, CoordinationMode)
    assert mode.kind == CoordinationKind.DELIBERATION


class _BrokenMode:
    """Does NOT satisfy CoordinationMode — missing run()."""

    kind = CoordinationKind.WORKFLOW


def test_broken_mode_does_not_satisfy_protocol() -> None:
    mode = _BrokenMode()
    assert not isinstance(mode, CoordinationMode)


# --- DeliberationPlan Field constraints ---


def test_deliberation_plan_rejects_empty_participants() -> None:
    with pytest.raises(ValidationError):
        DeliberationPlan(topic="test", participants=[])


def test_deliberation_plan_rejects_excessive_max_rounds() -> None:
    with pytest.raises(ValidationError):
        DeliberationPlan(topic="test", participants=["a"], max_rounds=100)


def test_deliberation_plan_rejects_empty_topic() -> None:
    with pytest.raises(ValidationError):
        DeliberationPlan(topic="", participants=["a"])
