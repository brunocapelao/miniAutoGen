"""Coordination contracts for the Side C architecture.

Defines the protocol and plans that coordination modes must follow.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel, Field

from miniautogen.core.contracts.agentic_loop import ConversationPolicy
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.run_result import RunResult


class CoordinationKind(str, Enum):
    """Identifies which coordination mode is in use."""

    WORKFLOW = "workflow"
    DELIBERATION = "deliberation"


class CoordinationPlan(BaseModel):
    """Envelope base for all coordination plans."""

    pass


PlanT = TypeVar("PlanT", bound=CoordinationPlan)


@runtime_checkable
class CoordinationMode(Protocol[PlanT]):
    """Interface that every coordination mode must implement.

    Generic in PlanT to force each mode to declare its plan type.
    This eliminates **kwargs as an escape hatch and guarantees type safety
    in composition.
    """

    kind: CoordinationKind

    async def run(
        self, agents: list[Any], context: RunContext, plan: PlanT
    ) -> RunResult: ...


# --- Workflow contracts ---


class WorkflowStep(BaseModel):
    """A single step in a workflow plan.

    ``component_name`` and ``config`` are reserved for the Canonical Patterns
    layer (Camada 3), where steps may resolve to pipeline components rather
    than agents.  The current WorkflowRuntime dispatches by ``agent_id`` only.
    """

    component_name: str
    agent_id: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class WorkflowPlan(CoordinationPlan):
    """Execution plan for WorkflowRuntime.

    Models structured, disciplined execution with optional fan-out
    and synthesis.
    """

    steps: list[WorkflowStep]
    fan_out: bool = False
    synthesis_agent: str | None = None


# --- Deliberation contracts ---


class DeliberationPlan(CoordinationPlan):
    """Execution plan for DeliberationRuntime.

    Models the abstract deliberation cycle, not a specific use case.
    The cycle is: contribution -> critique -> consolidation -> sufficiency -> iteration.
    """

    topic: str = Field(min_length=1)
    participants: list[str] = Field(min_length=1)
    max_rounds: int = Field(default=3, ge=1, le=50)
    leader_agent: str | None = None
    policy: ConversationPolicy = Field(default_factory=ConversationPolicy)
