"""Tests for agent endpoints."""

from __future__ import annotations


def test_list_agents(client):
    resp = client.get("/api/v1/agents")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["name"] == "researcher"
    assert "role" in data[0]
    assert "engine_type" in data[0] or "engine_profile" in data[0]


def test_get_agent(client):
    resp = client.get("/api/v1/agents/researcher")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "researcher"


def test_get_agent_not_found(client, mock_provider):
    mock_provider.get_agent.side_effect = KeyError("nope")
    resp = client.get("/api/v1/agents/nonexistent")
    assert resp.status_code == 404
    data = resp.json()
    assert data["code"] == "agent_not_found"
