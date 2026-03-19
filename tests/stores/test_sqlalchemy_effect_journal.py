"""Tests for SQLAlchemyEffectJournal implementation."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
import pytest_asyncio

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
        descriptor=_make_descriptor(
            tool_name=tool_name, run_id=run_id, step_id=step_id,
        ),
        status=status,
        created_at=datetime.now(timezone.utc),
    )


@pytest_asyncio.fixture
async def journal():
    from miniautogen.stores.sqlalchemy_effect_journal import SQLAlchemyEffectJournal

    j = SQLAlchemyEffectJournal(db_url="sqlite+aiosqlite:///:memory:")
    await j.init_db()
    return j


@pytest.mark.asyncio
async def test_import() -> None:
    from miniautogen.stores.sqlalchemy_effect_journal import SQLAlchemyEffectJournal  # noqa: F401


@pytest.mark.asyncio
async def test_is_subclass_of_abc() -> None:
    from miniautogen.stores.effect_journal import EffectJournal
    from miniautogen.stores.sqlalchemy_effect_journal import SQLAlchemyEffectJournal

    assert issubclass(SQLAlchemyEffectJournal, EffectJournal)


@pytest.mark.asyncio
async def test_register_and_get(journal) -> None:
    record = _make_record(key="key-abc")
    await journal.register(record)
    fetched = await journal.get("key-abc")

    assert fetched is not None
    assert fetched.idempotency_key == "key-abc"
    assert fetched.status == EffectStatus.PENDING
    assert fetched.descriptor.tool_name == "send_email"
    assert fetched.descriptor.run_id == "run-1"


@pytest.mark.asyncio
async def test_get_returns_none_for_missing_key(journal) -> None:
    assert await journal.get("nonexistent") is None


@pytest.mark.asyncio
async def test_update_status_to_completed(journal) -> None:
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
    assert fetched.result_hash == "sha256-result"


@pytest.mark.asyncio
async def test_update_status_to_failed(journal) -> None:
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
async def test_list_by_run(journal) -> None:
    await journal.register(_make_record(key="k1", run_id="run-1"))
    await journal.register(_make_record(key="k2", run_id="run-1"))
    await journal.register(_make_record(key="k3", run_id="run-2"))

    results = await journal.list_by_run("run-1")
    assert len(results) == 2
    assert all(r.descriptor.run_id == "run-1" for r in results)


@pytest.mark.asyncio
async def test_list_by_run_filters_by_status(journal) -> None:
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
async def test_delete_by_run(journal) -> None:
    await journal.register(_make_record(key="k1", run_id="run-1"))
    await journal.register(_make_record(key="k2", run_id="run-1"))
    await journal.register(_make_record(key="k3", run_id="run-2"))

    deleted = await journal.delete_by_run("run-1")
    assert deleted == 2

    assert await journal.get("k1") is None
    assert await journal.get("k2") is None
    assert await journal.get("k3") is not None


@pytest.mark.asyncio
async def test_delete_by_run_returns_zero_for_missing(journal) -> None:
    assert await journal.delete_by_run("nonexistent") == 0


@pytest.mark.asyncio
async def test_register_overwrites_existing(journal) -> None:
    """Registering with the same key overwrites the record."""
    record1 = _make_record(key="k1", tool_name="tool_a")
    record2 = _make_record(key="k1", tool_name="tool_b")

    await journal.register(record1)
    await journal.register(record2)

    fetched = await journal.get("k1")
    assert fetched is not None
    assert fetched.descriptor.tool_name == "tool_b"
