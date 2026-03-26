"""Tests for agent CRUD endpoints (POST, PUT, DELETE)."""

from __future__ import annotations


def test_create_agent(client, mock_provider):
    mock_provider.create_agent.return_value = {
        "name": "analyst",
        "role": "analyst",
        "goal": "Analyze data",
        "engine_profile": "default_api",
    }
    resp = client.post("/api/v1/agents", json={
        "name": "analyst",
        "role": "analyst",
        "goal": "Analyze data",
        "engine_profile": "default_api",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "analyst"
    assert data["role"] == "analyst"
    mock_provider.create_agent.assert_called_once_with(
        "analyst",
        role="analyst",
        goal="Analyze data",
        engine_profile="default_api",
        temperature=None,
    )


def test_create_agent_with_temperature(client, mock_provider):
    mock_provider.create_agent.return_value = {
        "name": "creative",
        "role": "writer",
        "goal": "Write creatively",
        "engine_profile": "default_api",
        "temperature": 0.9,
    }
    resp = client.post("/api/v1/agents", json={
        "name": "creative",
        "role": "writer",
        "goal": "Write creatively",
        "engine_profile": "default_api",
        "temperature": 0.9,
    })
    assert resp.status_code == 201
    mock_provider.create_agent.assert_called_once_with(
        "creative",
        role="writer",
        goal="Write creatively",
        engine_profile="default_api",
        temperature=0.9,
    )


def test_create_agent_duplicate_409(client, mock_provider):
    mock_provider.create_agent.side_effect = ValueError("Agent 'researcher' already exists")
    resp = client.post("/api/v1/agents", json={
        "name": "researcher",
        "role": "researcher",
        "goal": "Research",
        "engine_profile": "default_api",
    })
    assert resp.status_code == 409
    data = resp.json()
    assert data["code"] == "agent_exists"


def test_create_agent_validation_error(client):
    resp = client.post("/api/v1/agents", json={
        "name": "",
        "role": "researcher",
        "goal": "Research",
        "engine_profile": "default_api",
    })
    assert resp.status_code == 422


def test_update_agent(client, mock_provider):
    mock_provider.update_agent.return_value = {
        "name": "researcher",
        "role": "senior_researcher",
        "goal": "Research",
        "engine_profile": "default_api",
    }
    resp = client.put("/api/v1/agents/researcher", json={
        "role": "senior_researcher",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "senior_researcher"
    mock_provider.update_agent.assert_called_once_with("researcher", role="senior_researcher")


def test_update_agent_not_found_404(client, mock_provider):
    mock_provider.update_agent.side_effect = KeyError("nonexistent")
    resp = client.put("/api/v1/agents/nonexistent", json={
        "role": "new_role",
    })
    assert resp.status_code == 404
    data = resp.json()
    assert data["code"] == "agent_not_found"


def test_update_agent_empty_body_400(client):
    resp = client.put("/api/v1/agents/researcher", json={})
    assert resp.status_code == 400
    data = resp.json()
    assert data["code"] == "empty_update"


def test_delete_agent(client, mock_provider):
    mock_provider.delete_agent.return_value = {"deleted": "researcher"}
    resp = client.delete("/api/v1/agents/researcher")
    assert resp.status_code == 200
    data = resp.json()
    assert data["deleted"] == "researcher"
    mock_provider.delete_agent.assert_called_once_with("researcher")


def test_delete_agent_not_found_404(client, mock_provider):
    mock_provider.delete_agent.side_effect = KeyError("nonexistent")
    resp = client.delete("/api/v1/agents/nonexistent")
    assert resp.status_code == 404
    data = resp.json()
    assert data["code"] == "agent_not_found"
