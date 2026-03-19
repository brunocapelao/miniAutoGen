"""Tests for default_supervision field on DeliberationPlan and AgenticLoopPlan.

Verifies backward compatibility: existing JSON payloads without the field
deserialize correctly with default_supervision=None.
"""

from __future__ import annotations

from miniautogen.core.contracts.coordination import (
    AgenticLoopPlan,
    DeliberationPlan,
)
from miniautogen.core.contracts.enums import SupervisionStrategy
from miniautogen.core.contracts.supervision import StepSupervision


class TestDeliberationPlanDefaultSupervision:
    """DeliberationPlan backward compatibility for default_supervision."""

    def test_no_supervision_field_defaults_to_none(self) -> None:
        plan = DeliberationPlan(topic="test", participants=["alice"])
        assert plan.default_supervision is None

    def test_json_without_supervision_deserializes_to_none(self) -> None:
        raw = {"topic": "test", "participants": ["alice"], "max_rounds": 2}
        plan = DeliberationPlan.model_validate(raw)
        assert plan.default_supervision is None

    def test_supervision_field_round_trips(self) -> None:
        sup = StepSupervision(strategy=SupervisionStrategy.RESTART, max_restarts=2)
        plan = DeliberationPlan(
            topic="test", participants=["alice"], default_supervision=sup
        )
        assert plan.default_supervision is not None
        assert plan.default_supervision.strategy == SupervisionStrategy.RESTART
        assert plan.default_supervision.max_restarts == 2

        # Round-trip through JSON
        data = plan.model_dump()
        restored = DeliberationPlan.model_validate(data)
        assert restored.default_supervision is not None
        assert restored.default_supervision.strategy == SupervisionStrategy.RESTART


class TestAgenticLoopPlanDefaultSupervision:
    """AgenticLoopPlan backward compatibility for default_supervision."""

    def test_no_supervision_field_defaults_to_none(self) -> None:
        plan = AgenticLoopPlan(router_agent="router", participants=["a"])
        assert plan.default_supervision is None

    def test_json_without_supervision_deserializes_to_none(self) -> None:
        raw = {"router_agent": "router", "participants": ["a"], "goal": "test"}
        plan = AgenticLoopPlan.model_validate(raw)
        assert plan.default_supervision is None

    def test_supervision_field_round_trips(self) -> None:
        sup = StepSupervision(strategy=SupervisionStrategy.RESTART, max_restarts=5)
        plan = AgenticLoopPlan(
            router_agent="router",
            participants=["a"],
            default_supervision=sup,
        )
        assert plan.default_supervision is not None
        assert plan.default_supervision.max_restarts == 5

        data = plan.model_dump()
        restored = AgenticLoopPlan.model_validate(data)
        assert restored.default_supervision is not None
        assert restored.default_supervision.max_restarts == 5
