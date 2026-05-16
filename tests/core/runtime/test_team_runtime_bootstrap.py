"""Tests for TeamRuntime bootstrap: TeamPlan, CoordinationKind.TEAM, TeamRuntime exists."""

from __future__ import annotations

import pytest

from miniautogen.core.contracts.coordination import (
    CoordinationKind,
    CoordinationMode,
    TeamPlan,
)


def test_coordination_kind_team_exists() -> None:
    """CoordinationKind.TEAM must be defined."""
    assert hasattr(CoordinationKind, "TEAM")
    assert CoordinationKind.TEAM.value == "team"


def test_teamplan_valid() -> None:
    """TeamPlan must accept valid configuration."""
    plan = TeamPlan(
        lead_agent="orchestrator",
        teammates=["legal", "security", "architect"],
        lead_prompt="Synthesize findings",
        teammate_prompts={
            "legal": "Review legal compliance",
            "security": "Audit security",
            "architect": "Review architecture",
        },
        on_teammate_failure="isolate",
    )
    assert plan.lead_agent == "orchestrator"
    assert len(plan.teammates) == 3
    assert plan.on_teammate_failure == "isolate"
    assert plan.max_concurrent_teammates is None


def test_teamplan_lead_not_in_teammates() -> None:
    """lead_agent cannot also appear in teammates."""
    with pytest.raises(ValueError, match="lead_agent cannot also be a teammate"):
        TeamPlan(
            lead_agent="orchestrator",
            teammates=["legal", "orchestrator"],
        )


def test_teamplan_teammates_unique() -> None:
    """teammates must not contain duplicates."""
    with pytest.raises(ValueError, match="teammates must be unique"):
        TeamPlan(
            lead_agent="orchestrator",
            teammates=["legal", "legal"],
        )


def test_teamplan_min_teammates() -> None:
    """teammates must have at least 1 entry."""
    with pytest.raises(ValueError, match="List should have at least 1 item"):
        TeamPlan(
            lead_agent="orchestrator",
            teammates=[],
        )


def test_teamplan_default_on_teammate_failure() -> None:
    """on_teammate_failure must default to 'isolate'."""
    plan = TeamPlan(
        lead_agent="orchestrator",
        teammates=["legal"],
    )
    assert plan.on_teammate_failure == "isolate"


def test_teamplan_max_concurrent_optional() -> None:
    """max_concurrent_teammates must be Optional[int] defaulting to None."""
    plan = TeamPlan(
        lead_agent="orchestrator",
        teammates=["legal", "security"],
    )
    assert plan.max_concurrent_teammates is None

    plan2 = TeamPlan(
        lead_agent="orchestrator",
        teammates=["legal", "security"],
        max_concurrent_teammates=2,
    )
    assert plan2.max_concurrent_teammates == 2


def test_teamplan_extends_coordinationplan() -> None:
    """TeamPlan must be a subclass of CoordinationPlan."""
    plan = TeamPlan(
        lead_agent="orchestrator",
        teammates=["legal"],
    )
    from pydantic import BaseModel

    assert isinstance(plan, BaseModel)


def test_teamruntime_protocol_satisfaction() -> None:
    """TeamRuntime must satisfy CoordinationMode[TeamPlan] protocol."""
    from miniautogen.core.runtime.pipeline_runner import PipelineRunner
    from miniautogen.core.runtime.team_runtime import TeamRuntime

    runner = PipelineRunner()
    runtime = TeamRuntime(runner=runner)
    assert isinstance(runtime, CoordinationMode)
    assert runtime.kind == CoordinationKind.TEAM
