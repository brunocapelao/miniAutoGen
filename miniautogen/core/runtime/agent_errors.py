"""Error hierarchy for the AgentRuntime compositor.

All AgentRuntime exceptions inherit from AgentRuntimeError so callers
can catch the whole category or specific subtypes.

Each subclass MUST define a class-level ``category`` attribute mapping to the
canonical ErrorCategory taxonomy defined in CLAUDE.md section 4.2:
  transient, permanent, validation, timeout, cancellation,
  adapter, configuration, state_consistency
"""

from __future__ import annotations

from miniautogen.core.contracts.enums import ErrorCategory


class AgentRuntimeError(Exception):
    """Base exception for all AgentRuntime compositor errors.

    Subclasses MUST define a class-level ``category`` attribute so that
    classify_error() can use it directly.
    """

    category: ErrorCategory


class DelegationDepthExceededError(AgentRuntimeError):
    """Raised when a delegation chain exceeds the configured maximum depth.

    Prevents infinite delegation loops between agents.
    """

    category = ErrorCategory.VALIDATION


class AgentClosedError(AgentRuntimeError):
    """Raised when an operation is attempted on a closed AgentRuntime.

    State is inconsistent: the runtime has been shut down and can no longer
    accept new turns or tool executions.
    """

    category = ErrorCategory.STATE_CONSISTENCY


class ToolExecutionError(AgentRuntimeError):
    """Raised when a tool invocation fails inside the registry adapter.

    Wraps adapter-level failures (e.g. network errors, filesystem errors)
    that originate in the tool implementation.
    """

    category = ErrorCategory.ADAPTER


class ToolTimeoutError(AgentRuntimeError):
    """Raised when a tool execution exceeds the configured timeout budget.

    The underlying operation was cancelled due to an AnyIO timeout scope.
    """

    category = ErrorCategory.TIMEOUT


class AgentSecurityError(AgentRuntimeError):
    """Raised when an operation violates a security constraint.

    Examples: invalid agent name, path traversal attempt in filesystem tool,
    unauthorized cross-tenant delegation. These failures are permanent —
    retrying will produce the same result.
    """

    category = ErrorCategory.PERMANENT
