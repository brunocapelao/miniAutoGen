"""Supervision contracts for per-step fault recovery configuration."""

from __future__ import annotations

from typing import Any

from pydantic import ConfigDict

from miniautogen.core.contracts.base import MiniAutoGenBaseModel
from miniautogen.core.contracts.enums import SupervisionStrategy


class StepSupervision(MiniAutoGenBaseModel):
    """Immutable per-step supervision policy.

    Attached to WorkflowStep, WorkflowPlan (flow-level default), or AgentSpec.
    Resolution order: step-level > flow-level > agent-level > system default.
    """

    model_config = ConfigDict(frozen=True)

    strategy: SupervisionStrategy = SupervisionStrategy.ESCALATE
    max_restarts: int = 3
    restart_window_seconds: float = 60.0
    circuit_breaker_threshold: int = 5
    heartbeat_interval_seconds: float | None = None
    max_lifetime_seconds: float | None = None


class SupervisionDecision(MiniAutoGenBaseModel):
    """Immutable result returned by a Supervisor after handling a failure.

    Uses tuple-of-tuples for metadata to preserve immutability,
    matching the ExecutionEvent.payload pattern.
    """

    model_config = ConfigDict(frozen=True)

    action: SupervisionStrategy
    reason: str
    should_checkpoint: bool = False
    metadata: tuple[tuple[str, Any], ...] = ()
