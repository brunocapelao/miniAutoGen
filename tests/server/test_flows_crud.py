"""Tests for flow CRUD endpoints (POST, PUT, DELETE)."""

from __future__ import annotations


def test_create_flow(client, mock_provider):
    mock_provider.create_pipeline.return_value = {
        "name": "analysis",
        "mode": "workflow",
        "participants": ["researcher"],
        "target": "pipelines.analysis:build",
    }
    resp = client.post("/api/v1/flows", json={
        "name": "analysis",
        "mode": "workflow",
        "participants": ["researcher"],
        "target": "pipelines.analysis:build",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "analysis"
    assert data["mode"] == "workflow"
    mock_provider.create_pipeline.assert_called_once_with(
        "analysis",
        mode="workflow",
        participants=["researcher"],
        leader=None,
        target="pipelines.analysis:build",
    )


def test_create_flow_minimal(client, mock_provider):
    mock_provider.create_pipeline.return_value = {
        "name": "simple",
        "mode": "workflow",
    }
    resp = client.post("/api/v1/flows", json={"name": "simple"})
    assert resp.status_code == 201
    mock_provider.create_pipeline.assert_called_once_with(
        "simple",
        mode="workflow",
        participants=None,
        leader=None,
        target=None,
    )


def test_create_flow_duplicate_409(client, mock_provider):
    mock_provider.create_pipeline.side_effect = ValueError("Pipeline 'main' already exists")
    resp = client.post("/api/v1/flows", json={
        "name": "main",
        "mode": "workflow",
    })
    assert resp.status_code == 409
    data = resp.json()
    assert data["code"] == "flow_exists"


def test_create_flow_validation_error(client):
    resp = client.post("/api/v1/flows", json={"name": ""})
    assert resp.status_code == 422


def test_update_flow(client, mock_provider):
    mock_provider.update_pipeline.return_value = {
        "name": "main",
        "mode": "debate",
        "participants": ["researcher", "writer"],
    }
    resp = client.put("/api/v1/flows/main", json={
        "mode": "debate",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "debate"
    mock_provider.update_pipeline.assert_called_once_with("main", mode="debate")


def test_update_flow_not_found_404(client, mock_provider):
    mock_provider.update_pipeline.side_effect = KeyError("nonexistent")
    resp = client.put("/api/v1/flows/nonexistent", json={
        "mode": "debate",
    })
    assert resp.status_code == 404
    data = resp.json()
    assert data["code"] == "flow_not_found"


def test_update_flow_empty_body_400(client):
    resp = client.put("/api/v1/flows/main", json={})
    assert resp.status_code == 400
    data = resp.json()
    assert data["code"] == "empty_update"


def test_delete_flow(client, mock_provider):
    mock_provider.delete_pipeline.return_value = {"deleted": "main"}
    resp = client.delete("/api/v1/flows/main")
    assert resp.status_code == 200
    data = resp.json()
    assert data["deleted"] == "main"
    mock_provider.delete_pipeline.assert_called_once_with("main")


def test_delete_flow_not_found_404(client, mock_provider):
    mock_provider.delete_pipeline.side_effect = KeyError("nonexistent")
    resp = client.delete("/api/v1/flows/nonexistent")
    assert resp.status_code == 404
    data = resp.json()
    assert data["code"] == "flow_not_found"
