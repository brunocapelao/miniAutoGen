"""Error classification function with extensible registry.

Maps Python exceptions to canonical ErrorCategory values.
Custom mappings are checked BEFORE defaults, allowing users
to override for library-specific exceptions (e.g., httpx, aiohttp)
without importing those libraries in core.
"""

from __future__ import annotations

import asyncio

from miniautogen.backends.errors import AgentDriverError, BackendUnavailableError
from miniautogen.core.contracts.effect import EffectError
from miniautogen.core.contracts.enums import ErrorCategory
from miniautogen.policies.budget import BudgetExceededError
from miniautogen.policies.permission import PermissionDeniedError

# ── Default mappings (ORDER MATTERS: subclasses BEFORE superclasses) ──────

_DEFAULT_MAPPINGS: list[tuple[type, ErrorCategory]] = [
    # Priority 1: Self-classifying effect errors (handled specially in classify_error)
    # Priority 2: Timeout
    (TimeoutError, ErrorCategory.TIMEOUT),
    # Priority 3: Cancellation — use asyncio.CancelledError directly to avoid
    # anyio.get_cancelled_exc_class() which requires a running event loop at import time.
    # On the asyncio backend anyio returns this same class; trio users can
    # register trio.Cancelled via register_error_mapping().
    (asyncio.CancelledError, ErrorCategory.CANCELLATION),
    # Priority 4: PermissionError BEFORE OSError (PermissionError is subclass of OSError)
    (PermissionError, ErrorCategory.PERMANENT),
    # Priority 5: Validation errors
    (ValueError, ErrorCategory.VALIDATION),
    (TypeError, ErrorCategory.VALIDATION),
    (PermissionDeniedError, ErrorCategory.VALIDATION),
    # Priority 6: Budget
    (BudgetExceededError, ErrorCategory.VALIDATION),
    # Priority 7: Backend unavailable
    (BackendUnavailableError, ErrorCategory.ADAPTER),
    # Priority 8: Agent driver errors (base class catches all subclasses)
    (AgentDriverError, ErrorCategory.ADAPTER),
    # Priority 9: Network/IO errors (ConnectionError is subclass of OSError)
    (ConnectionError, ErrorCategory.TRANSIENT),
    (OSError, ErrorCategory.TRANSIENT),
    # Priority 10: Programming errors
    (KeyError, ErrorCategory.PERMANENT),
    (AttributeError, ErrorCategory.PERMANENT),
    (NotImplementedError, ErrorCategory.PERMANENT),
]

# ── User-extensible registry ─────────────────────────────────────────────

_custom_mappings: list[tuple[type, ErrorCategory]] = []


def register_error_mapping(exc_class: type, category: ErrorCategory) -> None:
    """Register a custom exception-to-category mapping.

    Custom mappings are checked BEFORE default mappings, allowing users
    to override defaults for library-specific exceptions (e.g., httpx,
    aiohttp, gRPC) without importing those libraries in core.

    Args:
        exc_class: The exception class to map.
        category: The ErrorCategory to assign.
    """
    _custom_mappings.append((exc_class, category))


def classify_error(exc: BaseException) -> ErrorCategory:
    """Map a Python exception to a canonical ErrorCategory.

    Check order:
    1. Self-classifying EffectError subclasses (use exc.category directly)
    2. Custom user mappings (registered via register_error_mapping)
    3. Default mappings (ordered: subclasses before superclasses)
    4. PERMANENT fallback (unknown errors should not retry)

    Args:
        exc: The exception to classify.

    Returns:
        The ErrorCategory for the exception.
    """
    # Priority 1: Self-classifying EffectError subclasses
    if isinstance(exc, EffectError):
        return exc.category

    # Priority 2: Custom mappings (checked first, newest last = last registered wins
    # for overlapping types, but isinstance finds first match)
    for exc_class, category in _custom_mappings:
        if isinstance(exc, exc_class):
            return category

    # Priority 3: Default mappings
    for exc_class, category in _DEFAULT_MAPPINGS:
        if isinstance(exc, exc_class):
            return category

    # Priority 4: Fail-safe fallback
    return ErrorCategory.PERMANENT
