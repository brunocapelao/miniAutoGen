"""Tests for DashDataProvider."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Create a minimal MiniAutoGen project for testing."""
    config = {
        "project": {"name": "test-project", "version": "0.1.0"},
        "defaults": {"engine_profile": "default_api", "memory_profile": "default"},
        "engine_profiles": {
            "default_api": {
                "kind": "api",
                "provider": "litellm",
                "model": "gpt-4o-mini",
                "temperature": 0.2,
            },
        },
        "pipelines": {
            "main": {
                "target": "pipelines.main:build_pipeline",
                "mode": "workflow",
            },
        },
    }
    cfg_path = tmp_path / "miniautogen.yaml"
    with cfg_path.open("w") as f:
        yaml.dump(config, f, default_flow_style=False)

    # Create agents directory with a sample agent
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    agent_data = {
        "id": "researcher",
        "version": "1.0.0",
        "name": "researcher",
        "role": "researcher",
        "goal": "Research topics",
        "engine_profile": "default_api",
    }
    with (agents_dir / "researcher.yaml").open("w") as f:
        yaml.dump(agent_data, f, default_flow_style=False)

    # Create pipelines directory
    pipelines_dir = tmp_path / "pipelines"
    pipelines_dir.mkdir()
    (pipelines_dir / "main.py").write_text(
        'def build_pipeline():\n    return None\n'
    )

    return tmp_path


def test_provider_init(project_dir: Path) -> None:
    from miniautogen.tui.data_provider import DashDataProvider

    provider = DashDataProvider(project_dir)
    assert provider.project_root == project_dir.resolve()
    assert provider.has_project() is True


def test_provider_no_project(tmp_path: Path) -> None:
    from miniautogen.tui.data_provider import DashDataProvider

    provider = DashDataProvider(tmp_path)
    assert provider.has_project() is False


def test_get_config(project_dir: Path) -> None:
    from miniautogen.tui.data_provider import DashDataProvider

    provider = DashDataProvider(project_dir)
    config = provider.get_config()
    assert config["project_name"] == "test-project"
    assert config["version"] == "0.1.0"
    assert config["default_engine"] == "default_api"
    assert config["engine_count"] == 1
    assert config["agent_count"] == 1
    assert config["pipeline_count"] == 1


def test_get_engines(project_dir: Path) -> None:
    from miniautogen.tui.data_provider import DashDataProvider

    provider = DashDataProvider(project_dir)
    engines = provider.get_engines()
    assert len(engines) == 1
    assert engines[0]["name"] == "default_api"
    assert engines[0]["provider"] == "litellm"


def test_get_agents(project_dir: Path) -> None:
    from miniautogen.tui.data_provider import DashDataProvider

    provider = DashDataProvider(project_dir)
    agents = provider.get_agents()
    assert len(agents) == 1
    assert agents[0]["name"] == "researcher"
    assert agents[0]["role"] == "researcher"


def test_get_pipelines(project_dir: Path) -> None:
    from miniautogen.tui.data_provider import DashDataProvider

    provider = DashDataProvider(project_dir)
    pipelines = provider.get_pipelines()
    assert len(pipelines) == 1
    assert pipelines[0]["name"] == "main"
    assert pipelines[0]["mode"] == "workflow"


def test_get_runs_empty(project_dir: Path) -> None:
    from miniautogen.tui.data_provider import DashDataProvider

    provider = DashDataProvider(project_dir)
    runs = provider.get_runs()
    assert runs == []


def test_get_events_empty(project_dir: Path) -> None:
    from miniautogen.tui.data_provider import DashDataProvider

    provider = DashDataProvider(project_dir)
    events = provider.get_events()
    assert events == []


def test_create_engine(project_dir: Path) -> None:
    from miniautogen.tui.data_provider import DashDataProvider

    provider = DashDataProvider(project_dir)
    result = provider.create_engine(
        "new-engine",
        provider="openai",
        model="gpt-4o",
        kind="api",
    )
    assert result["provider"] == "openai"
    assert result["model"] == "gpt-4o"

    # Verify persisted
    engines = provider.get_engines()
    names = [e["name"] for e in engines]
    assert "new-engine" in names


def test_create_engine_duplicate(project_dir: Path) -> None:
    from miniautogen.tui.data_provider import DashDataProvider

    provider = DashDataProvider(project_dir)
    with pytest.raises(ValueError, match="already exists"):
        provider.create_engine(
            "default_api",
            provider="litellm",
            model="gpt-4o-mini",
        )


def test_update_engine(project_dir: Path) -> None:
    from miniautogen.tui.data_provider import DashDataProvider

    provider = DashDataProvider(project_dir)
    result = provider.update_engine("default_api", model="gpt-4o")
    assert result["after"]["model"] == "gpt-4o"


def test_delete_engine_with_reference(project_dir: Path) -> None:
    from miniautogen.tui.data_provider import DashDataProvider

    provider = DashDataProvider(project_dir)
    # default_api is referenced by researcher agent
    with pytest.raises(ValueError, match="referenced by"):
        provider.delete_engine("default_api")


def test_create_agent(project_dir: Path) -> None:
    from miniautogen.tui.data_provider import DashDataProvider

    provider = DashDataProvider(project_dir)
    result = provider.create_agent(
        "planner",
        role="planner",
        goal="Plan tasks",
        engine_profile="default_api",
    )
    assert result["role"] == "planner"

    agents = provider.get_agents()
    names = [a["name"] for a in agents]
    assert "planner" in names


def test_delete_agent(project_dir: Path) -> None:
    from miniautogen.tui.data_provider import DashDataProvider

    # Create an agent that has no pipeline references
    provider = DashDataProvider(project_dir)
    provider.create_agent(
        "disposable",
        role="temp",
        goal="Temporary",
        engine_profile="default_api",
    )
    result = provider.delete_agent("disposable")
    assert result["deleted"] == "disposable"


def test_create_pipeline(project_dir: Path) -> None:
    from miniautogen.tui.data_provider import DashDataProvider

    provider = DashDataProvider(project_dir)
    result = provider.create_pipeline(
        "secondary",
        mode="deliberation",
        participants=["researcher"],
    )
    assert result["mode"] == "deliberation"

    pipelines = provider.get_pipelines()
    names = [p["name"] for p in pipelines]
    assert "secondary" in names


def test_delete_pipeline(project_dir: Path) -> None:
    from miniautogen.tui.data_provider import DashDataProvider

    provider = DashDataProvider(project_dir)
    result = provider.delete_pipeline("main")
    assert result["deleted"] == "main"

    pipelines = provider.get_pipelines()
    names = [p["name"] for p in pipelines]
    assert "main" not in names


def test_delete_pipeline_not_found(project_dir: Path) -> None:
    from miniautogen.tui.data_provider import DashDataProvider

    provider = DashDataProvider(project_dir)
    with pytest.raises(KeyError, match="not found"):
        provider.delete_pipeline("nonexistent")


def test_server_status(project_dir: Path) -> None:
    from miniautogen.tui.data_provider import DashDataProvider

    provider = DashDataProvider(project_dir)
    status = provider.server_status()
    assert status["status"] == "stopped"


def test_get_config_no_project(tmp_path: Path) -> None:
    from miniautogen.tui.data_provider import DashDataProvider

    provider = DashDataProvider(tmp_path)
    config = provider.get_config()
    assert config == {}


def test_provider_has_run_pipeline_method(project_dir: Path) -> None:
    from miniautogen.tui.data_provider import DashDataProvider

    provider = DashDataProvider(project_dir)
    assert hasattr(provider, "run_pipeline")
    assert callable(provider.run_pipeline)


def test_get_engines_no_project(tmp_path: Path) -> None:
    from miniautogen.tui.data_provider import DashDataProvider

    provider = DashDataProvider(tmp_path)
    engines = provider.get_engines()
    assert engines == []
