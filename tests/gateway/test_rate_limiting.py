"""Tests for rate limiting middleware."""

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
async def test_read_endpoint_allows_requests_within_limit(app):
    """60 reads/minute should be allowed."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        # Send a few requests -- well within the 60/min limit
        for _ in range(5):
            resp = await client.get("/api/v1/runs")
            assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_endpoint_allows_requests_within_limit(app):
    """10 creates/minute should be allowed."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        for _ in range(5):
            resp = await client.post("/api/v1/runs", json={})
            assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_endpoint_returns_429_when_limit_exceeded(app):
    """Exceeding 10 creates/minute should return 429."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        responses = []
        for _ in range(12):
            resp = await client.post("/api/v1/runs", json={})
            responses.append(resp.status_code)
    # First 10 should succeed, the 11th and 12th should be rate limited
    assert responses.count(201) == 10
    assert responses.count(429) == 2


@pytest.mark.asyncio
async def test_health_endpoint_is_not_rate_limited(app):
    """Health checks should never be rate limited."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        for _ in range(100):
            resp = await client.get("/health")
            assert resp.status_code == 200
