"""Effect exception classes and data models for the MiniAutoGen effect engine.

Each exception carries an ErrorCategory class attribute for self-classification
by the classify_error() function.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import ConfigDict

from miniautogen.core.contracts.base import MiniAutoGenBaseModel
from miniautogen.core.contracts.enums import ErrorCategory


class EffectStatus(str, Enum):
    """Status of an effect record in the journal.

    Lifecycle: PENDING -> COMPLETED | FAILED
    """

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class EffectDescriptor(MiniAutoGenBaseModel):
    """Immutable description of a side effect to be executed.

    Captures the identity of a tool call for idempotency tracking.
    Uses tuple-of-tuples for metadata to preserve immutability,
    matching the ExecutionEvent.payload pattern.
    """

    model_config = ConfigDict(frozen=True)

    effect_type: str
    tool_name: str
    args_hash: str
    run_id: str
    step_id: str
    metadata: tuple[tuple[str, Any], ...] = ()


class EffectRecord(MiniAutoGenBaseModel):
    """Immutable journal entry tracking execution of a side effect.

    The idempotency_key is SHA-256(run_id + step_id + tool_name + args_hash).
    Attempt number is explicitly EXCLUDED from the key -- including it would
    generate different keys per retry, defeating deduplication.

    error_info MUST be sanitized: no PII, credentials, or payment instrument
    details. Store exception type + generic message only.
    """

    model_config = ConfigDict(frozen=True)

    idempotency_key: str
    descriptor: EffectDescriptor
    status: EffectStatus
    created_at: datetime
    completed_at: datetime | None = None
    result_hash: str | None = None
    error_info: str | None = None


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
