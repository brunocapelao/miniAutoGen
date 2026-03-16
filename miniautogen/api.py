"""Public API — MiniAutoGen Side C.

Usage::

    from miniautogen.api import WorkflowRuntime, DeliberationRuntime, CompositeRuntime

This module re-exports the essential types that define MiniAutoGen's
identity as a multi-agent coordination library.
"""

from miniautogen.core.contracts import Message, RunContext, RunResult, ExecutionEvent
from miniautogen.core.contracts.coordination import (
    CoordinationKind,
    CoordinationPlan,
    DeliberationPlan,
    WorkflowPlan,
    WorkflowStep,
)
from miniautogen.core.runtime import (
    CompositeRuntime,
    DeliberationRuntime,
    PipelineRunner,
    WorkflowRuntime,
)
from miniautogen.core.runtime.composite_runtime import CompositionStep
from miniautogen.pipeline.pipeline import Pipeline
from miniautogen.pipeline.components.pipelinecomponent import PipelineComponent

__all__ = [
    # Core contracts
    "Message",
    "RunContext",
    "RunResult",
    "ExecutionEvent",
    # Coordination
    "CoordinationKind",
    "CoordinationPlan",
    "DeliberationPlan",
    "WorkflowPlan",
    "WorkflowStep",
    "CompositionStep",
    # Runtimes (Coordination Modes)
    "CompositeRuntime",
    "DeliberationRuntime",
    "PipelineRunner",
    "WorkflowRuntime",
    # Pipeline
    "Pipeline",
    "PipelineComponent",
]
