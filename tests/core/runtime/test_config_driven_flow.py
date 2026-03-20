"""Tests for config-driven flow execution helpers.

Covers:
- _build_coordination_from_config with workflow mode
- _build_coordination_from_config with deliberation mode
- _build_coordination_from_config with loop mode
- Unknown mode raises ValueError
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from miniautogen.cli.config import FlowConfig
from miniautogen.core.contracts.coordination import (
    AgenticLoopPlan,
    DeliberationPlan,
    WorkflowPlan,
)
from miniautogen.core.runtime.agentic_loop_runtime import AgenticLoopRuntime
from miniautogen.core.runtime.deliberation_runtime import DeliberationRuntime
from miniautogen.core.runtime.pipeline_runner import (
    PipelineRunner,
    _build_coordination_from_config,
)
from miniautogen.core.runtime.workflow_runtime import WorkflowRuntime


@pytest.fixture()
def runner() -> PipelineRunner:
    return PipelineRunner()


@pytest.fixture()
def agent_registry() -> dict[str, MagicMock]:
    return {
        "researcher": MagicMock(),
        "writer": MagicMock(),
        "reviewer": MagicMock(),
    }


class TestBuildCoordinationWorkflow:
    """Workflow mode produces WorkflowPlan + WorkflowRuntime."""

    def test_returns_workflow_plan_and_runtime(
        self, runner, agent_registry,
    ) -> None:
        flow_config = FlowConfig(
            mode="workflow",
            participants=["researcher", "writer"],
        )

        plan, coord_runtime = _build_coordination_from_config(
            flow_config=flow_config,
            runner=runner,
            agent_registry=agent_registry,
        )

        assert isinstance(plan, WorkflowPlan)
        assert isinstance(coord_runtime, WorkflowRuntime)

    def test_workflow_steps_match_participants(
        self, runner, agent_registry,
    ) -> None:
        flow_config = FlowConfig(
            mode="workflow",
            participants=["researcher", "writer"],
        )

        plan, _ = _build_coordination_from_config(
            flow_config=flow_config,
            runner=runner,
            agent_registry=agent_registry,
        )

        assert len(plan.steps) == 2
        assert plan.steps[0].agent_id == "researcher"
        assert plan.steps[0].component_name == "researcher"
        assert plan.steps[1].agent_id == "writer"
        assert plan.steps[1].component_name == "writer"


class TestBuildCoordinationDeliberation:
    """Deliberation mode produces DeliberationPlan + DeliberationRuntime."""

    def test_returns_deliberation_plan_and_runtime(
        self, runner, agent_registry,
    ) -> None:
        flow_config = FlowConfig(
            mode="deliberation",
            participants=["researcher", "writer"],
            leader="researcher",
            max_rounds=5,
        )

        plan, coord_runtime = _build_coordination_from_config(
            flow_config=flow_config,
            runner=runner,
            agent_registry=agent_registry,
            input_text="Discuss architecture",
        )

        assert isinstance(plan, DeliberationPlan)
        assert isinstance(coord_runtime, DeliberationRuntime)

    def test_deliberation_plan_fields(
        self, runner, agent_registry,
    ) -> None:
        flow_config = FlowConfig(
            mode="deliberation",
            participants=["researcher", "writer"],
            leader="researcher",
            max_rounds=5,
        )

        plan, _ = _build_coordination_from_config(
            flow_config=flow_config,
            runner=runner,
            agent_registry=agent_registry,
            input_text="Discuss architecture",
        )

        assert plan.topic == "Discuss architecture"
        assert plan.participants == ["researcher", "writer"]
        assert plan.max_rounds == 5
        assert plan.leader_agent == "researcher"


class TestBuildCoordinationLoop:
    """Loop mode produces AgenticLoopPlan + AgenticLoopRuntime."""

    def test_returns_loop_plan_and_runtime(
        self, runner, agent_registry,
    ) -> None:
        flow_config = FlowConfig(
            mode="loop",
            participants=["researcher", "writer"],
            router="researcher",
        )

        plan, coord_runtime = _build_coordination_from_config(
            flow_config=flow_config,
            runner=runner,
            agent_registry=agent_registry,
            input_text="Start the research",
        )

        assert isinstance(plan, AgenticLoopPlan)
        assert isinstance(coord_runtime, AgenticLoopRuntime)

    def test_loop_plan_fields(
        self, runner, agent_registry,
    ) -> None:
        flow_config = FlowConfig(
            mode="loop",
            participants=["researcher", "writer"],
            router="researcher",
        )

        plan, _ = _build_coordination_from_config(
            flow_config=flow_config,
            runner=runner,
            agent_registry=agent_registry,
            input_text="Start the research",
        )

        assert plan.router_agent == "researcher"
        assert plan.participants == ["researcher", "writer"]
        assert plan.initial_message == "Start the research"


class TestBuildCoordinationUnknownMode:
    """Unknown mode raises ValueError."""

    def test_raises_on_unknown_mode(
        self, runner, agent_registry,
    ) -> None:
        flow_config = FlowConfig(
            mode="unknown_mode",
            participants=["researcher"],
            target="some.module:func",  # needed to bypass validation
        )
        # Override mode after construction to bypass FlowConfig validation
        object.__setattr__(flow_config, "mode", "unknown_mode")

        with pytest.raises(ValueError, match="Unknown flow mode"):
            _build_coordination_from_config(
                flow_config=flow_config,
                runner=runner,
                agent_registry=agent_registry,
            )
