"""Tests for request body size limit (1MB max)."""

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


@pytest.mark.asyncio
async def test_small_request_body_accepted(app):
    """Normal-sized request should succeed."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.post("/api/v1/runs", json={"input_payload": {"key": "value"}})
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_oversized_request_body_returns_413(app):
    """Request body >1MB should return 413."""
    # Create a payload slightly over 1MB
    large_value = "x" * (1024 * 1024 + 1)
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.post(
            "/api/v1/runs",
            json={"input_payload": {"data": large_value}},
        )
    assert resp.status_code == 413
