"""Public API -- MiniAutoGen Side C.

Usage::

    from miniautogen.api import WorkflowRuntime, DeliberationRuntime, CompositeRuntime

This module re-exports the essential types that define MiniAutoGen's
identity as a multi-agent coordination library.
"""

from miniautogen.backends import (
    AgentDriver,
    BackendCapabilities,
    BackendResolver,
)
from miniautogen.core.contracts import (
    AgentHook,
    AgentSpec,
    CoordinationMode,
    CoordinatorCapability,
    EffectDescriptor,
    EffectRecord,
    EffectStatus,
    EngineProfile,
    ErrorCategory,
    ExecutionEvent,
    InMemoryMemoryProvider,
    LoopStopReason,
    McpServerBinding,
    MemoryProfile,
    MemoryProvider,
    Message,
    RunContext,
    RunResult,
    RunStatus,
    RuntimeInterceptor,
    SkillSpec,
    StepSupervision,
    SupervisionDecision,
    SupervisionStrategy,
    ToolSpec,
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
from miniautogen.core.contracts.store import StoreProtocol
from miniautogen.core.contracts.tool import ToolProtocol, ToolResult
from miniautogen.core.effect_interceptor import EffectInterceptor
from miniautogen.core.events.event_sink import (
    CompositeEventSink,
    EventSink,
    FilteredEventSink,
    InMemoryEventSink,
    NullEventSink,
)
from miniautogen.core.events.filters import (
    CompositeFilter,
    EventFilter,
    RunFilter,
    TypeFilter,
)
from miniautogen.core.events.types import EventType
from miniautogen.core.runtime import (
    AgenticLoopRuntime,
    CompositeRuntime,
    DeliberationRuntime,
    PipelineRunner,
    WorkflowRuntime,
)
from miniautogen.core.runtime.composite_runtime import CompositionStep
from miniautogen.core.runtime.recovery import SessionRecovery
from miniautogen.observability.event_logging import LoggingEventSink
from miniautogen.pipeline.components.pipelinecomponent import PipelineComponent
from miniautogen.pipeline.pipeline import Pipeline
from miniautogen.policies.approval import ApprovalGate, AutoApproveGate
from miniautogen.policies.budget import BudgetExceededError, BudgetPolicy, BudgetTracker
from miniautogen.policies.chain import PolicyChain, PolicyContext, PolicyEvaluator, PolicyResult
from miniautogen.policies.effect import EffectPolicy
from miniautogen.policies.execution import ExecutionPolicy
from miniautogen.policies.retry import RetryPolicy
from miniautogen.stores.checkpoint_store import CheckpointStore
from miniautogen.stores.effect_journal import EffectJournal
from miniautogen.stores.in_memory_checkpoint_store import InMemoryCheckpointStore
from miniautogen.stores.in_memory_effect_journal import InMemoryEffectJournal
from miniautogen.stores.in_memory_run_store import InMemoryRunStore
from miniautogen.stores.run_store import RunStore

__all__ = [
    # Core contracts
    "AgentSpec",
    "EngineProfile",
    "ExecutionEvent",
    "LoopStopReason",
    "McpServerBinding",
    "MemoryProfile",
    "Message",
    "RunContext",
    "RunResult",
    "RunStatus",
    "SkillSpec",
    "StoreProtocol",
    "ToolProtocol",
    "ToolResult",
    "ToolSpec",
    "Conversation",
    # Agent protocols
    "WorkflowAgent",
    "DeliberationAgent",
    "ConversationalAgent",
    # Agent hooks and memory
    "AgentHook",
    "MemoryProvider",
    "InMemoryMemoryProvider",
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
    "CoordinationMode",
    "CoordinationPlan",
    "DeliberationPlan",
    "WorkflowPlan",
    "WorkflowStep",
    "CompositionStep",
    "SubrunRequest",
    "CoordinatorCapability",
    # Runtimes (Coordination Modes)
    "AgenticLoopRuntime",
    "CompositeRuntime",
    "DeliberationRuntime",
    "PipelineRunner",
    "WorkflowRuntime",
    # Runtime interceptor
    "RuntimeInterceptor",
    # Pipeline
    "Pipeline",
    "PipelineComponent",
    # Policy enforcement
    "PolicyChain",
    "PolicyContext",
    "PolicyResult",
    "PolicyEvaluator",
    "RetryPolicy",
    "BudgetPolicy",
    "BudgetTracker",
    "BudgetExceededError",
    "ExecutionPolicy",
    # Approval
    "ApprovalGate",
    "AutoApproveGate",
    # Effect engine
    "EffectInterceptor",
    "EffectPolicy",
    "EffectDescriptor",
    "EffectRecord",
    "EffectStatus",
    # Supervision
    "StepSupervision",
    "SupervisionDecision",
    "SupervisionStrategy",
    # Error taxonomy
    "ErrorCategory",
    # Events and observability
    "EventType",
    "EventSink",
    "NullEventSink",
    "CompositeEventSink",
    "CompositeFilter",
    "EventFilter",
    "FilteredEventSink",
    "InMemoryEventSink",
    "LoggingEventSink",
    "RunFilter",
    "TypeFilter",
    # Recovery
    "SessionRecovery",
    # Backend driver abstraction
    "AgentDriver",
    "BackendCapabilities",
    "BackendResolver",
    # Stores
    "CheckpointStore",
    "InMemoryCheckpointStore",
    "EffectJournal",
    "InMemoryEffectJournal",
    "InMemoryRunStore",
    "RunStore",
]
