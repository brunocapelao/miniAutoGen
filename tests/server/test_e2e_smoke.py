"""End-to-end smoke test for the Console Server."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from miniautogen.server.app import create_app


def _mock_provider() -> MagicMock:
    provider = MagicMock()
    provider.get_config.return_value = {
        "project_name": "smoke-test",
        "version": "0.1.0",
        "agent_count": 1,
        "pipeline_count": 1,
    }
    provider.get_agents.return_value = [
        {"name": "a1", "role": "tester", "engine_profile": "gpt4"},
    ]
    provider.get_pipelines.return_value = [
        {"name": "main", "mode": "workflow", "target": "main:build"},
    ]
    provider.get_runs.return_value = [
        {"run_id": "r1", "pipeline": "main", "status": "completed", "started": "2026-01-01", "events": 3},
    ]
    provider.get_events.return_value = [
        {"type": "run_started", "run_id": "r1", "timestamp": "2026-01-01T00:00:00Z"},
        {"type": "component_started", "run_id": "r1", "timestamp": "2026-01-01T00:00:01Z"},
        {"type": "run_finished", "run_id": "r1", "timestamp": "2026-01-01T00:00:02Z"},
    ]

    def _get_agent(name: str):
        if name == "a1":
            return {"name": "a1", "role": "tester", "engine_profile": "gpt4"}
        raise KeyError(name)

    def _get_pipeline(name: str):
        if name == "main":
            return {"name": "main", "mode": "workflow", "participants": ["a1"]}
        raise KeyError(name)

    provider.get_agent.side_effect = _get_agent
    provider.get_pipeline.side_effect = _get_pipeline
    provider.run_pipeline = AsyncMock(return_value={"status": "completed", "events": 3})

    # Public methods for run management (avoid direct _run_history access)
    _run_history: list[dict] = []
    provider.record_run = MagicMock(side_effect=lambda data: _run_history.append(data))

    def _update_run(run_id: str, updates: dict) -> None:
        for run in _run_history:
            if run.get("run_id") == run_id:
                run.update(updates)
                return

    provider.update_run = MagicMock(side_effect=_update_run)
    return provider


def test_smoke_all_endpoints():
    """Every endpoint returns 200 with valid data."""
    provider = _mock_provider()
    app = create_app(provider=provider, mode="embedded")
    client = TestClient(app)

    # Workspace
    r = client.get("/api/v1/workspace")
    assert r.status_code == 200
    assert r.json()["project_name"] == "smoke-test"

    # Agents
    r = client.get("/api/v1/agents")
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.get("/api/v1/agents/a1")
    assert r.status_code == 200

    # Flows
    r = client.get("/api/v1/flows")
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.get("/api/v1/flows/main")
    assert r.status_code == 200

    # Runs
    r = client.get("/api/v1/runs")
    assert r.status_code == 200
    assert r.json()["total"] == 1

    r = client.get("/api/v1/runs/r1")
    assert r.status_code == 200

    r = client.get("/api/v1/runs/r1/events")
    assert r.status_code == 200
    # In embedded mode, events come from WebSocketEventSink (not provider.get_events).
    # Since no pipeline actually ran, the event_sink has 0 events.
    assert r.json()["total"] == 0

    # Trigger run
    r = client.post("/api/v1/runs", json={"flow_name": "main"})
    assert r.status_code == 200
    assert "run_id" in r.json()

    # 404s
    r = client.get("/api/v1/agents/nonexistent")
    assert r.status_code == 404

    r = client.get("/api/v1/flows/nonexistent")
    assert r.status_code == 404

    r = client.get("/api/v1/runs/nonexistent")
    assert r.status_code == 404
