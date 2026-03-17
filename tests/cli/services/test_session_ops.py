"""Tests for session_ops service."""

import pytest

from miniautogen.api import InMemoryRunStore
from miniautogen.cli.services.session_ops import (
    clean_sessions,
    create_store_from_config,
    list_sessions,
)


@pytest.mark.anyio
async def test_list_sessions_empty() -> None:
    store = InMemoryRunStore()
    runs = await list_sessions(store)
    assert runs == []


@pytest.mark.anyio
async def test_list_sessions_with_data() -> None:
    store = InMemoryRunStore()
    await store.save_run("run-1", {"status": "completed"})
    await store.save_run("run-2", {"status": "failed"})
    runs = await list_sessions(store)
    assert len(runs) == 2


@pytest.mark.anyio
async def test_list_sessions_filter_status() -> None:
    store = InMemoryRunStore()
    await store.save_run("run-1", {"status": "completed"})
    await store.save_run("run-2", {"status": "failed"})
    runs = await list_sessions(store, status="failed")
    assert len(runs) == 1


@pytest.mark.anyio
async def test_clean_sessions_deletes_completed() -> None:
    store = InMemoryRunStore()
    await store.save_run(
        "run-1", {"run_id": "run-1", "status": "completed"},
    )
    await store.save_run(
        "run-2", {"run_id": "run-2", "status": "failed"},
    )
    count = await clean_sessions(store)
    assert count == 2
    assert await store.get_run("run-1") is None


@pytest.mark.anyio
async def test_clean_sessions_preserves_active() -> None:
    store = InMemoryRunStore()
    await store.save_run(
        "run-1", {"run_id": "run-1", "status": "started"},
    )
    await store.save_run(
        "run-2", {"run_id": "run-2", "status": "completed"},
    )
    count = await clean_sessions(store)
    assert count == 1
    assert await store.get_run("run-1") is not None


@pytest.mark.anyio
async def test_clean_sessions_cleans_finished() -> None:
    """Finished runs (from PipelineRunner) should be cleanable."""
    store = InMemoryRunStore()
    await store.save_run("run-1", {"run_id": "run-1", "status": "finished"})
    count = await clean_sessions(store)
    assert count == 1


@pytest.mark.anyio
async def test_clean_sessions_cleans_timed_out() -> None:
    """Timed-out runs should be cleanable."""
    store = InMemoryRunStore()
    await store.save_run("run-1", {"run_id": "run-1", "status": "timed_out"})
    count = await clean_sessions(store)
    assert count == 1


def test_create_store_returns_in_memory() -> None:
    store = create_store_from_config(None)
    assert isinstance(store, InMemoryRunStore)
