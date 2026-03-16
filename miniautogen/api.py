"""Public API — MiniAutoGen Side C.

Usage::

    from miniautogen.api import WorkflowRuntime, DeliberationRuntime, CompositeRuntime

This module re-exports the essential types that define MiniAutoGen's
identity as a multi-agent coordination library.
"""

from miniautogen.core.contracts import (
    ExecutionEvent,
    LoopStopReason,
    Message,
    RunContext,
    RunResult,
    RunStatus,
)
from miniautogen.core.contracts.agent import (
    ConversationalAgent,
    DeliberationAgent,
    WorkflowAgent,
)
from miniautogen.core.contracts.agentic_loop import (
    AgenticLoopState,
    ConversationPolicy,
    RouterDecision,
)
from miniautogen.core.contracts.conversation import Conversation
from miniautogen.core.contracts.coordination import (
    AgenticLoopPlan,
    CoordinationKind,
    CoordinationPlan,
    DeliberationPlan,
    SubrunRequest,
    WorkflowPlan,
    WorkflowStep,
)
from miniautogen.core.contracts.deliberation import (
    Contribution,
    Review,
)
from miniautogen.core.runtime import (
    AgenticLoopRuntime,
    CompositeRuntime,
    DeliberationRuntime,
    PipelineRunner,
    WorkflowRuntime,
)
from miniautogen.core.runtime.composite_runtime import CompositionStep
from miniautogen.pipeline.components.pipelinecomponent import PipelineComponent
from miniautogen.pipeline.pipeline import Pipeline
from miniautogen.backends import (
    AgentDriver,
    BackendCapabilities,
    BackendResolver,
)
from miniautogen.policies.budget import BudgetExceededError, BudgetTracker

__all__ = [
    # Core contracts
    "ExecutionEvent",
    "LoopStopReason",
    "Message",
    "RunContext",
    "RunResult",
    "RunStatus",
    "Conversation",
    # Agent protocols
    "WorkflowAgent",
    "DeliberationAgent",
    "ConversationalAgent",
    # Agentic loop
    "RouterDecision",
    "ConversationPolicy",
    "AgenticLoopState",
    "AgenticLoopPlan",
    # Deliberation (general + specialized)
    "Contribution",
    "Review",
    # Coordination
    "CoordinationKind",
    "CoordinationPlan",
    "DeliberationPlan",
    "WorkflowPlan",
    "WorkflowStep",
    "CompositionStep",
    "SubrunRequest",
    # Runtimes (Coordination Modes)
    "AgenticLoopRuntime",
    "CompositeRuntime",
    "DeliberationRuntime",
    "PipelineRunner",
    "WorkflowRuntime",
    # Pipeline
    "Pipeline",
    "PipelineComponent",
    # Policy enforcement
    "BudgetTracker",
    "BudgetExceededError",
    # Backend driver abstraction
    "AgentDriver",
    "BackendCapabilities",
    "BackendResolver",
]
