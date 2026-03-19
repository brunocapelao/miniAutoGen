"""Abstract base class for effect journal persistence.

The EffectJournal tracks side-effect execution records for idempotency.
Implementations must be async-compatible (AnyIO).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from miniautogen.core.contracts.effect import EffectRecord, EffectStatus


class EffectJournal(ABC):
    """Abstract journal for tracking effect execution records.

    Mirrors the store pattern used by RunStore, CheckpointStore, etc.
    All methods are async for compatibility with both in-memory and
    durable (SQLAlchemy) implementations.
    """

    @abstractmethod
    async def register(self, record: EffectRecord) -> None:
        """Persist a new effect record (typically in PENDING status).

        Raises:
            EffectDuplicateError: If a record with the same idempotency_key
                already exists with COMPLETED status.
        """

    @abstractmethod
    async def get(self, idempotency_key: str) -> EffectRecord | None:
        """Fetch an effect record by its idempotency key.

        Returns None if no record exists for the given key.
        """

    @abstractmethod
    async def update_status(
        self,
        idempotency_key: str,
        status: EffectStatus,
        *,
        completed_at: datetime | None = None,
        result_hash: str | None = None,
        error_info: str | None = None,
    ) -> None:
        """Update the status of an existing effect record.

        Used to transition PENDING -> COMPLETED or PENDING -> FAILED.

        Args:
            idempotency_key: The key of the record to update.
            status: New status (COMPLETED or FAILED).
            completed_at: Timestamp of completion (for COMPLETED status).
            result_hash: SHA-256 hash of the result (for audit).
            error_info: Sanitized error description (for FAILED status).
                MUST NOT contain PII, credentials, or payment details.
        """

    @abstractmethod
    async def list_by_run(
        self,
        run_id: str,
        *,
        status: EffectStatus | None = None,
    ) -> list[EffectRecord]:
        """List all effect records for a given run, optionally filtered by status.

        Args:
            run_id: The run identifier.
            status: Optional filter by effect status.

        Returns:
            List of matching EffectRecord instances.
        """

    @abstractmethod
    async def delete_by_run(self, run_id: str) -> int:
        """Delete all effect records for a given run.

        Returns the count of deleted records.
        Used for cleanup after run completion or cancellation.
        """
