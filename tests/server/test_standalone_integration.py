"""Integration tests for standalone Console mode."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from miniautogen.server.app import create_app
from miniautogen.server.standalone_provider import StandaloneProvider
from miniautogen.stores.in_memory_event_store import InMemoryEventStore
from miniautogen.stores.in_memory_run_store import InMemoryRunStore


@pytest.fixture
def standalone_app():
    """Create a standalone app with in-memory stores."""
    base = MagicMock()
    base.get_config.return_value = {"project_name": "standalone-test"}
    base.get_agents.return_value = []
    base.get_pipelines.return_value = []

    run_store = InMemoryRunStore()
    event_store = InMemoryEventStore()

    provider = StandaloneProvider(
        base_provider=base,
        run_store=run_store,
        event_store=event_store,
    )
    app = create_app(provider=provider, mode="standalone")
    return app, run_store, event_store


def test_standalone_list_runs_empty(standalone_app):
    app, _, _ = standalone_app
    client = TestClient(app)
    resp = client.get("/api/v1/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.anyio
async def test_standalone_list_runs_with_data(standalone_app):
    app, run_store, _ = standalone_app
    await run_store.save_run("r1", {
        "run_id": "r1", "status": "completed", "pipeline": "flow1",
    })
    client = TestClient(app)
    resp = client.get("/api/v1/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["run_id"] == "r1"


@pytest.mark.anyio
async def test_standalone_get_run(standalone_app):
    app, run_store, _ = standalone_app
    await run_store.save_run("r1", {
        "run_id": "r1", "status": "completed", "pipeline": "flow1",
    })
    client = TestClient(app)
    resp = client.get("/api/v1/runs/r1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == "r1"


@pytest.mark.anyio
async def test_standalone_get_run_not_found(standalone_app):
    app, _, _ = standalone_app
    client = TestClient(app)
    resp = client.get("/api/v1/runs/nonexistent")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_standalone_get_run_events(standalone_app):
    from miniautogen.core.contracts.events import ExecutionEvent

    app, run_store, event_store = standalone_app
    await run_store.save_run("r1", {"run_id": "r1", "status": "completed"})
    evt = ExecutionEvent(
        type="run_started",
        timestamp=datetime.now(timezone.utc),
        run_id="r1",
        correlation_id="c1",
        scope="test",
        payload={},
    )
    await event_store.append("r1", evt)

    client = TestClient(app)
    resp = client.get("/api/v1/runs/r1/events")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1


def test_standalone_no_websocket(standalone_app):
    """Standalone mode should not have WebSocket endpoint."""
    app, _, _ = standalone_app
    client = TestClient(app)
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/runs/test"):
            pass


def test_standalone_trigger_run_returns_501(standalone_app):
    """Cannot trigger runs in standalone mode."""
    app, _, _ = standalone_app
    client = TestClient(app)
    resp = client.post("/api/v1/runs", json={"flow_name": "test"})
    assert resp.status_code == 501


def test_console_command_has_db_option():
    """Console command should accept --db flag for store backend."""
    from click.testing import CliRunner

    from miniautogen.cli.commands.console import console_command

    runner = CliRunner()
    result = runner.invoke(console_command, ["--help"])
    assert "--db" in result.output
