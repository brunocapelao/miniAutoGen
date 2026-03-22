"""Tests for run endpoints."""

from __future__ import annotations
from unittest.mock import AsyncMock


def test_list_runs_empty(client):
    resp = client.get("/api/v1/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_list_runs_with_data(client, mock_provider):
    mock_provider.get_runs.return_value = [
        {"run_id": "r1", "pipeline": "main", "status": "completed", "started": "2026-01-01T00:00:00Z", "events": 5},
        {"run_id": "r2", "pipeline": "main", "status": "running", "started": "2026-01-01T00:01:00Z", "events": 2},
    ]
    resp = client.get("/api/v1/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_list_runs_pagination(client, mock_provider):
    mock_provider.get_runs.return_value = [
        {"run_id": f"r{i}", "pipeline": "main", "status": "completed", "started": "2026-01-01T00:00:00Z", "events": 0}
        for i in range(5)
    ]
    resp = client.get("/api/v1/runs?offset=2&limit=2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2
    assert data["offset"] == 2
    assert data["limit"] == 2


def test_get_run(client, mock_provider):
    mock_provider.get_runs.return_value = [
        {"run_id": "r1", "pipeline": "main", "status": "completed", "started": "2026-01-01T00:00:00Z", "events": 5},
    ]
    resp = client.get("/api/v1/runs/r1")
    assert resp.status_code == 200
    assert resp.json()["run_id"] == "r1"


def test_get_run_not_found(client):
    resp = client.get("/api/v1/runs/nonexistent")
    assert resp.status_code == 404


def test_get_run_events(client, mock_provider):
    mock_provider.get_events.return_value = [
        {"type": "run_started", "run_id": "r1", "timestamp": "2026-01-01T00:00:00Z"},
        {"type": "component_started", "run_id": "r1", "timestamp": "2026-01-01T00:00:01Z"},
    ]
    resp = client.get("/api/v1/runs/r1/events")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


def test_trigger_run(client, mock_provider):
    mock_provider.run_pipeline = AsyncMock(return_value={"status": "completed", "events": 3})
    resp = client.post("/api/v1/runs", json={"flow_name": "main"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "triggered"
    assert data["flow_name"] == "main"


def test_trigger_run_not_found(client, mock_provider):
    mock_provider.get_pipelines.return_value = []
    resp = client.post("/api/v1/runs", json={"flow_name": "nonexistent"})
    assert resp.status_code == 404
    assert resp.json()["code"] == "flow_not_found"
