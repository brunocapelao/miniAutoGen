"""Tests for engine CRUD endpoints (GET, POST, PUT, DELETE)."""

from __future__ import annotations


def test_list_engines(client, mock_provider):
    mock_provider.get_engines.return_value = [
        {"name": "default_api", "provider": "openai", "model": "gpt-4o", "kind": "api"},
        {"name": "local_ollama", "provider": "ollama", "model": "llama3", "kind": "local"},
    ]
    resp = client.get("/api/v1/engines")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["name"] == "default_api"
    assert data[1]["name"] == "local_ollama"


def test_get_engine(client, mock_provider):
    mock_provider.get_engine.return_value = {
        "name": "default_api",
        "provider": "openai",
        "model": "gpt-4o",
        "kind": "api",
        "temperature": 0.2,
    }
    resp = client.get("/api/v1/engines/default_api")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "default_api"
    assert data["provider"] == "openai"
    mock_provider.get_engine.assert_called_once_with("default_api")


def test_get_engine_not_found_404(client, mock_provider):
    mock_provider.get_engine.side_effect = KeyError("nonexistent")
    resp = client.get("/api/v1/engines/nonexistent")
    assert resp.status_code == 404
    data = resp.json()
    assert data["code"] == "engine_not_found"


def test_create_engine(client, mock_provider):
    mock_provider.create_engine.return_value = {
        "name": "new_engine",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "kind": "api",
        "temperature": 0.5,
    }
    resp = client.post("/api/v1/engines", json={
        "name": "new_engine",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "temperature": 0.5,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "new_engine"
    assert data["provider"] == "openai"
    mock_provider.create_engine.assert_called_once_with(
        "new_engine",
        provider="openai",
        model="gpt-4o-mini",
        kind="api",
        temperature=0.5,
        api_key_env=None,
        endpoint=None,
    )


def test_create_engine_duplicate_409(client, mock_provider):
    mock_provider.create_engine.side_effect = ValueError("Engine 'default_api' already exists")
    resp = client.post("/api/v1/engines", json={
        "name": "default_api",
        "provider": "openai",
        "model": "gpt-4o",
    })
    assert resp.status_code == 409
    data = resp.json()
    assert data["code"] == "engine_exists"


def test_update_engine(client, mock_provider):
    mock_provider.update_engine.return_value = {
        "name": "default_api",
        "provider": "openai",
        "model": "gpt-4o",
        "kind": "api",
        "temperature": 0.8,
    }
    resp = client.put("/api/v1/engines/default_api", json={
        "temperature": 0.8,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["temperature"] == 0.8
    mock_provider.update_engine.assert_called_once_with("default_api", temperature=0.8)


def test_update_engine_not_found_404(client, mock_provider):
    mock_provider.update_engine.side_effect = KeyError("nonexistent")
    resp = client.put("/api/v1/engines/nonexistent", json={
        "temperature": 0.5,
    })
    assert resp.status_code == 404
    data = resp.json()
    assert data["code"] == "engine_not_found"


def test_update_engine_empty_body_400(client):
    resp = client.put("/api/v1/engines/default_api", json={})
    assert resp.status_code == 400
    data = resp.json()
    assert data["code"] == "empty_update"


def test_delete_engine(client, mock_provider):
    mock_provider.delete_engine.return_value = {"deleted": "default_api"}
    resp = client.delete("/api/v1/engines/default_api")
    assert resp.status_code == 200
    data = resp.json()
    assert data["deleted"] == "default_api"
    mock_provider.delete_engine.assert_called_once_with("default_api")


def test_delete_engine_not_found_404(client, mock_provider):
    mock_provider.delete_engine.side_effect = KeyError("nonexistent")
    resp = client.delete("/api/v1/engines/nonexistent")
    assert resp.status_code == 404
    data = resp.json()
    assert data["code"] == "engine_not_found"
