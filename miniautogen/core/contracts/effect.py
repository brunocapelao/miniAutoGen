"""Effect exception classes for the MiniAutoGen effect engine.

Each exception carries an ErrorCategory class attribute for self-classification
by the classify_error() function.
"""

from __future__ import annotations

from miniautogen.core.contracts.enums import ErrorCategory


class EffectError(Exception):
    """Base exception for all effect-related errors.

    Subclasses MUST define a class-level ``category`` attribute
    so that classify_error() can use it directly.
    """

    category: ErrorCategory


class EffectDeniedError(EffectError):
    """Raised when an effect type is not allowed or max-per-step exceeded."""

    category = ErrorCategory.VALIDATION


class EffectDuplicateError(EffectError):
    """Raised when an idempotency key is already COMPLETED."""

    category = ErrorCategory.STATE_CONSISTENCY


class EffectJournalUnavailableError(EffectError):
    """Raised when the effect journal store is unreachable."""

    category = ErrorCategory.ADAPTER
