"""Tests for run_id validation on gateway routes."""

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


# -- RunCreateRequest.run_id validation --


@pytest.mark.asyncio
async def test_create_run_valid_run_id(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.post("/api/v1/runs", json={"run_id": "my-run_123"})
    assert resp.status_code == 201
    assert resp.json()["run_id"] == "my-run_123"


@pytest.mark.asyncio
async def test_create_run_id_too_long_returns_422(app):
    long_id = "a" * 129
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.post("/api/v1/runs", json={"run_id": long_id})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_run_id_with_special_chars_returns_422(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.post("/api/v1/runs", json={"run_id": "run;DROP TABLE"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_run_id_with_spaces_returns_422(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.post("/api/v1/runs", json={"run_id": "run id with spaces"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_run_id_empty_string_returns_422(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.post("/api/v1/runs", json={"run_id": ""})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_run_id_null_generates_uuid(app):
    """When run_id is null/omitted, a UUID is auto-generated."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.post("/api/v1/runs", json={})
    assert resp.status_code == 201
    assert len(resp.json()["run_id"]) == 36  # UUID format


# -- Path parameter run_id validation --


@pytest.mark.asyncio
async def test_get_run_invalid_run_id_returns_422(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.get("/api/v1/runs/invalid;id!")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_cancel_run_invalid_run_id_returns_422(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.post("/api/v1/runs/invalid;id!/cancel")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_events_invalid_run_id_returns_422(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.get("/api/v1/runs/invalid;id!/events")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_run_id_max_128_chars_accepted(app, run_store):
    run_id = "a" * 128
    await run_store.save_run(run_id, {"run_id": run_id, "status": "pending"})
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.get(f"/api/v1/runs/{run_id}")
    assert resp.status_code == 200
