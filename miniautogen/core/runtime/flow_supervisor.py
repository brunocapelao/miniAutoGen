"""FlowSupervisor -- manages StepSupervisors per workflow step.

Creates a StepSupervisor for each step on demand, tracks total flow-level
failures, and provides a flow-level circuit breaker.
"""

from __future__ import annotations

from datetime import datetime, timezone

from miniautogen.core.contracts.enums import ErrorCategory, SupervisionStrategy
from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.contracts.supervision import StepSupervision, SupervisionDecision
from miniautogen.core.events.event_sink import EventSink
from miniautogen.core.events.types import EventType
from miniautogen.core.runtime.supervisors import StepSupervisor
from miniautogen.observability import get_logger

_logger = get_logger(__name__)

# System default: no supervision configured = ESCALATE on error (fail-fast).
_SYSTEM_DEFAULT_SUPERVISION = StepSupervision(strategy=SupervisionStrategy.ESCALATE)


class FlowSupervisor:
    """Manages supervision for an entire workflow execution.

    - Creates a StepSupervisor per step on demand
    - Tracks total_flow_failures across all steps
    - Flow-level circuit breaker (default threshold: 10)
    - Escalations from steps propagate up and count toward flow failures
    """

    def __init__(
        self,
        *,
        event_sink: EventSink,
        flow_circuit_breaker_threshold: int = 10,
    ) -> None:
        self._event_sink = event_sink
        self._flow_circuit_breaker_threshold = flow_circuit_breaker_threshold
        self._step_supervisors: dict[str, StepSupervisor] = {}
        self._total_flow_failures: int = 0

    def _get_step_supervisor(self, step_id: str) -> StepSupervisor:
        """Get or create a StepSupervisor for the given step."""
        if step_id not in self._step_supervisors:
            self._step_supervisors[step_id] = StepSupervisor(
                event_sink=self._event_sink,
            )
        return self._step_supervisors[step_id]

    async def handle_step_failure(
        self,
        *,
        step_id: str,
        error: BaseException,
        error_category: ErrorCategory,
        supervision: StepSupervision | None,
        restart_count: int,
    ) -> SupervisionDecision:
        """Handle a step failure, applying flow-level circuit breaker first.

        Args:
            step_id: Identifier of the failed step.
            error: The exception that was raised.
            error_category: Classified category of the error.
            supervision: Step-level supervision config (None = system default).
            restart_count: Number of restarts already attempted for this step.

        Returns:
            SupervisionDecision with the action to take.
        """
        self._total_flow_failures += 1
        effective_supervision = supervision or _SYSTEM_DEFAULT_SUPERVISION

        # Flow-level circuit breaker: total failures across ALL steps
        if self._total_flow_failures >= self._flow_circuit_breaker_threshold:
            reason = (
                f"Flow circuit breaker opened: {self._total_flow_failures} "
                f"total failures across all steps "
                f">= threshold {self._flow_circuit_breaker_threshold}"
            )
            await self._emit_flow_circuit_opened(
                step_id=step_id,
                total_failures=self._total_flow_failures,
            )
            decision = SupervisionDecision(
                action=SupervisionStrategy.STOP,
                reason=reason,
            )
            _logger.error(
                "flow_circuit_breaker_opened",
                step_id=step_id,
                total_flow_failures=self._total_flow_failures,
            )
            return decision

        # Delegate to step-level supervisor
        step_sv = self._get_step_supervisor(step_id)
        decision = await step_sv.handle_failure(
            child_id=step_id,
            error=error,
            error_category=error_category,
            supervision=effective_supervision,
            restart_count=restart_count,
        )

        return decision

    async def emit_retry_succeeded(
        self,
        *,
        step_id: str,
        total_attempts: int,
        error_categories_encountered: list[str],
    ) -> None:
        """Emit SUPERVISION_RETRY_SUCCEEDED after a step succeeds on retry.

        Called by WorkflowRuntime when a step that previously failed
        succeeds on a subsequent attempt.
        """
        event = ExecutionEvent(
            type=EventType.SUPERVISION_RETRY_SUCCEEDED.value,
            timestamp=datetime.now(timezone.utc),
            scope="flow_supervisor",
            payload={
                "step_id": step_id,
                "total_attempts": total_attempts,
                "error_categories_encountered": error_categories_encountered,
            },
        )
        _logger.warning(
            "supervision_retry_succeeded",
            step_id=step_id,
            total_attempts=total_attempts,
        )
        await self._event_sink.publish(event)

    async def _emit_flow_circuit_opened(
        self,
        *,
        step_id: str,
        total_failures: int,
    ) -> None:
        event = ExecutionEvent(
            type=EventType.SUPERVISION_CIRCUIT_OPENED.value,
            timestamp=datetime.now(timezone.utc),
            scope="flow_supervisor",
            payload={
                "step_id": step_id,
                "total_failures": total_failures,
                "level": "flow",
            },
        )
        await self._event_sink.publish(event)
