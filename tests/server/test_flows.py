"""Tests for flow endpoints."""

from __future__ import annotations


def test_list_flows(client):
    resp = client.get("/api/v1/flows")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "main"
    assert data[0]["mode"] == "workflow"


def test_get_flow(client):
    resp = client.get("/api/v1/flows/main")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "main"
    assert "participants" in data


def test_get_flow_not_found(client, mock_provider):
    mock_provider.get_pipeline.side_effect = KeyError("nope")
    resp = client.get("/api/v1/flows/nonexistent")
    assert resp.status_code == 404
    data = resp.json()
    assert data["code"] == "flow_not_found"
