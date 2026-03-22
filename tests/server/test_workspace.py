"""Tests for workspace endpoint."""

from __future__ import annotations


def test_get_workspace(client):
    resp = client.get("/api/v1/workspace")
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_name"] == "test-project"
    assert data["agent_count"] == 2


def test_get_workspace_empty(mock_provider, client):
    mock_provider.get_config.return_value = {}
    resp = client.get("/api/v1/workspace")
    assert resp.status_code == 200
    assert resp.json() == {}
