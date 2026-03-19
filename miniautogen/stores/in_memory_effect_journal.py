"""In-memory implementation of EffectJournal for testing and single-process use."""

from __future__ import annotations

from datetime import datetime

from miniautogen.core.contracts.effect import EffectRecord, EffectStatus
from miniautogen.stores.effect_journal import EffectJournal


class InMemoryEffectJournal(EffectJournal):
    """Dict-backed effect journal.

    Sufficient for testing and single-process use.
    Not suitable for multi-process deduplication.
    """

    def __init__(self) -> None:
        self._records: dict[str, EffectRecord] = {}

    async def register(self, record: EffectRecord) -> None:
        """Persist a new effect record.

        Overwrites any existing record with the same idempotency key.
        Duplicate-completion checks are handled by EffectInterceptor,
        not at the store level.
        """
        self._records[record.idempotency_key] = record

    async def get(self, idempotency_key: str) -> EffectRecord | None:
        """Fetch an effect record by its idempotency key."""
        return self._records.get(idempotency_key)

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

        Creates a new frozen EffectRecord with updated fields
        (since EffectRecord is immutable).
        """
        existing = self._records.get(idempotency_key)
        if existing is None:
            return

        # Build update dict with only the fields that changed
        update_data: dict[str, object] = {"status": status}
        if completed_at is not None:
            update_data["completed_at"] = completed_at
        if result_hash is not None:
            update_data["result_hash"] = result_hash
        if error_info is not None:
            update_data["error_info"] = error_info

        # Create new frozen record with updated fields
        updated = existing.model_copy(update=update_data)
        self._records[idempotency_key] = updated

    async def list_by_run(
        self,
        run_id: str,
        *,
        status: EffectStatus | None = None,
    ) -> list[EffectRecord]:
        """List all effect records for a given run, optionally filtered by status."""
        results = [
            r for r in self._records.values()
            if r.descriptor.run_id == run_id
        ]
        if status is not None:
            results = [r for r in results if r.status == status]
        return results

    async def delete_by_run(self, run_id: str) -> int:
        """Delete all effect records for a given run. Returns count deleted."""
        keys_to_delete = [
            key for key, record in self._records.items()
            if record.descriptor.run_id == run_id
        ]
        for key in keys_to_delete:
            del self._records[key]
        return len(keys_to_delete)
