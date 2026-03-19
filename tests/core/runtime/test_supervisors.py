"""Tests for the Supervisor protocol and StepSupervisor implementation."""

from __future__ import annotations

import pytest

from miniautogen.core.contracts.enums import ErrorCategory, SupervisionStrategy
from miniautogen.core.contracts.supervision import StepSupervision
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.runtime.supervisors import StepSupervisor, Supervisor


class TestSupervisorProtocol:
    """The Supervisor protocol is runtime-checkable."""

    def test_step_supervisor_satisfies_protocol(self) -> None:
        sink = InMemoryEventSink()
        supervisor = StepSupervisor(event_sink=sink)
        assert isinstance(supervisor, Supervisor)


class TestStepSupervisorForcedOverrides:
    """Forced overrides by error category -- always apply regardless of config."""

    @pytest.mark.asyncio
    async def test_permanent_forces_stop(self) -> None:
        """PERMANENT errors always STOP, even if strategy is RESTART."""
        sink = InMemoryEventSink()
        sv = StepSupervisor(event_sink=sink)
        supervision = StepSupervision(strategy=SupervisionStrategy.RESTART, max_restarts=10)

        decision = await sv.handle_failure(
            child_id="step-1",
            error=RuntimeError("code bug"),
            error_category=ErrorCategory.PERMANENT,
            supervision=supervision,
            restart_count=0,
        )

        assert decision.action == SupervisionStrategy.STOP
        assert "forced" in decision.reason.lower() or "permanent" in decision.reason.lower()

    @pytest.mark.asyncio
    async def test_validation_forces_stop(self) -> None:
        """VALIDATION errors always STOP."""
        sink = InMemoryEventSink()
        sv = StepSupervisor(event_sink=sink)
        supervision = StepSupervision(strategy=SupervisionStrategy.RESTART, max_restarts=10)

        decision = await sv.handle_failure(
            child_id="step-1",
            error=ValueError("bad input"),
            error_category=ErrorCategory.VALIDATION,
            supervision=supervision,
            restart_count=0,
        )

        assert decision.action == SupervisionStrategy.STOP

    @pytest.mark.asyncio
    async def test_configuration_forces_escalate(self) -> None:
        """CONFIGURATION errors always ESCALATE."""
        sink = InMemoryEventSink()
        sv = StepSupervisor(event_sink=sink)
        supervision = StepSupervision(strategy=SupervisionStrategy.RESTART, max_restarts=10)

        decision = await sv.handle_failure(
            child_id="step-1",
            error=RuntimeError("missing API key"),
            error_category=ErrorCategory.CONFIGURATION,
            supervision=supervision,
            restart_count=0,
        )

        assert decision.action == SupervisionStrategy.ESCALATE

    @pytest.mark.asyncio
    async def test_state_consistency_forces_escalate(self) -> None:
        """STATE_CONSISTENCY errors always ESCALATE."""
        sink = InMemoryEventSink()
        sv = StepSupervisor(event_sink=sink)
        supervision = StepSupervision(strategy=SupervisionStrategy.RESTART, max_restarts=10)

        decision = await sv.handle_failure(
            child_id="step-1",
            error=RuntimeError("data mismatch"),
            error_category=ErrorCategory.STATE_CONSISTENCY,
            supervision=supervision,
            restart_count=0,
        )

        assert decision.action == SupervisionStrategy.ESCALATE


class TestStepSupervisorCircuitBreaker:
    """Circuit breaker is CUMULATIVE (not windowed)."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_at_threshold(self) -> None:
        """After circuit_breaker_threshold total failures, STOP."""
        sink = InMemoryEventSink()
        sv = StepSupervisor(event_sink=sink)
        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESTART,
            max_restarts=100,  # high so restart budget is not the limit
            circuit_breaker_threshold=3,
        )

        # First 2 failures: should RESTART (under threshold)
        for i in range(2):
            decision = await sv.handle_failure(
                child_id="step-1",
                error=ConnectionError("transient"),
                error_category=ErrorCategory.TRANSIENT,
                supervision=supervision,
                restart_count=i,
            )
            assert decision.action == SupervisionStrategy.RESTART

        # 3rd failure: circuit breaker opens -> STOP
        decision = await sv.handle_failure(
            child_id="step-1",
            error=ConnectionError("transient"),
            error_category=ErrorCategory.TRANSIENT,
            supervision=supervision,
            restart_count=2,
        )
        assert decision.action == SupervisionStrategy.STOP

    @pytest.mark.asyncio
    async def test_circuit_breaker_emits_event(self) -> None:
        """SUPERVISION_CIRCUIT_OPENED event is emitted when breaker opens."""
        sink = InMemoryEventSink()
        sv = StepSupervisor(event_sink=sink)
        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESTART,
            max_restarts=100,
            circuit_breaker_threshold=1,
        )

        await sv.handle_failure(
            child_id="step-1",
            error=ConnectionError("down"),
            error_category=ErrorCategory.TRANSIENT,
            supervision=supervision,
            restart_count=0,
        )

        event_types = [e.type for e in sink.events]
        assert "supervision_circuit_opened" in event_types


class TestStepSupervisorRestartBudget:
    """Restart budget is WINDOWED."""

    @pytest.mark.asyncio
    async def test_restart_within_budget(self) -> None:
        """Restarts allowed when under max_restarts within window."""
        sink = InMemoryEventSink()
        sv = StepSupervisor(event_sink=sink)
        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESTART,
            max_restarts=2,
            restart_window_seconds=60.0,
            circuit_breaker_threshold=100,
        )

        decision = await sv.handle_failure(
            child_id="step-1",
            error=ConnectionError("transient"),
            error_category=ErrorCategory.TRANSIENT,
            supervision=supervision,
            restart_count=0,
        )
        assert decision.action == SupervisionStrategy.RESTART

    @pytest.mark.asyncio
    async def test_restart_budget_exceeded_escalates(self) -> None:
        """When max_restarts reached within window, ESCALATE."""
        sink = InMemoryEventSink()
        sv = StepSupervisor(event_sink=sink)
        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESTART,
            max_restarts=2,
            restart_window_seconds=60.0,
            circuit_breaker_threshold=100,
        )

        # Exhaust restart budget
        for i in range(2):
            await sv.handle_failure(
                child_id="step-1",
                error=ConnectionError("transient"),
                error_category=ErrorCategory.TRANSIENT,
                supervision=supervision,
                restart_count=i,
            )

        # 3rd attempt: budget exhausted -> ESCALATE
        decision = await sv.handle_failure(
            child_id="step-1",
            error=ConnectionError("transient"),
            error_category=ErrorCategory.TRANSIENT,
            supervision=supervision,
            restart_count=2,
        )
        assert decision.action == SupervisionStrategy.ESCALATE

    @pytest.mark.asyncio
    async def test_escalation_emits_event(self) -> None:
        """SUPERVISION_ESCALATED event is emitted on escalation."""
        sink = InMemoryEventSink()
        sv = StepSupervisor(event_sink=sink)
        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESTART,
            max_restarts=0,
            circuit_breaker_threshold=100,
        )

        await sv.handle_failure(
            child_id="step-1",
            error=ConnectionError("transient"),
            error_category=ErrorCategory.TRANSIENT,
            supervision=supervision,
            restart_count=0,
        )

        event_types = [e.type for e in sink.events]
        assert "supervision_escalated" in event_types


class TestStepSupervisorConfiguredStrategy:
    """When no forced override or budget limit, apply configured strategy."""

    @pytest.mark.asyncio
    async def test_stop_strategy(self) -> None:
        """STOP strategy returns STOP immediately."""
        sink = InMemoryEventSink()
        sv = StepSupervisor(event_sink=sink)
        supervision = StepSupervision(strategy=SupervisionStrategy.STOP)

        decision = await sv.handle_failure(
            child_id="step-1",
            error=ConnectionError("any"),
            error_category=ErrorCategory.TRANSIENT,
            supervision=supervision,
            restart_count=0,
        )
        assert decision.action == SupervisionStrategy.STOP

    @pytest.mark.asyncio
    async def test_escalate_strategy(self) -> None:
        """ESCALATE strategy returns ESCALATE."""
        sink = InMemoryEventSink()
        sv = StepSupervisor(event_sink=sink)
        supervision = StepSupervision(strategy=SupervisionStrategy.ESCALATE)

        decision = await sv.handle_failure(
            child_id="step-1",
            error=ConnectionError("any"),
            error_category=ErrorCategory.TRANSIENT,
            supervision=supervision,
            restart_count=0,
        )
        assert decision.action == SupervisionStrategy.ESCALATE

    @pytest.mark.asyncio
    async def test_resume_returns_decision(self) -> None:
        """RESUME returns decision with action=RESUME, should_checkpoint=True."""
        sink = InMemoryEventSink()
        sv = StepSupervisor(event_sink=sink)
        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESUME,
            max_restarts=5,
            circuit_breaker_threshold=100,
        )

        decision = await sv.handle_failure(
            child_id="step-1",
            error=ConnectionError("any"),
            error_category=ErrorCategory.TRANSIENT,
            supervision=supervision,
            restart_count=0,
        )

        assert decision.action == SupervisionStrategy.RESUME
        assert decision.should_checkpoint is True


class TestStepSupervisorAuditTrail:
    """Every decision emits SUPERVISION_FAILURE_RECEIVED and SUPERVISION_DECISION_MADE events."""

    @pytest.mark.asyncio
    async def test_failure_received_event_payload(self) -> None:
        """SUPERVISION_FAILURE_RECEIVED has exception type, category, message, attempt, step_id."""
        sink = InMemoryEventSink()
        sv = StepSupervisor(event_sink=sink)
        supervision = StepSupervision(strategy=SupervisionStrategy.STOP)

        await sv.handle_failure(
            child_id="step-1",
            error=ConnectionError("network down"),
            error_category=ErrorCategory.TRANSIENT,
            supervision=supervision,
            restart_count=3,
        )

        failure_events = [e for e in sink.events if e.type == "supervision_failure_received"]
        assert len(failure_events) == 1
        payload = failure_events[0].payload_dict()
        assert payload["exception_type"] == "ConnectionError"
        assert payload["error_category"] == "transient"
        assert payload["message"] == "ConnectionError"
        assert payload["attempt"] == 3
        assert payload["step_id"] == "step-1"

    @pytest.mark.asyncio
    async def test_decision_made_event_payload(self) -> None:
        """SUPERVISION_DECISION_MADE has action, reason, restart_count, was_forced_override."""
        sink = InMemoryEventSink()
        sv = StepSupervisor(event_sink=sink)
        supervision = StepSupervision(strategy=SupervisionStrategy.RESTART, max_restarts=10)

        # PERMANENT forces STOP -- so was_forced_override=True
        await sv.handle_failure(
            child_id="step-1",
            error=RuntimeError("bug"),
            error_category=ErrorCategory.PERMANENT,
            supervision=supervision,
            restart_count=0,
        )

        decision_events = [e for e in sink.events if e.type == "supervision_decision_made"]
        assert len(decision_events) == 1
        payload = decision_events[0].payload_dict()
        assert payload["action"] == "stop"
        assert payload["was_forced_override"] is True
        assert payload["restart_count"] == 0

    @pytest.mark.asyncio
    async def test_restart_emits_restart_started(self) -> None:
        """RESTART decision emits SUPERVISION_RESTART_STARTED."""
        sink = InMemoryEventSink()
        sv = StepSupervisor(event_sink=sink)
        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESTART,
            max_restarts=5,
            circuit_breaker_threshold=100,
        )

        await sv.handle_failure(
            child_id="step-1",
            error=ConnectionError("transient"),
            error_category=ErrorCategory.TRANSIENT,
            supervision=supervision,
            restart_count=0,
        )

        event_types = [e.type for e in sink.events]
        assert "supervision_restart_started" in event_types

    @pytest.mark.asyncio
    async def test_non_forced_override_flag(self) -> None:
        """TRANSIENT with RESTART strategy: was_forced_override=False."""
        sink = InMemoryEventSink()
        sv = StepSupervisor(event_sink=sink)
        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESTART,
            max_restarts=5,
            circuit_breaker_threshold=100,
        )

        await sv.handle_failure(
            child_id="step-1",
            error=ConnectionError("transient"),
            error_category=ErrorCategory.TRANSIENT,
            supervision=supervision,
            restart_count=0,
        )

        decision_events = [e for e in sink.events if e.type == "supervision_decision_made"]
        assert len(decision_events) == 1
        payload = decision_events[0].payload_dict()
        assert payload["was_forced_override"] is False


class TestPhantomRestartTimestamps:
    """Document that restart timestamps are recorded optimistically.

    The supervisor records the restart timestamp BEFORE the caller confirms
    the restart succeeded. This is fail-safe: over-counting exhausts the
    budget sooner (safe), under-counting would allow extra retries (unsafe).
    """

    @pytest.mark.asyncio
    async def test_restart_timestamp_recorded_on_decision(self) -> None:
        """Timestamp is recorded when the RESTART decision is made, not after."""
        sink = InMemoryEventSink()
        sv = StepSupervisor(event_sink=sink)
        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESTART,
            max_restarts=5,
            restart_window_seconds=60.0,
            circuit_breaker_threshold=100,
        )

        # First failure -> RESTART decision
        decision = await sv.handle_failure(
            child_id="step-1",
            error=ConnectionError("transient"),
            error_category=ErrorCategory.TRANSIENT,
            supervision=supervision,
            restart_count=0,
        )
        assert decision.action == SupervisionStrategy.RESTART

        # Verify that the timestamp was recorded (accessible via internal state)
        assert len(sv._restart_timestamps.get("step-1", [])) == 1

    @pytest.mark.asyncio
    async def test_resume_timestamp_also_recorded_optimistically(self) -> None:
        """RESUME decisions also record timestamps optimistically."""
        sink = InMemoryEventSink()
        sv = StepSupervisor(event_sink=sink)
        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESUME,
            max_restarts=5,
            restart_window_seconds=60.0,
            circuit_breaker_threshold=100,
        )

        decision = await sv.handle_failure(
            child_id="step-1",
            error=ConnectionError("transient"),
            error_category=ErrorCategory.TRANSIENT,
            supervision=supervision,
            restart_count=0,
        )
        assert decision.action == SupervisionStrategy.RESUME
        assert decision.should_checkpoint is True

        # Timestamp recorded even though caller hasn't confirmed restart
        assert len(sv._restart_timestamps.get("step-1", [])) == 1
