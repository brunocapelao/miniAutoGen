"""Tests for supervision fields on WorkflowStep and WorkflowPlan."""

from __future__ import annotations

from miniautogen.core.contracts.coordination import WorkflowPlan, WorkflowStep
from miniautogen.core.contracts.enums import SupervisionStrategy
from miniautogen.core.contracts.supervision import StepSupervision


class TestWorkflowStepSupervisionField:
    """WorkflowStep gains an optional supervision field."""

    def test_default_supervision_is_none(self) -> None:
        step = WorkflowStep(component_name="s1")
        assert step.supervision is None

    def test_supervision_can_be_set(self) -> None:
        sup = StepSupervision(strategy=SupervisionStrategy.RESTART, max_restarts=2)
        step = WorkflowStep(component_name="s1", supervision=sup)
        assert step.supervision is not None
        assert step.supervision.strategy == SupervisionStrategy.RESTART
        assert step.supervision.max_restarts == 2

    def test_backward_compat_from_dict_without_supervision(self) -> None:
        """Existing stored JSON without supervision field deserializes correctly."""
        data = {"component_name": "s1", "agent_id": "a1", "config": {}}
        step = WorkflowStep.model_validate(data)
        assert step.supervision is None

    def test_from_dict_with_supervision(self) -> None:
        data = {
            "component_name": "s1",
            "supervision": {
                "strategy": "restart",
                "max_restarts": 5,
            },
        }
        step = WorkflowStep.model_validate(data)
        assert step.supervision is not None
        assert step.supervision.strategy == SupervisionStrategy.RESTART
        assert step.supervision.max_restarts == 5


class TestWorkflowPlanDefaultSupervision:
    """WorkflowPlan gains an optional default_supervision field."""

    def test_default_supervision_is_none(self) -> None:
        plan = WorkflowPlan(steps=[WorkflowStep(component_name="s1")])
        assert plan.default_supervision is None

    def test_default_supervision_can_be_set(self) -> None:
        sup = StepSupervision(strategy=SupervisionStrategy.RESTART, max_restarts=3)
        plan = WorkflowPlan(
            steps=[WorkflowStep(component_name="s1")],
            default_supervision=sup,
        )
        assert plan.default_supervision is not None
        assert plan.default_supervision.strategy == SupervisionStrategy.RESTART

    def test_backward_compat_from_dict_without_default_supervision(self) -> None:
        data = {
            "steps": [{"component_name": "s1"}],
            "fan_out": False,
        }
        plan = WorkflowPlan.model_validate(data)
        assert plan.default_supervision is None

    def test_step_supervision_overrides_plan_default(self) -> None:
        """Resolution order: step.supervision > plan.default_supervision."""
        plan_sup = StepSupervision(strategy=SupervisionStrategy.RESTART, max_restarts=1)
        step_sup = StepSupervision(strategy=SupervisionStrategy.STOP)
        plan = WorkflowPlan(
            steps=[WorkflowStep(component_name="s1", supervision=step_sup)],
            default_supervision=plan_sup,
        )
        # Step-level should take priority
        effective = plan.steps[0].supervision or plan.default_supervision
        assert effective is not None
        assert effective.strategy == SupervisionStrategy.STOP
