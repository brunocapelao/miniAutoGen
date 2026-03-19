"""Tests for StepSupervision and SupervisionDecision frozen models."""

from __future__ import annotations

import pytest

from miniautogen.core.contracts.enums import SupervisionStrategy
from miniautogen.core.contracts.supervision import (
    StepSupervision,
    SupervisionDecision,
)


class TestStepSupervision:
    def test_default_strategy_is_escalate(self) -> None:
        s = StepSupervision()
        assert s.strategy == SupervisionStrategy.ESCALATE

    def test_default_max_restarts(self) -> None:
        s = StepSupervision()
        assert s.max_restarts == 3

    def test_default_circuit_breaker_threshold(self) -> None:
        s = StepSupervision()
        assert s.circuit_breaker_threshold == 5

    def test_frozen_rejects_mutation(self) -> None:
        s = StepSupervision()
        with pytest.raises(Exception):
            s.strategy = SupervisionStrategy.RESTART  # type: ignore[misc]

    def test_custom_values(self) -> None:
        s = StepSupervision(
            strategy=SupervisionStrategy.RESTART,
            max_restarts=5,
            restart_window_seconds=120.0,
            circuit_breaker_threshold=10,
        )
        assert s.strategy == SupervisionStrategy.RESTART
        assert s.max_restarts == 5
        assert s.restart_window_seconds == 120.0
        assert s.circuit_breaker_threshold == 10

    def test_serialization_round_trip(self) -> None:
        s = StepSupervision(strategy=SupervisionStrategy.STOP)
        json_str = s.model_dump_json()
        restored = StepSupervision.model_validate_json(json_str)
        assert restored.strategy == s.strategy
        assert restored.max_restarts == s.max_restarts


class TestSupervisionDecision:
    def test_metadata_is_tuple_of_tuples(self) -> None:
        d = SupervisionDecision(
            action=SupervisionStrategy.STOP,
            reason="permanent error",
        )
        assert isinstance(d.metadata, tuple)
        assert d.metadata == ()

    def test_metadata_with_values(self) -> None:
        d = SupervisionDecision(
            action=SupervisionStrategy.ESCALATE,
            reason="too many failures",
            metadata=(("count", 5), ("last_error", "timeout")),
        )
        assert d.metadata == (("count", 5), ("last_error", "timeout"))

    def test_frozen_rejects_mutation(self) -> None:
        d = SupervisionDecision(
            action=SupervisionStrategy.STOP,
            reason="test",
        )
        with pytest.raises(Exception):
            d.reason = "changed"  # type: ignore[misc]

    def test_should_checkpoint_default_false(self) -> None:
        d = SupervisionDecision(
            action=SupervisionStrategy.RESTART,
            reason="transient error",
        )
        assert d.should_checkpoint is False

    def test_serialization_round_trip(self) -> None:
        d = SupervisionDecision(
            action=SupervisionStrategy.ESCALATE,
            reason="circuit breaker",
            should_checkpoint=True,
            metadata=(("threshold", 5),),
        )
        json_str = d.model_dump_json()
        restored = SupervisionDecision.model_validate_json(json_str)
        assert restored.action == d.action
        assert restored.reason == d.reason
        assert restored.should_checkpoint is True
