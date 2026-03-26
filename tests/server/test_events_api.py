"""Tests for the /api/v1/events REST endpoint."""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from miniautogen.server.app import create_app


@pytest.fixture
def app_with_events(mock_provider: MagicMock):
    """Create app and populate broadcaster with sample events."""
    app = create_app(provider=mock_provider, mode="embedded")
    broadcaster = app.state.event_broadcaster

    # Populate buffer synchronously via deque (bypass async publish for test setup)
    for i in range(5):
        broadcaster._buffer.append({"type": "step", "index": i})
    broadcaster._buffer.append({"type": "run_started", "run_id": "r1"})
    broadcaster._buffer.append({"type": "run_finished", "run_id": "r1"})

    return app


@pytest.fixture
def events_client(app_with_events) -> TestClient:
    return TestClient(app_with_events)


def test_get_recent_events(events_client: TestClient):
    """GET /api/v1/events returns list of recent events."""
    resp = events_client.get("/api/v1/events")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 7


def test_get_recent_events_with_limit(events_client: TestClient):
    """GET /api/v1/events?limit=3 returns only last 3 events."""
    resp = events_client.get("/api/v1/events?limit=3")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3


def test_get_recent_events_filter_by_type(events_client: TestClient):
    """GET /api/v1/events?type=run_started returns only matching events."""
    resp = events_client.get("/api/v1/events?type=run_started")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["type"] == "run_started"


def test_get_events_empty_broadcaster(mock_provider: MagicMock):
    """GET /api/v1/events returns empty list when no events."""
    app = create_app(provider=mock_provider, mode="embedded")
    client = TestClient(app)
    resp = client.get("/api/v1/events")
    assert resp.status_code == 200
    assert resp.json() == []
