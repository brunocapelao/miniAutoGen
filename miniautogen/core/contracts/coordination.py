"""Coordination contracts for the Side C architecture.

Defines the protocol and plans that coordination modes must follow.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel, Field, model_validator

from miniautogen.core.contracts.agentic_loop import ConversationPolicy
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.run_result import RunResult
from miniautogen.core.contracts.supervision import StepSupervision
from miniautogen.core.contracts.team_task import TaskListConfig


class MailboxConfig(BaseModel):
    enabled: bool = False
    buffer_size: int = 256
    idle_threshold_seconds: float = 5.0


class PlanApprovalConfig(BaseModel):
    timeout_seconds: float = 300.0
    required_for: list[str] = Field(default_factory=list)

# TODO(review): validate plan type matches mode before stabilization (biz-reviewer, 2026-03-16, Low)
_EXPERIMENTAL_CONTRACTS = {"SubrunRequest"}


class CoordinationKind(str, Enum):
    """Identifies which coordination mode is in use."""

    WORKFLOW = "workflow"
    DELIBERATION = "deliberation"
    AGENTIC_LOOP = "agentic_loop"
    TEAM = "team"


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

    async def run(self, agents: list[Any], context: RunContext, plan: PlanT) -> RunResult: ...


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
    supervision: StepSupervision | None = None


class WorkflowPlan(CoordinationPlan):
    """Execution plan for WorkflowRuntime.

    Models structured, disciplined execution with optional fan-out
    and synthesis.
    """

    steps: list[WorkflowStep]
    fan_out: bool = False
    synthesis_agent: str | None = None
    default_supervision: StepSupervision | None = None


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
    default_supervision: StepSupervision | None = None


# --- Agentic Loop contracts ---


class AgenticLoopPlan(CoordinationPlan):
    """Plan for agentic loop coordination — conversational agent interaction."""

    router_agent: str
    participants: list[str] = Field(min_length=1)
    policy: ConversationPolicy = Field(default_factory=ConversationPolicy)
    goal: str = ""
    initial_message: str | None = None
    default_supervision: StepSupervision | None = None


# --- Team contracts ---


class ContributionSummary(BaseModel):
    """Summary of a single teammate's contribution for the lead."""

    teammate: str
    status: Literal["finished", "failed", "cancelled"]
    output: Any = None
    error_category: str | None = None
    error_message: str | None = None


class TeamPlan(CoordinationPlan):
    """Execution plan for TeamRuntime.

    Models a team of peer agents with a lead who consolidates results.
    Each teammate runs as an isolated AgentRuntime concurrently.
    """

    lead_agent: str
    teammates: list[str] = Field(min_length=1)
    lead_prompt: str | None = None
    teammate_prompts: dict[str, str] = Field(default_factory=dict)
    on_teammate_failure: Literal["isolate", "abort_team"] = "isolate"
    max_concurrent_teammates: int | None = Field(default=None, ge=1)

    # Team task list (Spec 016)
    task_list: TaskListConfig | None = None
    lead_runs_first: bool = False

    # Team mailbox (Spec 017)
    mailbox: dict[str, Any] | MailboxConfig | None = None
    plan_approval: dict[str, Any] | PlanApprovalConfig | None = None

    @model_validator(mode="after")
    def _no_dup_no_self(self) -> "TeamPlan":
        if len(set(self.teammates)) != len(self.teammates):
            raise ValueError("teammates must be unique")
        if self.lead_agent in self.teammates:
            raise ValueError("lead_agent cannot also be a teammate")
        return self

    @model_validator(mode="after")
    def _apply_task_list_defaults(self) -> "TeamPlan":
        if self.task_list and self.task_list.enabled:
            if not self.lead_runs_first:
                object.__setattr__(self, "lead_runs_first", True)
        return self


# --- Subrun contracts ---


class SubrunRequest(BaseModel):
    """Request to spawn a sub-run within a composite execution.

    .. stability:: experimental

    Reserved for CompositeRuntime sub-execution. This contract is not
    yet consumed by any runtime and may change without notice.
    """

    mode: CoordinationKind
    plan: CoordinationPlan
    label: str = ""
    input_key: str | None = None
    output_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
