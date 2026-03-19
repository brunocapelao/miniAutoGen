"""Tests for FlowSupervisor -- manages StepSupervisors per step."""

from __future__ import annotations

import pytest

from miniautogen.core.contracts.enums import ErrorCategory, SupervisionStrategy
from miniautogen.core.contracts.supervision import StepSupervision
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.runtime.flow_supervisor import FlowSupervisor


class TestFlowSupervisorBasic:
    """FlowSupervisor creates StepSupervisors on demand."""

    @pytest.mark.asyncio
    async def test_delegates_to_step_supervisor(self) -> None:
        """FlowSupervisor creates a StepSupervisor and delegates."""
        sink = InMemoryEventSink()
        fsv = FlowSupervisor(event_sink=sink)
        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESTART,
            max_restarts=3,
            circuit_breaker_threshold=100,
        )

        decision = await fsv.handle_step_failure(
            step_id="step-1",
            error=ConnectionError("transient"),
            error_category=ErrorCategory.TRANSIENT,
            supervision=supervision,
            restart_count=0,
        )
        assert decision.action == SupervisionStrategy.RESTART

    @pytest.mark.asyncio
    async def test_default_supervision_fallback_escalate(self) -> None:
        """When supervision is None, system default is ESCALATE."""
        sink = InMemoryEventSink()
        fsv = FlowSupervisor(event_sink=sink)

        decision = await fsv.handle_step_failure(
            step_id="step-1",
            error=ConnectionError("transient"),
            error_category=ErrorCategory.TRANSIENT,
            supervision=None,
            restart_count=0,
        )
        assert decision.action == SupervisionStrategy.ESCALATE


class TestFlowSupervisorFlowCircuitBreaker:
    """Flow-level circuit breaker: total failures across ALL steps."""

    @pytest.mark.asyncio
    async def test_flow_circuit_breaker_opens(self) -> None:
        """After flow_circuit_breaker_threshold total flow failures, STOP."""
        sink = InMemoryEventSink()
        fsv = FlowSupervisor(event_sink=sink, flow_circuit_breaker_threshold=3)
        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESTART,
            max_restarts=100,
            circuit_breaker_threshold=100,
        )

        # Failures across different steps all count toward flow total
        for i, step_id in enumerate(["step-1", "step-2", "step-1"]):
            decision = await fsv.handle_step_failure(
                step_id=step_id,
                error=ConnectionError("transient"),
                error_category=ErrorCategory.TRANSIENT,
                supervision=supervision,
                restart_count=i,
            )

        # 3rd failure hits flow threshold -> STOP
        assert decision.action == SupervisionStrategy.STOP

    @pytest.mark.asyncio
    async def test_flow_circuit_breaker_emits_event(self) -> None:
        """Flow-level breaker emits SUPERVISION_CIRCUIT_OPENED."""
        sink = InMemoryEventSink()
        fsv = FlowSupervisor(event_sink=sink, flow_circuit_breaker_threshold=1)
        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESTART,
            max_restarts=100,
            circuit_breaker_threshold=100,
        )

        await fsv.handle_step_failure(
            step_id="step-1",
            error=ConnectionError("transient"),
            error_category=ErrorCategory.TRANSIENT,
            supervision=supervision,
            restart_count=0,
        )

        event_types = [e.type for e in sink.events]
        assert "supervision_circuit_opened" in event_types


class TestFlowSupervisorStepIsolation:
    """Each step gets its own StepSupervisor instance."""

    @pytest.mark.asyncio
    async def test_separate_step_supervisors(self) -> None:
        """Failures in step-1 don't affect step-2's restart budget."""
        sink = InMemoryEventSink()
        fsv = FlowSupervisor(event_sink=sink, flow_circuit_breaker_threshold=100)
        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESTART,
            max_restarts=1,
            circuit_breaker_threshold=100,
        )

        # step-1 uses its restart
        d1 = await fsv.handle_step_failure(
            step_id="step-1",
            error=ConnectionError("t"),
            error_category=ErrorCategory.TRANSIENT,
            supervision=supervision,
            restart_count=0,
        )
        assert d1.action == SupervisionStrategy.RESTART

        # step-2 has its own budget -- can still restart
        d2 = await fsv.handle_step_failure(
            step_id="step-2",
            error=ConnectionError("t"),
            error_category=ErrorCategory.TRANSIENT,
            supervision=supervision,
            restart_count=0,
        )
        assert d2.action == SupervisionStrategy.RESTART


class TestFlowSupervisorEscalationPropagation:
    """Escalations from steps propagate up."""

    @pytest.mark.asyncio
    async def test_step_escalation_counts_as_flow_failure(self) -> None:
        """Step escalation increments total_flow_failures."""
        sink = InMemoryEventSink()
        fsv = FlowSupervisor(event_sink=sink, flow_circuit_breaker_threshold=2)
        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESTART,
            max_restarts=0,  # Immediately exhaust budget -> ESCALATE
            circuit_breaker_threshold=100,
        )

        # First step escalates (budget=0)
        d1 = await fsv.handle_step_failure(
            step_id="step-1",
            error=ConnectionError("t"),
            error_category=ErrorCategory.TRANSIENT,
            supervision=supervision,
            restart_count=0,
        )
        assert d1.action == SupervisionStrategy.ESCALATE

        # Second step also escalates -> flow breaker should open
        d2 = await fsv.handle_step_failure(
            step_id="step-2",
            error=ConnectionError("t"),
            error_category=ErrorCategory.TRANSIENT,
            supervision=supervision,
            restart_count=0,
        )
        # Flow breaker opened: STOP overrides the step's ESCALATE
        assert d2.action == SupervisionStrategy.STOP
