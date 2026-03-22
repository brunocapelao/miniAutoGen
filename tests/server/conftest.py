"""Shared fixtures for Console Server tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from miniautogen.server.app import create_app


@pytest.fixture
def mock_provider() -> MagicMock:
    """Mock DashDataProvider for testing routes without real project."""
    provider = MagicMock()
    provider.get_config.return_value = {
        "project_name": "test-project",
        "version": "0.1.0",
        "default_engine": "default_api",
        "default_memory": "default",
        "engine_count": 1,
        "agent_count": 2,
        "pipeline_count": 1,
        "database": "(none)",
    }
    provider.get_agents.return_value = [
        {"name": "researcher", "role": "researcher", "goal": "Research", "engine_profile": "default_api"},
        {"name": "writer", "role": "writer", "goal": "Write", "engine_profile": "default_api"},
    ]
    provider.get_agent.return_value = {
        "name": "researcher", "role": "researcher", "goal": "Research",
        "engine_profile": "default_api",
    }
    provider.get_pipelines.return_value = [
        {"name": "main", "mode": "workflow", "target": "pipelines.main:build_pipeline"},
    ]
    provider.get_pipeline.return_value = {
        "name": "main", "mode": "workflow", "target": "pipelines.main:build_pipeline",
        "participants": ["researcher", "writer"],
    }
    provider.get_runs.return_value = []
    provider.get_events.return_value = []
    return provider


@pytest.fixture
def client(mock_provider: MagicMock) -> TestClient:
    """FastAPI test client with mocked provider."""
    app = create_app(provider=mock_provider, mode="embedded")
    return TestClient(app)
