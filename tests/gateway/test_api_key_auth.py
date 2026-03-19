"""Tests for API key authentication dependency."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from miniautogen.gateway.app import create_app
from miniautogen.stores.in_memory_run_store import InMemoryRunStore


@pytest.fixture()
def run_store() -> InMemoryRunStore:
    return InMemoryRunStore()


@pytest.fixture()
def app_with_api_key(run_store):
    """App configured with an API key requirement."""
    return create_app(run_store=run_store, event_store=None, api_key="test-secret-key")


@pytest.fixture()
def app_without_api_key(run_store):
    """App configured without API key (no auth required)."""
    return create_app(run_store=run_store, event_store=None, api_key=None)


BASE_URL = "http://test"


@pytest.mark.asyncio
async def test_request_with_valid_api_key_succeeds(app_with_api_key):
    async with AsyncClient(
        transport=ASGITransport(app=app_with_api_key), base_url=BASE_URL
    ) as client:
        resp = await client.get(
            "/api/v1/runs",
            headers={"X-API-Key": "test-secret-key"},
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_request_without_api_key_returns_401(app_with_api_key):
    async with AsyncClient(
        transport=ASGITransport(app=app_with_api_key), base_url=BASE_URL
    ) as client:
        resp = await client.get("/api/v1/runs")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Missing or invalid API key"


@pytest.mark.asyncio
async def test_request_with_wrong_api_key_returns_401(app_with_api_key):
    async with AsyncClient(
        transport=ASGITransport(app=app_with_api_key), base_url=BASE_URL
    ) as client:
        resp = await client.get(
            "/api/v1/runs",
            headers={"X-API-Key": "wrong-key"},
        )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Missing or invalid API key"


@pytest.mark.asyncio
async def test_health_endpoint_bypasses_auth(app_with_api_key):
    """Health check should work without API key for load balancer probes."""
    async with AsyncClient(
        transport=ASGITransport(app=app_with_api_key), base_url=BASE_URL
    ) as client:
        resp = await client.get("/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_no_api_key_configured_allows_all_requests(app_without_api_key):
    """When no API key is configured, all requests should pass through."""
    async with AsyncClient(
        transport=ASGITransport(app=app_without_api_key), base_url=BASE_URL
    ) as client:
        resp = await client.get("/api/v1/runs")
    assert resp.status_code == 200
