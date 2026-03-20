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


@pytest.mark.anyio
async def test_clean_sessions_with_older_than() -> None:
    """Only delete runs older than N days."""
    store = InMemoryRunStore()
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    await store.save_run("run-recent", {
        "run_id": "run-recent",
        "status": "completed",
        "created_at": now,
    })
    # Clean with older_than=1 should NOT delete recent run
    count = await clean_sessions(store, older_than_days=1)
    assert count == 0
    assert await store.get_run("run-recent") is not None


@pytest.mark.anyio
async def test_clean_sessions_with_old_run() -> None:
    """Delete runs older than N days."""
    store = InMemoryRunStore()
    await store.save_run("run-old", {
        "run_id": "run-old",
        "status": "completed",
        "created_at": "2020-01-01T00:00:00+00:00",
    })
    count = await clean_sessions(store, older_than_days=1)
    assert count == 1


@pytest.mark.anyio
async def test_clean_sessions_unparseable_date_skipped() -> None:
    """Runs with unparseable dates are skipped (not deleted)."""
    store = InMemoryRunStore()
    await store.save_run("run-bad-date", {
        "run_id": "run-bad-date",
        "status": "completed",
        "created_at": "not-a-date",
    })
    count = await clean_sessions(store, older_than_days=1)
    assert count == 0
    assert await store.get_run("run-bad-date") is not None


@pytest.mark.anyio
async def test_list_sessions_with_limit() -> None:
    """Limit parameter restricts results."""
    store = InMemoryRunStore()
    for i in range(10):
        await store.save_run(f"run-{i}", {"status": "completed"})
    runs = await list_sessions(store, limit=3)
    assert len(runs) == 3


def test_create_store_warns_on_db_config() -> None:
    """Warns when database config provided but ignored."""
    import warnings

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        store = create_store_from_config(
            {"url": "sqlite+aiosqlite:///test.db"},
        )
        assert isinstance(store, InMemoryRunStore)
        assert len(w) == 1
        assert "not yet supported" in str(w[0].message).lower()


def test_create_store_returns_sqlalchemy_when_url_set() -> None:
    """When database_config has a URL, create_store_from_config returns SQLAlchemyRunStore."""
    from miniautogen.stores.sqlalchemy_run_store import SQLAlchemyRunStore

    store = create_store_from_config({"url": "sqlite+aiosqlite:///test.db"})
    assert isinstance(store, SQLAlchemyRunStore)


def test_create_store_returns_in_memory_when_no_url() -> None:
    """When database_config has no URL, returns InMemoryRunStore."""
    store = create_store_from_config({})
    assert isinstance(store, InMemoryRunStore)


def test_create_store_returns_in_memory_when_none() -> None:
    """When database_config is None, returns InMemoryRunStore."""
    store = create_store_from_config(None)
    assert isinstance(store, InMemoryRunStore)
