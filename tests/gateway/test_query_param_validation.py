"""Tests for query parameter validation (limit, after_index)."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from miniautogen.gateway.app import create_app
from miniautogen.stores.in_memory_run_store import InMemoryRunStore


@pytest.fixture()
def run_store() -> InMemoryRunStore:
    return InMemoryRunStore()


@pytest.fixture()
def app(run_store):
    return create_app(run_store=run_store, event_store=None)


BASE_URL = "http://test"


# -- limit validation on /api/v1/runs --


@pytest.mark.asyncio
async def test_list_runs_limit_default_is_50(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.get("/api/v1/runs")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_runs_limit_max_1000(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.get("/api/v1/runs", params={"limit": 1000})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_runs_limit_above_1000_returns_422(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.get("/api/v1/runs", params={"limit": 1001})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_runs_limit_zero_returns_422(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.get("/api/v1/runs", params={"limit": 0})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_runs_limit_negative_returns_422(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.get("/api/v1/runs", params={"limit": -1})
    assert resp.status_code == 422


# -- after_index validation on /api/v1/runs/{run_id}/events --


@pytest.mark.asyncio
async def test_events_after_index_zero_accepted(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.get("/api/v1/runs/test-run/events", params={"after_index": 0})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_events_after_index_negative_returns_422(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.get("/api/v1/runs/test-run/events", params={"after_index": -1})
    assert resp.status_code == 422
