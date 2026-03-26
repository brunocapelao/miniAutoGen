"""Tests for config detail endpoint."""

from __future__ import annotations


def test_get_config_detail(client, mock_provider):
    mock_provider.get_config_detail.return_value = {
        "project": {"name": "test-project", "version": "0.1.0"},
        "defaults": {"engine": "default_api", "memory_profile": "default"},
        "database": {"url": "sqlite:///test.db"},
        "engines": [
            {"name": "default_api", "provider": "openai", "model": "gpt-4o"},
        ],
    }
    resp = client.get("/api/v1/config/detail")
    assert resp.status_code == 200
    data = resp.json()
    assert data["project"]["name"] == "test-project"
    assert data["defaults"]["engine"] == "default_api"
    assert data["database"]["url"] == "sqlite:///test.db"
    assert len(data["engines"]) == 1
    mock_provider.get_config_detail.assert_called_once()
