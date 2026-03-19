"""Tests for the FastAPI HTTP gateway."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.gateway.app import create_app
from miniautogen.stores.in_memory_event_store import InMemoryEventStore
from miniautogen.stores.in_memory_run_store import InMemoryRunStore


@pytest.fixture()
def run_store() -> InMemoryRunStore:
    return InMemoryRunStore()


@pytest.fixture()
def event_store() -> InMemoryEventStore:
    return InMemoryEventStore()


@pytest.fixture()
def app(run_store: InMemoryRunStore, event_store: InMemoryEventStore):
    return create_app(run_store=run_store, event_store=event_store)


@pytest.fixture()
def base_url() -> str:
    return "http://test"


# -- Health -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_returns_ok(app, base_url):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=base_url) as client:
        resp = await client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body


# -- POST /api/v1/runs --------------------------------------------------------


@pytest.mark.asyncio
async def test_create_run_returns_201_with_pending_status(app, base_url):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=base_url) as client:
        resp = await client.post("/api/v1/runs", json={"input_payload": {"key": "value"}})

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "pending"
    assert body["run_id"]  # non-empty


@pytest.mark.asyncio
async def test_create_run_with_custom_run_id(app, base_url):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=base_url) as client:
        resp = await client.post("/api/v1/runs", json={"run_id": "custom-123"})

    assert resp.status_code == 201
    body = resp.json()
    assert body["run_id"] == "custom-123"


@pytest.mark.asyncio
async def test_create_run_persists_to_store(app, base_url, run_store):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=base_url) as client:
        resp = await client.post(
            "/api/v1/runs",
            json={"run_id": "stored-run", "input_payload": {"x": 1}, "namespace": "test"},
        )

    assert resp.status_code == 201
    stored = await run_store.get_run("stored-run")
    assert stored is not None
    assert stored["status"] == "pending"
    assert stored["input_payload"] == {"x": 1}
    assert stored["namespace"] == "test"


# -- GET /api/v1/runs ---------------------------------------------------------


@pytest.mark.asyncio
async def test_list_runs_returns_all(app, base_url, run_store):
    await run_store.save_run("r1", {"run_id": "r1", "status": "pending"})
    await run_store.save_run("r2", {"run_id": "r2", "status": "finished"})

    async with AsyncClient(transport=ASGITransport(app=app), base_url=base_url) as client:
        resp = await client.get("/api/v1/runs")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2


@pytest.mark.asyncio
async def test_list_runs_filters_by_status(app, base_url, run_store):
    await run_store.save_run("r1", {"run_id": "r1", "status": "pending"})
    await run_store.save_run("r2", {"run_id": "r2", "status": "finished"})

    async with AsyncClient(transport=ASGITransport(app=app), base_url=base_url) as client:
        resp = await client.get("/api/v1/runs", params={"status": "pending"})

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["status"] == "pending"


@pytest.mark.asyncio
async def test_list_runs_empty_when_no_store(base_url):
    app = create_app(run_store=None, event_store=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url=base_url) as client:
        resp = await client.get("/api/v1/runs")

    assert resp.status_code == 200
    assert resp.json() == []


# -- GET /api/v1/runs/{run_id} ------------------------------------------------


@pytest.mark.asyncio
async def test_get_run_returns_details(app, base_url, run_store):
    await run_store.save_run("r1", {
        "run_id": "r1",
        "status": "finished",
        "output": {"result": 42},
        "metadata": {"tag": "test"},
    })

    async with AsyncClient(transport=ASGITransport(app=app), base_url=base_url) as client:
        resp = await client.get("/api/v1/runs/r1")

    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == "r1"
    assert body["status"] == "finished"
    assert body["output"] == {"result": 42}
    assert body["metadata"] == {"tag": "test"}


@pytest.mark.asyncio
async def test_get_run_unknown_id_returns_404(app, base_url):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=base_url) as client:
        resp = await client.get("/api/v1/runs/nonexistent")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_run_no_store_returns_404(base_url):
    app = create_app(run_store=None, event_store=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url=base_url) as client:
        resp = await client.get("/api/v1/runs/any-id")

    assert resp.status_code == 404


# -- POST /api/v1/runs/{run_id}/cancel ----------------------------------------


@pytest.mark.asyncio
async def test_cancel_run_changes_status(app, base_url, run_store):
    await run_store.save_run("r1", {"run_id": "r1", "status": "pending"})

    async with AsyncClient(transport=ASGITransport(app=app), base_url=base_url) as client:
        resp = await client.post("/api/v1/runs/r1/cancel")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "cancelled"

    stored = await run_store.get_run("r1")
    assert stored["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_unknown_run_returns_404(app, base_url):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=base_url) as client:
        resp = await client.post("/api/v1/runs/nonexistent/cancel")

    assert resp.status_code == 404


# -- GET /api/v1/runs/{run_id}/events -----------------------------------------


@pytest.mark.asyncio
async def test_get_events_returns_events(app, base_url, event_store):
    ts = datetime(2025, 1, 1, tzinfo=timezone.utc)
    await event_store.append("r1", ExecutionEvent(
        type="run_started", timestamp=ts, run_id="r1", payload={"key": "val"},
    ))

    async with AsyncClient(transport=ASGITransport(app=app), base_url=base_url) as client:
        resp = await client.get("/api/v1/runs/r1/events")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["type"] == "run_started"
    assert body[0]["run_id"] == "r1"
    assert body[0]["payload"] == {"key": "val"}


@pytest.mark.asyncio
async def test_get_events_with_after_index(app, base_url, event_store):
    ts = datetime(2025, 1, 1, tzinfo=timezone.utc)
    await event_store.append("r1", ExecutionEvent(
        type="run_started", timestamp=ts, run_id="r1",
    ))
    await event_store.append("r1", ExecutionEvent(
        type="run_finished", timestamp=ts, run_id="r1",
    ))

    async with AsyncClient(transport=ASGITransport(app=app), base_url=base_url) as client:
        resp = await client.get("/api/v1/runs/r1/events", params={"after_index": 1})

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["type"] == "run_finished"


@pytest.mark.asyncio
async def test_get_events_no_store_returns_empty(base_url):
    app = create_app(run_store=None, event_store=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url=base_url) as client:
        resp = await client.get("/api/v1/runs/r1/events")

    assert resp.status_code == 200
    assert resp.json() == []
