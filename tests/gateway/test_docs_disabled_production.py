"""Tests for disabling auto-docs in production."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from miniautogen.gateway.app import create_app


BASE_URL = "http://test"


@pytest.mark.asyncio
async def test_docs_available_in_development():
    """In development mode, /docs and /redoc should be accessible."""
    app = create_app(env="development")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        docs_resp = await client.get("/docs")
        redoc_resp = await client.get("/redoc")
    assert docs_resp.status_code == 200
    assert redoc_resp.status_code == 200


@pytest.mark.asyncio
async def test_docs_disabled_in_production():
    """In production mode, /docs and /redoc should return 404."""
    app = create_app(env="production")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        docs_resp = await client.get("/docs")
        redoc_resp = await client.get("/redoc")
    assert docs_resp.status_code == 404
    assert redoc_resp.status_code == 404


@pytest.mark.asyncio
async def test_openapi_json_disabled_in_production():
    """In production mode, /openapi.json should also return 404."""
    app = create_app(env="production")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.get("/openapi.json")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_docs_default_is_development():
    """By default (no env param), docs should be available."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.get("/docs")
    assert resp.status_code == 200
