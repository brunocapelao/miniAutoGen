"""Parametrized contract tests for all store implementations."""

import pytest

from miniautogen.stores.in_memory_checkpoint_store import (
    InMemoryCheckpointStore,
)
from miniautogen.stores.in_memory_run_store import InMemoryRunStore


# --- RunStore contract tests ---


@pytest.mark.anyio
async def test_run_store_save_and_get() -> None:
    store = InMemoryRunStore()
    await store.save_run("run-1", {"status": "running"})
    result = await store.get_run("run-1")
    assert result == {"status": "running"}


@pytest.mark.anyio
async def test_run_store_get_missing() -> None:
    store = InMemoryRunStore()
    assert await store.get_run("missing") is None


@pytest.mark.anyio
async def test_run_store_list_all() -> None:
    store = InMemoryRunStore()
    await store.save_run("r1", {"status": "ok"})
    await store.save_run("r2", {"status": "failed"})
    runs = await store.list_runs()
    assert len(runs) == 2


@pytest.mark.anyio
async def test_run_store_list_by_status() -> None:
    store = InMemoryRunStore()
    await store.save_run("r1", {"status": "ok"})
    await store.save_run("r2", {"status": "failed"})
    runs = await store.list_runs(status="ok")
    assert len(runs) == 1
    assert runs[0]["status"] == "ok"


@pytest.mark.anyio
async def test_run_store_list_with_limit() -> None:
    store = InMemoryRunStore()
    for i in range(10):
        await store.save_run(f"r{i}", {"status": "ok"})
    runs = await store.list_runs(limit=3)
    assert len(runs) == 3


@pytest.mark.anyio
async def test_run_store_delete() -> None:
    store = InMemoryRunStore()
    await store.save_run("r1", {"status": "ok"})
    assert await store.delete_run("r1") is True
    assert await store.get_run("r1") is None
    assert await store.delete_run("r1") is False


# --- CheckpointStore contract tests ---


@pytest.mark.anyio
async def test_checkpoint_store_save_and_get() -> None:
    store = InMemoryCheckpointStore()
    await store.save_checkpoint("r1", {"state": "s1"})
    result = await store.get_checkpoint("r1")
    assert result == {"state": "s1"}


@pytest.mark.anyio
async def test_checkpoint_store_get_missing() -> None:
    store = InMemoryCheckpointStore()
    assert await store.get_checkpoint("missing") is None


@pytest.mark.anyio
async def test_checkpoint_store_list_all() -> None:
    store = InMemoryCheckpointStore()
    await store.save_checkpoint("r1", {"state": "s1"})
    await store.save_checkpoint("r2", {"state": "s2"})
    checkpoints = await store.list_checkpoints()
    assert len(checkpoints) == 2


@pytest.mark.anyio
async def test_checkpoint_store_delete() -> None:
    store = InMemoryCheckpointStore()
    await store.save_checkpoint("r1", {"state": "s1"})
    assert await store.delete_checkpoint("r1") is True
    assert await store.get_checkpoint("r1") is None
    assert await store.delete_checkpoint("r1") is False


# --- SessionRecovery tests ---


@pytest.mark.anyio
async def test_recovery_can_resume() -> None:
    from miniautogen.core.runtime.recovery import SessionRecovery

    cs = InMemoryCheckpointStore()
    recovery = SessionRecovery(cs)
    await cs.save_checkpoint("run-1", {"state": "ok"})
    assert await recovery.can_resume("run-1") is True
    assert await recovery.can_resume("run-2") is False


@pytest.mark.anyio
async def test_recovery_load_checkpoint() -> None:
    from miniautogen.core.runtime.recovery import SessionRecovery

    cs = InMemoryCheckpointStore()
    recovery = SessionRecovery(cs)
    await cs.save_checkpoint("run-1", {"state": "saved"})
    data = await recovery.load_checkpoint("run-1")
    assert data == {"state": "saved"}


@pytest.mark.anyio
async def test_recovery_mark_resumed() -> None:
    from miniautogen.core.runtime.recovery import SessionRecovery

    cs = InMemoryCheckpointStore()
    rs = InMemoryRunStore()
    recovery = SessionRecovery(cs, rs)
    await recovery.mark_resumed("run-1")
    run = await rs.get_run("run-1")
    assert run is not None
    assert run["status"] == "resumed"
