"""Tests for error message sanitization in EffectInterceptor."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from miniautogen.core.contracts.effect import EffectRecord, EffectStatus
from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.effect_interceptor import EffectInterceptor
from miniautogen.core.events.event_sink import EventSink
from miniautogen.stores.effect_journal import EffectJournal


class CapturingEventSink(EventSink):
    """Event sink that captures all published events."""

    def __init__(self):
        self.events: list[ExecutionEvent] = []

    async def publish(self, event: ExecutionEvent) -> None:
        self.events.append(event)


class InMemoryJournal(EffectJournal):
    """Minimal in-memory journal for testing."""

    def __init__(self):
        self._records: dict[str, EffectRecord] = {}
        self.last_error_info: str | None = None

    async def register(self, record: EffectRecord) -> None:
        self._records[record.idempotency_key] = record

    async def get(self, idempotency_key: str) -> EffectRecord | None:
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
        record = self._records.get(idempotency_key)
        if record:
            # EffectRecord may be frozen; store the error_info separately
            self.last_error_info = error_info

    async def list_by_run(
        self,
        run_id: str,
        *,
        status: EffectStatus | None = None,
    ) -> list[EffectRecord]:
        return [
            r for r in self._records.values()
            if r.descriptor.run_id == run_id
            and (status is None or r.status == status)
        ]

    async def delete_by_run(self, run_id: str) -> int:
        keys = [
            k for k, r in self._records.items()
            if r.descriptor.run_id == run_id
        ]
        for k in keys:
            del self._records[k]
        return len(keys)


@pytest.fixture()
def event_sink():
    return CapturingEventSink()


@pytest.fixture()
def journal():
    return InMemoryJournal()


@pytest.fixture()
def interceptor(journal, event_sink):
    return EffectInterceptor(journal=journal, event_sink=event_sink)


@pytest.mark.asyncio
async def test_failed_effect_does_not_store_raw_error_message(interceptor, journal):
    """The error_info stored in journal must NOT contain str(exc).

    It should only contain type(exc).__name__ to prevent leaking
    sensitive information.
    """
    async def failing_tool():
        raise RuntimeError("Connection to db://admin:password@secret-host:5432 failed")

    with pytest.raises(RuntimeError):
        await interceptor.execute(
            run_id="run-1",
            step_id="step-1",
            tool_name="db_connect",
            args={},
            tool_fn=failing_tool,
        )

    # Check that the stored error_info does not contain sensitive details
    assert hasattr(journal, "last_error_info")
    assert "password" not in journal.last_error_info
    assert "secret-host" not in journal.last_error_info
    assert journal.last_error_info == "RuntimeError"
