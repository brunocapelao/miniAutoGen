"""Integration tests for the full Console Server."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from miniautogen.server.app import create_app


def _make_provider() -> MagicMock:
    provider = MagicMock()
    provider.get_config.return_value = {}
    provider.get_agents.return_value = []
    provider.get_pipelines.return_value = []
    provider.get_runs.return_value = []
    provider.get_events.return_value = []
    return provider


def test_full_app_starts():
    provider = _make_provider()
    app = create_app(provider=provider, mode="embedded")
    client = TestClient(app)
    assert client.get("/api/v1/workspace").status_code == 200
    assert client.get("/api/v1/agents").status_code == 200
    assert client.get("/api/v1/flows").status_code == 200
    assert client.get("/api/v1/runs").status_code == 200


def test_websocket_endpoint_exists():
    provider = _make_provider()
    app = create_app(provider=provider, mode="embedded")
    routes = [r.path for r in app.routes]
    assert "/ws/runs/{run_id}" in routes


def test_standalone_mode_no_websocket():
    provider = _make_provider()
    app = create_app(provider=provider, mode="standalone")
    routes = [r.path for r in app.routes]
    assert "/ws/runs/{run_id}" not in routes
