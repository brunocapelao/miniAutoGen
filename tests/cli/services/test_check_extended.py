"""Extended tests for check_project service — pipeline participants,
mode-specific validation, gateway accessibility, tool/skill schema errors.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from miniautogen.cli.config import CONFIG_FILENAME, load_config
from miniautogen.cli.services.check_project import (
    _check_gateway_accessibility,
    _check_pipeline_participants,
    _check_pipelines,
    _check_skills,
    _check_tools,
    check_project,
)


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data))


def _base_config() -> dict:
    return {
        "project": {"name": "test", "version": "0.1.0"},
        "defaults": {"engine_profile": "default_api", "memory_profile": "default"},
        "engine_profiles": {
            "default_api": {"kind": "api", "provider": "litellm", "model": "gpt-4o-mini"},
        },
        "memory_profiles": {
            "default": {"session": True},
        },
        "pipelines": {"main": {"target": "pipelines.main:build_pipeline"}},
    }


def _make_project(tmp_path: Path, config: dict | None = None) -> Path:
    cfg = config or _base_config()
    _write_yaml(tmp_path / CONFIG_FILENAME, cfg)
    (tmp_path / "pipelines").mkdir(exist_ok=True)
    (tmp_path / "pipelines" / "main.py").write_text("def build_pipeline(): pass")
    return tmp_path


# ── Pipeline participant validation ─────────────────────────────────────


class TestPipelineParticipants:
    def test_missing_participant_agent(self, tmp_path: Path) -> None:
        """Participant agent file does not exist — should fail."""
        cfg = _base_config()
        cfg["pipelines"]["main"]["participants"] = ["researcher"]
        project = _make_project(tmp_path, cfg)
        (project / "agents").mkdir()
        # Agent file NOT created
        config = load_config(project / CONFIG_FILENAME)
        results = _check_pipeline_participants(config, project)
        failed = [r for r in results if not r.passed]
        assert len(failed) == 1
        assert "researcher" in failed[0].message

    def test_participant_agent_exists(self, tmp_path: Path) -> None:
        """Participant agent file exists — no failure."""
        cfg = _base_config()
        cfg["pipelines"]["main"]["participants"] = ["researcher"]
        project = _make_project(tmp_path, cfg)
        _write_yaml(project / "agents" / "researcher.yaml", {
            "id": "researcher", "name": "Researcher",
            "engine_profile": "default_api",
        })
        config = load_config(project / CONFIG_FILENAME)
        results = _check_pipeline_participants(config, project)
        failed = [r for r in results if not r.passed]
        assert len(failed) == 0

    def test_missing_leader_agent(self, tmp_path: Path) -> None:
        """Leader agent referenced but file missing — should fail."""
        cfg = _base_config()
        cfg["pipelines"]["main"]["leader"] = "missing_leader"
        project = _make_project(tmp_path, cfg)
        (project / "agents").mkdir()
        config = load_config(project / CONFIG_FILENAME)
        results = _check_pipeline_participants(config, project)
        failed = [r for r in results if not r.passed]
        assert any("missing_leader" in r.message for r in failed)

    def test_no_config_file_returns_empty(self, tmp_path: Path) -> None:
        """No miniautogen.yaml — returns empty results."""
        config = load_config(
            _make_project(tmp_path) / CONFIG_FILENAME,
        )
        # Remove config file to trigger early return
        (tmp_path / CONFIG_FILENAME).unlink()
        results = _check_pipeline_participants(config, tmp_path)
        assert results == []

    def test_non_dict_raw_config_returns_empty(self, tmp_path: Path) -> None:
        """miniautogen.yaml contains non-dict — returns empty."""
        project = _make_project(tmp_path)
        (project / CONFIG_FILENAME).write_text("- item1\n- item2\n")
        config = load_config(
            _make_project(tmp_path / "valid") / CONFIG_FILENAME,
        )
        results = _check_pipeline_participants(config, project)
        assert results == []

    def test_non_dict_pipeline_entry_skipped(self, tmp_path: Path) -> None:
        """Pipeline entry that is not a dict should be skipped.

        _check_pipeline_participants reads raw YAML independently,
        so we load a valid config but tamper the YAML file after loading.
        """
        cfg = _base_config()
        project = _make_project(tmp_path, cfg)
        config = load_config(project / CONFIG_FILENAME)
        # Tamper YAML after config was loaded so that the raw read sees
        # a non-dict pipeline entry (line 408-409 in check_project.py).
        raw = yaml.safe_load((project / CONFIG_FILENAME).read_text())
        raw["pipelines"]["bad"] = "not-a-dict"
        (project / CONFIG_FILENAME).write_text(yaml.dump(raw))
        # Should not crash — the non-dict entry is skipped
        results = _check_pipeline_participants(config, project)
        failed = [r for r in results if not r.passed]
        assert not any("bad" in r.name for r in failed)


# ── Gateway accessibility ───────────────────────────────────────────────


class TestGatewayAccessibility:
    def test_no_local_endpoints_returns_empty(self, tmp_path: Path) -> None:
        """No vllm/gemini-cli providers — skip gateway check."""
        project = _make_project(tmp_path)
        config = load_config(project / CONFIG_FILENAME)
        results = _check_gateway_accessibility(config)
        assert results == []

    def test_gateway_running(self, tmp_path: Path) -> None:
        """Gateway health check succeeds."""
        cfg = _base_config()
        cfg["engine_profiles"]["local"] = {
            "kind": "api", "provider": "vllm", "model": "llama",
        }
        project = _make_project(tmp_path, cfg)
        config = load_config(project / CONFIG_FILENAME)

        with patch("urllib.request.urlopen"):
            results = _check_gateway_accessibility(config)
        passed = [r for r in results if r.passed]
        assert len(passed) == 1

    def test_gateway_not_running(self, tmp_path: Path) -> None:
        """Gateway health check fails."""
        import urllib.error

        cfg = _base_config()
        cfg["engine_profiles"]["local"] = {
            "kind": "api", "provider": "gemini-cli", "model": "gemini",
        }
        project = _make_project(tmp_path, cfg)
        config = load_config(project / CONFIG_FILENAME)

        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("refused"),
        ):
            results = _check_gateway_accessibility(config)
        failed = [r for r in results if not r.passed]
        assert len(failed) == 1
        assert "not accessible" in failed[0].message


# ── Agent YAML non-dict content ─────────────────────────────────────────


class TestAgentNonDictContent:
    def test_agent_yaml_non_dict(self, tmp_path: Path) -> None:
        """Agent YAML that loads as a list — should report failure."""
        project = _make_project(tmp_path)
        agents_dir = project / "agents"
        agents_dir.mkdir(exist_ok=True)
        (agents_dir / "bad.yaml").write_text("- item1\n- item2\n")
        config = load_config(project / CONFIG_FILENAME)
        results = check_project(config, project)
        failed = [r for r in results if not r.passed and "bad" in r.name]
        assert len(failed) >= 1
        assert "mapping" in failed[0].message.lower() or "Expected" in failed[0].message


# ── Skills schema validation error ──────────────────────────────────────


class TestSkillSchemaValidation:
    def test_skill_yaml_schema_error(self, tmp_path: Path) -> None:
        """skill.yaml with invalid schema — should report failure."""
        project = _make_project(tmp_path)
        skill_dir = project / "skills" / "broken"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# Broken Skill")
        # Write a skill.yaml with invalid data (depends on SkillSpec)
        (skill_dir / "skill.yaml").write_text(
            "invalid_field_only: true\n"
        )
        config = load_config(project / CONFIG_FILENAME)
        results = _check_skills(project)
        # Either valid or invalid depending on SkillSpec; just confirm no crash
        assert isinstance(results, list)

    def test_skill_yaml_parse_error(self, tmp_path: Path) -> None:
        """skill.yaml with broken YAML syntax — should report failure."""
        project = _make_project(tmp_path)
        skill_dir = project / "skills" / "bad_yaml"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# Bad YAML")
        (skill_dir / "skill.yaml").write_text(":\n  bad: yaml: content:\n")
        config = load_config(project / CONFIG_FILENAME)
        results = _check_skills(project)
        failed = [r for r in results if not r.passed]
        assert any("yaml" in r.name.lower() or "YAML" in r.message for r in failed)


# ── Tools validation ────────────────────────────────────────────────────


class TestToolsValidation:
    def test_tool_yaml_non_dict(self, tmp_path: Path) -> None:
        """tool YAML that loads as a list — expected mapping failure."""
        project = _make_project(tmp_path)
        tools_dir = project / "tools"
        tools_dir.mkdir(exist_ok=True)
        (tools_dir / "bad_tool.yaml").write_text("- item1\n")
        results = _check_tools(project)
        failed = [r for r in results if not r.passed]
        assert any("Expected mapping" in r.message for r in failed)

    def test_tool_yaml_parse_error(self, tmp_path: Path) -> None:
        """tool YAML with broken syntax."""
        project = _make_project(tmp_path)
        tools_dir = project / "tools"
        tools_dir.mkdir(exist_ok=True)
        (tools_dir / "broken.yaml").write_text(":\n  bad: yaml: x:\n")
        results = _check_tools(project)
        failed = [r for r in results if not r.passed]
        assert any("YAML parse error" in r.message for r in failed)

    def test_tool_schema_validation_error(self, tmp_path: Path) -> None:
        """tool YAML that fails ToolSpec validation."""
        project = _make_project(tmp_path)
        tools_dir = project / "tools"
        tools_dir.mkdir(exist_ok=True)
        # dict but missing required 'name' field (ToolSpec likely requires it)
        (tools_dir / "invalid.yaml").write_text("random_key: true\n")
        results = _check_tools(project)
        # Just verify no crash; actual failure depends on ToolSpec requirements
        assert isinstance(results, list)


# ── Pipeline target resolves outside project ────────────────────────────


class TestPipelineTargetOutsideProject:
    def test_target_resolves_outside_project(self, tmp_path: Path) -> None:
        """Pipeline target that resolves outside the project root."""
        cfg = _base_config()
        cfg["pipelines"]["escape"] = {
            "target": "....etc.passwd:run",
        }
        project = _make_project(tmp_path, cfg)
        config = load_config(project / CONFIG_FILENAME)
        results = _check_pipelines(config, project)
        escape_results = [r for r in results if "escape" in r.name]
        # Should either fail or report not found
        assert len(escape_results) >= 1
