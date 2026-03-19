from miniautogen.policies.approval import (
    ApprovalGate,
    ApprovalPolicy,
    ApprovalRequest,
    ApprovalResponse,
    AutoApproveGate,
)
from miniautogen.policies.budget import BudgetExceededError, BudgetPolicy, BudgetTracker
from miniautogen.policies.chain import (
    PolicyChain,
    PolicyContext,
    PolicyEvaluator,
    PolicyResult,
)
from miniautogen.policies.effect import EffectPolicy
from miniautogen.policies.execution import ExecutionPolicy
from miniautogen.policies.permission import (
    PermissionDeniedError,
    PermissionPolicy,
    check_permission,
)
from miniautogen.policies.retry import RetryPolicy, build_retrying_call
from miniautogen.policies.timeout import TimeoutScope
from miniautogen.policies.validation import (
    ValidationError,
    ValidationPolicy,
    Validator,
    validate_with_policy,
)

__all__ = [
    "ApprovalGate",
    "ApprovalPolicy",
    "ApprovalRequest",
    "ApprovalResponse",
    "AutoApproveGate",
    "BudgetExceededError",
    "BudgetPolicy",
    "BudgetTracker",
    "EffectPolicy",
    "ExecutionPolicy",
    "PermissionDeniedError",
    "PermissionPolicy",
    "PolicyChain",
    "PolicyContext",
    "PolicyEvaluator",
    "PolicyResult",
    "RetryPolicy",
    "TimeoutScope",
    "ValidationError",
    "ValidationPolicy",
    "Validator",
    "build_retrying_call",
    "check_permission",
    "validate_with_policy",
]

# ── Register policy error mappings with core classifier ───────────────────
# This keeps core/runtime/classifier.py free of policies imports.
from miniautogen.core.contracts.enums import ErrorCategory
from miniautogen.core.runtime.classifier import register_error_mapping

register_error_mapping(PermissionDeniedError, ErrorCategory.VALIDATION)
register_error_mapping(BudgetExceededError, ErrorCategory.VALIDATION)
