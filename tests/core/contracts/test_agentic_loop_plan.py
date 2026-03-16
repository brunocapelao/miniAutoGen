"""Tests for AgenticLoopPlan coordination contract."""

import pytest
from pydantic import ValidationError

from miniautogen.core.contracts.agentic_loop import ConversationPolicy
from miniautogen.core.contracts.coordination import (
    AgenticLoopPlan,
    CoordinationKind,
    CoordinationPlan,
)


def test_agentic_loop_plan_is_subclass_of_coordination_plan() -> None:
    assert issubclass(AgenticLoopPlan, CoordinationPlan)


def test_agentic_loop_plan_instance_is_coordination_plan() -> None:
    plan = AgenticLoopPlan(router_agent="router", participants=["a"])
    assert isinstance(plan, CoordinationPlan)


def test_agentic_loop_plan_has_required_fields() -> None:
    plan = AgenticLoopPlan(
        router_agent="router",
        participants=["agent_a", "agent_b"],
        goal="Solve the problem",
    )
    assert plan.router_agent == "router"
    assert plan.participants == ["agent_a", "agent_b"]
    assert plan.goal == "Solve the problem"
    assert isinstance(plan.policy, ConversationPolicy)


def test_agentic_loop_plan_default_policy() -> None:
    plan = AgenticLoopPlan(router_agent="router", participants=["a"])
    assert isinstance(plan.policy, ConversationPolicy)
    assert plan.policy.max_turns == 8
    assert plan.policy.timeout_seconds == 120.0


def test_agentic_loop_plan_default_goal_is_empty() -> None:
    plan = AgenticLoopPlan(router_agent="router", participants=["a"])
    assert plan.goal == ""


def test_agentic_loop_plan_custom_policy() -> None:
    policy = ConversationPolicy(max_turns=20, timeout_seconds=600.0)
    plan = AgenticLoopPlan(
        router_agent="router",
        participants=["a", "b"],
        policy=policy,
    )
    assert plan.policy.max_turns == 20
    assert plan.policy.timeout_seconds == 600.0


def test_coordination_kind_has_agentic_loop() -> None:
    assert CoordinationKind.AGENTIC_LOOP.value == "agentic_loop"


def test_agentic_loop_plan_rejects_empty_participants() -> None:
    with pytest.raises(ValidationError):
        AgenticLoopPlan(router_agent="router", participants=[])


def test_agentic_loop_plan_requires_router_agent() -> None:
    with pytest.raises(ValidationError):
        AgenticLoopPlan(participants=["a"])  # type: ignore[call-arg]


def test_agentic_loop_plan_serialization_roundtrip() -> None:
    plan = AgenticLoopPlan(
        router_agent="router",
        participants=["a", "b"],
        goal="test goal",
        policy=ConversationPolicy(max_turns=5),
    )
    data = plan.model_dump()
    restored = AgenticLoopPlan.model_validate(data)
    assert restored == plan
