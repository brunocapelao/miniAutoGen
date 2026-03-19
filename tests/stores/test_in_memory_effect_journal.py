"""Tests for InMemoryEffectJournal implementation."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from miniautogen.core.contracts.effect import (
    EffectDescriptor,
    EffectRecord,
    EffectStatus,
)


def _make_descriptor(
    tool_name: str = "send_email",
    run_id: str = "run-1",
    step_id: str = "step-1",
) -> EffectDescriptor:
    return EffectDescriptor(
        effect_type="tool_call",
        tool_name=tool_name,
        args_hash="abc123",
        run_id=run_id,
        step_id=step_id,
    )


def _make_record(
    key: str = "key-1",
    tool_name: str = "send_email",
    run_id: str = "run-1",
    step_id: str = "step-1",
    status: EffectStatus = EffectStatus.PENDING,
) -> EffectRecord:
    return EffectRecord(
        idempotency_key=key,
        descriptor=_make_descriptor(tool_name=tool_name, run_id=run_id, step_id=step_id),
        status=status,
        created_at=datetime.now(timezone.utc),
    )


class TestInMemoryEffectJournalImport:
    def test_import(self) -> None:
        from miniautogen.stores.in_memory_effect_journal import InMemoryEffectJournal  # noqa: F401

    def test_is_subclass_of_abc(self) -> None:
        from miniautogen.stores.effect_journal import EffectJournal
        from miniautogen.stores.in_memory_effect_journal import InMemoryEffectJournal

        assert issubclass(InMemoryEffectJournal, EffectJournal)


@pytest.mark.asyncio
async def test_register_and_get() -> None:
    from miniautogen.stores.in_memory_effect_journal import InMemoryEffectJournal

    journal = InMemoryEffectJournal()
    record = _make_record(key="key-abc")

    await journal.register(record)
    fetched = await journal.get("key-abc")

    assert fetched is not None
    assert fetched.idempotency_key == "key-abc"
    assert fetched.status == EffectStatus.PENDING


@pytest.mark.asyncio
async def test_get_returns_none_for_missing_key() -> None:
    from miniautogen.stores.in_memory_effect_journal import InMemoryEffectJournal

    journal = InMemoryEffectJournal()
    assert await journal.get("nonexistent") is None


@pytest.mark.asyncio
async def test_update_status_to_completed() -> None:
    from miniautogen.stores.in_memory_effect_journal import InMemoryEffectJournal

    journal = InMemoryEffectJournal()
    record = _make_record(key="key-complete")
    await journal.register(record)

    now = datetime.now(timezone.utc)
    await journal.update_status(
        "key-complete",
        EffectStatus.COMPLETED,
        completed_at=now,
        result_hash="sha256-result",
    )

    fetched = await journal.get("key-complete")
    assert fetched is not None
    assert fetched.status == EffectStatus.COMPLETED
    assert fetched.completed_at == now
    assert fetched.result_hash == "sha256-result"


@pytest.mark.asyncio
async def test_update_status_to_failed() -> None:
    from miniautogen.stores.in_memory_effect_journal import InMemoryEffectJournal

    journal = InMemoryEffectJournal()
    record = _make_record(key="key-fail")
    await journal.register(record)

    await journal.update_status(
        "key-fail",
        EffectStatus.FAILED,
        error_info="TimeoutError: connection timed out",
    )

    fetched = await journal.get("key-fail")
    assert fetched is not None
    assert fetched.status == EffectStatus.FAILED
    assert fetched.error_info == "TimeoutError: connection timed out"


@pytest.mark.asyncio
async def test_list_by_run_returns_all_records() -> None:
    from miniautogen.stores.in_memory_effect_journal import InMemoryEffectJournal

    journal = InMemoryEffectJournal()
    await journal.register(_make_record(key="k1", run_id="run-1"))
    await journal.register(_make_record(key="k2", run_id="run-1"))
    await journal.register(_make_record(key="k3", run_id="run-2"))

    results = await journal.list_by_run("run-1")
    assert len(results) == 2
    assert all(r.descriptor.run_id == "run-1" for r in results)


@pytest.mark.asyncio
async def test_list_by_run_filters_by_status() -> None:
    from miniautogen.stores.in_memory_effect_journal import InMemoryEffectJournal

    journal = InMemoryEffectJournal()
    await journal.register(_make_record(key="k1", run_id="run-1"))
    await journal.register(_make_record(key="k2", run_id="run-1"))
    now = datetime.now(timezone.utc)
    await journal.update_status("k1", EffectStatus.COMPLETED, completed_at=now)

    pending = await journal.list_by_run("run-1", status=EffectStatus.PENDING)
    assert len(pending) == 1
    assert pending[0].idempotency_key == "k2"

    completed = await journal.list_by_run("run-1", status=EffectStatus.COMPLETED)
    assert len(completed) == 1
    assert completed[0].idempotency_key == "k1"


@pytest.mark.asyncio
async def test_delete_by_run() -> None:
    from miniautogen.stores.in_memory_effect_journal import InMemoryEffectJournal

    journal = InMemoryEffectJournal()
    await journal.register(_make_record(key="k1", run_id="run-1"))
    await journal.register(_make_record(key="k2", run_id="run-1"))
    await journal.register(_make_record(key="k3", run_id="run-2"))

    deleted = await journal.delete_by_run("run-1")
    assert deleted == 2

    assert await journal.get("k1") is None
    assert await journal.get("k2") is None
    assert await journal.get("k3") is not None


@pytest.mark.asyncio
async def test_delete_by_run_returns_zero_for_missing_run() -> None:
    from miniautogen.stores.in_memory_effect_journal import InMemoryEffectJournal

    journal = InMemoryEffectJournal()
    assert await journal.delete_by_run("nonexistent") == 0
