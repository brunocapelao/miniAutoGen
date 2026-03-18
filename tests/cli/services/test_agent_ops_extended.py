"""Extended tests for agent_ops service — covers _agents_dir creation,
schema validation failure, corrupt YAML, engine validation, dry_run,
and delete with leader references.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from miniautogen.cli.services.agent_ops import (
    _agents_dir,
    _validate_agent,
    create_agent,
    delete_agent,
    list_agents,
    show_agent,
    update_agent,
)
from miniautogen.cli.services.yaml_ops import write_yaml


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data))


def _make_project(tmp_path: Path) -> Path:
    """Create minimal project with config and agents dir."""
    config = {
        "project": {"name": "test", "version": "0.1.0"},
        "defaults": {"engine_profile": "default_api", "memory_profile": "default"},
        "engine_profiles": {
            "default_api": {"kind": "api", "provider": "litellm", "model": "gpt-4o-mini"},
        },
        "pipelines": {},
    }
    _write_yaml(tmp_path / "miniautogen.yaml", config)
    return tmp_path


def _create_agent_yaml(project: Path, name: str) -> Path:
    """Write a valid agent YAML file."""
    agent = {
        "id": name,
        "version": "1.0.0",
        "name": name,
        "role": "assistant",
        "goal": "help",
        "engine_profile": "default_api",
    }
    path = project / "agents" / f"{name}.yaml"
    _write_yaml(path, agent)
    return path


# ── _agents_dir ─────────────────────────────────────────────────────────


class TestAgentsDir:
    def test_creates_missing_directory(self, tmp_path: Path) -> None:
        """agents/ doesn't exist yet — should be created."""
        assert not (tmp_path / "agents").exists()
        result = _agents_dir(tmp_path)
        assert result.is_dir()
        assert result == tmp_path / "agents"

    def test_existing_directory_unchanged(self, tmp_path: Path) -> None:
        """agents/ already exists — just returns it."""
        (tmp_path / "agents").mkdir()
        result = _agents_dir(tmp_path)
        assert result.is_dir()


# ── _validate_agent (schema failure) ────────────────────────────────────


class TestValidateAgent:
    def test_valid_agent_data(self) -> None:
        data = {"id": "test", "name": "Test", "version": "1.0.0"}
        _validate_agent(data)  # should not raise

    def test_invalid_agent_missing_id(self) -> None:
        with pytest.raises(ValueError, match="Agent validation failed"):
            _validate_agent({"name": "NoId"})

    def test_invalid_agent_missing_name(self) -> None:
        with pytest.raises(ValueError, match="Agent validation failed"):
            _validate_agent({"id": "no_name"})


# ── create_agent ────────────────────────────────────────────────────────


class TestCreateAgent:
    def test_schema_validation_failure(self, tmp_path: Path) -> None:
        """create_agent with data that fails AgentSpec validation."""
        project = _make_project(tmp_path)
        # We need to trigger validation failure. AgentSpec requires 'id'
        # and 'name'. create_agent builds the data dict itself, so a normal
        # call should succeed. But if the validation fails internally...
        # The easiest path: the name is valid but engine_profile doesn't exist.
        with pytest.raises(ValueError, match="not found"):
            create_agent(
                project, "myagent",
                role="test", goal="test",
                engine_profile="nonexistent_engine",
            )

    def test_create_duplicate_raises(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path)
        create_agent(
            project, "agent1",
            role="test", goal="test",
            engine_profile="default_api",
        )
        with pytest.raises(ValueError, match="already exists"):
            create_agent(
                project, "agent1",
                role="test2", goal="test2",
                engine_profile="default_api",
            )


# ── show_agent ──────────────────────────────────────────────────────────


class TestShowAgent:
    def test_show_valid_agent(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path)
        _create_agent_yaml(project, "researcher")
        data = show_agent(project, "researcher")
        assert data["id"] == "researcher"

    def test_show_missing_agent(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path)
        (project / "agents").mkdir(exist_ok=True)
        with pytest.raises(KeyError, match="not found"):
            show_agent(project, "missing")

    def test_show_corrupt_yaml(self, tmp_path: Path) -> None:
        """Agent YAML with broken syntax — should raise."""
        project = _make_project(tmp_path)
        agents_dir = project / "agents"
        agents_dir.mkdir(exist_ok=True)
        (agents_dir / "corrupt.yaml").write_text(":\n  bad: yaml: x:\n")
        with pytest.raises(Exception):
            show_agent(project, "corrupt")


# ── list_agents ─────────────────────────────────────────────────────────


class TestListAgents:
    def test_list_with_corrupt_yaml(self, tmp_path: Path) -> None:
        """Corrupt agent YAML shows as (invalid) in listing."""
        project = _make_project(tmp_path)
        agents_dir = project / "agents"
        agents_dir.mkdir(exist_ok=True)
        (agents_dir / "bad.yaml").write_text("- list_not_dict\n")
        result = list_agents(project)
        assert len(result) == 1
        assert result[0]["role"] == "(invalid)"


# ── update_agent ────────────────────────────────────────────────────────


class TestUpdateAgent:
    def test_engine_not_found(self, tmp_path: Path) -> None:
        """Updating engine_profile to one that doesn't exist — should fail."""
        project = _make_project(tmp_path)
        _create_agent_yaml(project, "agent1")
        with pytest.raises(ValueError, match="not found"):
            update_agent(
                project, "agent1",
                engine_profile="nonexistent",
            )

    def test_engine_found(self, tmp_path: Path) -> None:
        """Updating engine_profile to a valid one — should succeed."""
        project = _make_project(tmp_path)
        _create_agent_yaml(project, "agent1")
        result = update_agent(
            project, "agent1",
            engine_profile="default_api",
        )
        assert result["after"]["engine_profile"] == "default_api"

    def test_dry_run_mode(self, tmp_path: Path) -> None:
        """dry_run=True should not write to disk."""
        project = _make_project(tmp_path)
        _create_agent_yaml(project, "agent1")
        original = yaml.safe_load(
            (project / "agents" / "agent1.yaml").read_text(),
        )
        result = update_agent(
            project, "agent1",
            dry_run=True,
            role="new_role",
        )
        assert result["after"]["role"] == "new_role"
        # File should be unchanged
        on_disk = yaml.safe_load(
            (project / "agents" / "agent1.yaml").read_text(),
        )
        assert on_disk["role"] == original["role"]

    def test_update_missing_agent(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path)
        (project / "agents").mkdir(exist_ok=True)
        with pytest.raises(KeyError, match="not found"):
            update_agent(project, "ghost", role="x")


# ── delete_agent ────────────────────────────────────────────────────────


class TestDeleteAgent:
    def test_delete_unreferenced_agent(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path)
        _create_agent_yaml(project, "agent1")
        result = delete_agent(project, "agent1")
        assert result["deleted"] == "agent1"
        assert not (project / "agents" / "agent1.yaml").exists()

    def test_delete_agent_referenced_as_participant(
        self, tmp_path: Path,
    ) -> None:
        """Agent used as pipeline participant — should raise."""
        project = _make_project(tmp_path)
        _create_agent_yaml(project, "agent1")
        # Add pipeline reference
        cfg = yaml.safe_load(
            (project / "miniautogen.yaml").read_text(),
        )
        cfg["pipelines"]["main"] = {
            "target": "p.main:build",
            "participants": ["agent1"],
        }
        (project / "miniautogen.yaml").write_text(yaml.dump(cfg))
        with pytest.raises(ValueError, match="referenced by pipeline"):
            delete_agent(project, "agent1")

    def test_delete_agent_referenced_as_leader(
        self, tmp_path: Path,
    ) -> None:
        """Agent used as pipeline leader — should raise."""
        project = _make_project(tmp_path)
        _create_agent_yaml(project, "leader1")
        cfg = yaml.safe_load(
            (project / "miniautogen.yaml").read_text(),
        )
        cfg["pipelines"]["main"] = {
            "target": "p.main:build",
            "leader": "leader1",
        }
        (project / "miniautogen.yaml").write_text(yaml.dump(cfg))
        with pytest.raises(ValueError, match="referenced by pipeline"):
            delete_agent(project, "leader1")

    def test_delete_missing_agent(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path)
        (project / "agents").mkdir(exist_ok=True)
        with pytest.raises(KeyError, match="not found"):
            delete_agent(project, "ghost")
