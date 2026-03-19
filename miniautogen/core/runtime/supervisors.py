"""Supervisor protocol and StepSupervisor implementation.

StepSupervisor decides what to do when a workflow step fails:
RESTART, STOP, or ESCALATE. Decision algorithm (priority order):

1. Forced override by error category (PERMANENT->STOP, VALIDATION->STOP,
   CONFIGURATION->ESCALATE, STATE_CONSISTENCY->ESCALATE)
2. Circuit breaker: cumulative failures >= threshold -> STOP
3. Restart budget: windowed restarts >= max_restarts -> ESCALATE
4. Configured strategy (RESUME raises NotImplementedError)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

from miniautogen.core.contracts.enums import ErrorCategory, SupervisionStrategy
from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.contracts.supervision import StepSupervision, SupervisionDecision
from miniautogen.core.events.event_sink import EventSink
from miniautogen.core.events.types import EventType
from miniautogen.observability import get_logger

_logger = get_logger(__name__)

# Forced overrides: these categories ALWAYS produce a specific action
# regardless of configured strategy.
_FORCED_OVERRIDES: dict[ErrorCategory, SupervisionStrategy] = {
    ErrorCategory.PERMANENT: SupervisionStrategy.STOP,
    ErrorCategory.VALIDATION: SupervisionStrategy.STOP,
    ErrorCategory.CONFIGURATION: SupervisionStrategy.ESCALATE,
    ErrorCategory.STATE_CONSISTENCY: SupervisionStrategy.ESCALATE,
}


@runtime_checkable
class Supervisor(Protocol):
    """Protocol for fault supervision handlers."""

    async def handle_failure(
        self,
        *,
        child_id: str,
        error: BaseException,
        error_category: ErrorCategory,
        supervision: StepSupervision,
        restart_count: int,
    ) -> SupervisionDecision: ...


class StepSupervisor:
    """Per-step fault supervisor with forced overrides, circuit breaker, and windowed restarts.

    Internal state:
    - _failure_counts: per child_id, cumulative (never reset)
    - _restart_timestamps: per child_id, for windowed restart counting
    """

    def __init__(self, *, event_sink: EventSink) -> None:
        self._event_sink = event_sink
        self._failure_counts: dict[str, int] = {}
        self._restart_timestamps: dict[str, list[datetime]] = {}

    async def handle_failure(
        self,
        *,
        child_id: str,
        error: BaseException,
        error_category: ErrorCategory,
        supervision: StepSupervision,
        restart_count: int,
    ) -> SupervisionDecision:
        """Decide what action to take after a step failure.

        Decision priority:
        1. Forced override by error category
        2. Circuit breaker (cumulative failures >= threshold)
        3. Restart budget (windowed restarts >= max_restarts)
        4. Configured strategy
        """
        # Track cumulative failures
        self._failure_counts[child_id] = self._failure_counts.get(child_id, 0) + 1
        total_failures = self._failure_counts[child_id]

        # Emit SUPERVISION_FAILURE_RECEIVED
        await self._emit_failure_received(
            child_id=child_id,
            error=error,
            error_category=error_category,
            attempt=restart_count,
        )

        # 1. Forced override by error category
        if error_category in _FORCED_OVERRIDES:
            action = _FORCED_OVERRIDES[error_category]
            reason = (
                f"Forced override: {error_category.value} errors always "
                f"{action.value}"
            )
            decision = SupervisionDecision(
                action=action,
                reason=reason,
            )
            await self._emit_decision(
                child_id=child_id,
                decision=decision,
                restart_count=restart_count,
                was_forced_override=True,
            )
            if action == SupervisionStrategy.ESCALATE:
                await self._emit_escalated(child_id=child_id, reason=reason)
            return decision

        # 2. Circuit breaker (cumulative)
        if total_failures >= supervision.circuit_breaker_threshold:
            reason = (
                f"Circuit breaker opened: {total_failures} cumulative failures "
                f">= threshold {supervision.circuit_breaker_threshold}"
            )
            decision = SupervisionDecision(
                action=SupervisionStrategy.STOP,
                reason=reason,
            )
            await self._emit_circuit_opened(child_id=child_id, total_failures=total_failures)
            await self._emit_decision(
                child_id=child_id,
                decision=decision,
                restart_count=restart_count,
                was_forced_override=False,
            )
            return decision

        # 3. Restart budget (windowed)
        now = datetime.now(timezone.utc)
        timestamps = self._restart_timestamps.setdefault(child_id, [])
        window_start = now.timestamp() - supervision.restart_window_seconds
        recent_restarts = [
            ts for ts in timestamps if ts.timestamp() >= window_start
        ]
        self._restart_timestamps[child_id] = recent_restarts  # prune old entries

        if len(recent_restarts) >= supervision.max_restarts:
            reason = (
                f"Restart budget exhausted: {len(recent_restarts)} restarts "
                f"within {supervision.restart_window_seconds}s window "
                f"(max: {supervision.max_restarts})"
            )
            decision = SupervisionDecision(
                action=SupervisionStrategy.ESCALATE,
                reason=reason,
            )
            await self._emit_escalated(child_id=child_id, reason=reason)
            await self._emit_decision(
                child_id=child_id,
                decision=decision,
                restart_count=restart_count,
                was_forced_override=False,
            )
            return decision

        # 4. Configured strategy
        strategy = supervision.strategy

        if strategy == SupervisionStrategy.RESUME:
            raise NotImplementedError(
                "RESUME requires Phase 4 CheckpointManager. "
                "Use RESTART, STOP, or ESCALATE."
            )

        if strategy == SupervisionStrategy.RESTART:
            reason = (
                f"Restarting step '{child_id}': "
                f"{error_category.value} error, attempt {restart_count + 1}"
            )
            decision = SupervisionDecision(
                action=SupervisionStrategy.RESTART,
                reason=reason,
            )
            # Record the restart timestamp
            self._restart_timestamps[child_id].append(now)
            await self._emit_restart_started(child_id=child_id, attempt=restart_count + 1)
            await self._emit_decision(
                child_id=child_id,
                decision=decision,
                restart_count=restart_count,
                was_forced_override=False,
            )
            return decision

        if strategy == SupervisionStrategy.ESCALATE:
            reason = f"Escalating step '{child_id}': configured strategy is ESCALATE"
            decision = SupervisionDecision(
                action=SupervisionStrategy.ESCALATE,
                reason=reason,
            )
            await self._emit_escalated(child_id=child_id, reason=reason)
            await self._emit_decision(
                child_id=child_id,
                decision=decision,
                restart_count=restart_count,
                was_forced_override=False,
            )
            return decision

        # strategy == STOP
        reason = f"Stopping step '{child_id}': configured strategy is STOP"
        decision = SupervisionDecision(
            action=SupervisionStrategy.STOP,
            reason=reason,
        )
        await self._emit_decision(
            child_id=child_id,
            decision=decision,
            restart_count=restart_count,
            was_forced_override=False,
        )
        return decision

    # ------------------------------------------------------------------
    # Event emission helpers
    # ------------------------------------------------------------------

    async def _emit_failure_received(
        self,
        *,
        child_id: str,
        error: BaseException,
        error_category: ErrorCategory,
        attempt: int,
    ) -> None:
        event = ExecutionEvent(
            type=EventType.SUPERVISION_FAILURE_RECEIVED.value,
            timestamp=datetime.now(timezone.utc),
            scope="step_supervisor",
            payload={
                "step_id": child_id,
                "exception_type": type(error).__name__,
                "error_category": error_category.value,
                "message": str(error),
                "attempt": attempt,
            },
        )
        _logger.warning(
            "supervision_failure_received",
            step_id=child_id,
            exception_type=type(error).__name__,
            error_category=error_category.value,
            attempt=attempt,
        )
        await self._event_sink.publish(event)

    async def _emit_decision(
        self,
        *,
        child_id: str,
        decision: SupervisionDecision,
        restart_count: int,
        was_forced_override: bool,
    ) -> None:
        log_level = "error" if decision.action in (
            SupervisionStrategy.STOP, SupervisionStrategy.ESCALATE
        ) else "warning"

        event = ExecutionEvent(
            type=EventType.SUPERVISION_DECISION_MADE.value,
            timestamp=datetime.now(timezone.utc),
            scope="step_supervisor",
            payload={
                "step_id": child_id,
                "action": decision.action.value,
                "reason": decision.reason,
                "restart_count": restart_count,
                "was_forced_override": was_forced_override,
            },
        )
        getattr(_logger, log_level)(
            "supervision_decision_made",
            step_id=child_id,
            action=decision.action.value,
            reason=decision.reason,
            was_forced_override=was_forced_override,
        )
        await self._event_sink.publish(event)

    async def _emit_restart_started(
        self,
        *,
        child_id: str,
        attempt: int,
    ) -> None:
        event = ExecutionEvent(
            type=EventType.SUPERVISION_RESTART_STARTED.value,
            timestamp=datetime.now(timezone.utc),
            scope="step_supervisor",
            payload={
                "step_id": child_id,
                "attempt": attempt,
            },
        )
        _logger.warning(
            "supervision_restart_started",
            step_id=child_id,
            attempt=attempt,
        )
        await self._event_sink.publish(event)

    async def _emit_circuit_opened(
        self,
        *,
        child_id: str,
        total_failures: int,
    ) -> None:
        event = ExecutionEvent(
            type=EventType.SUPERVISION_CIRCUIT_OPENED.value,
            timestamp=datetime.now(timezone.utc),
            scope="step_supervisor",
            payload={
                "step_id": child_id,
                "total_failures": total_failures,
            },
        )
        _logger.error(
            "supervision_circuit_opened",
            step_id=child_id,
            total_failures=total_failures,
        )
        await self._event_sink.publish(event)

    async def _emit_escalated(
        self,
        *,
        child_id: str,
        reason: str,
    ) -> None:
        event = ExecutionEvent(
            type=EventType.SUPERVISION_ESCALATED.value,
            timestamp=datetime.now(timezone.utc),
            scope="step_supervisor",
            payload={
                "step_id": child_id,
                "reason": reason,
            },
        )
        _logger.error(
            "supervision_escalated",
            step_id=child_id,
            reason=reason,
        )
        await self._event_sink.publish(event)
