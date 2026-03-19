"""Tests for SQLAlchemy run store SQL LIMIT enforcement."""

from __future__ import annotations

import pytest
import pytest_asyncio

from miniautogen.stores.sqlalchemy_run_store import SQLAlchemyRunStore


@pytest_asyncio.fixture()
async def store():
    """Create an in-memory SQLite-backed store for testing."""
    s = SQLAlchemyRunStore("sqlite+aiosqlite:///:memory:")
    await s.init_db()
    return s


@pytest.mark.asyncio
async def test_list_runs_respects_limit(store):
    """SQL LIMIT should be applied at the database level."""
    for i in range(20):
        await store.save_run(f"run-{i}", {"run_id": f"run-{i}", "status": "pending"})

    runs = await store.list_runs(limit=5)
    assert len(runs) == 5


@pytest.mark.asyncio
async def test_list_runs_with_status_filter_and_limit(store):
    """Filtering by status happens after SQL LIMIT.

    With 10 runs (5 pending, 5 finished), limit=10 fetches all,
    then Python filters to pending -- giving 5 results.
    """
    for i in range(10):
        status = "pending" if i % 2 == 0 else "finished"
        await store.save_run(f"run-{i}", {"run_id": f"run-{i}", "status": status})

    runs = await store.list_runs(status="pending", limit=10)
    assert len(runs) == 5
    assert all(r["status"] == "pending" for r in runs)


@pytest.mark.asyncio
async def test_list_runs_default_limit_caps_results(store):
    """Default limit should prevent loading unlimited rows."""
    for i in range(150):
        await store.save_run(f"run-{i}", {"run_id": f"run-{i}", "status": "pending"})

    runs = await store.list_runs()
    assert len(runs) == 100  # default limit
