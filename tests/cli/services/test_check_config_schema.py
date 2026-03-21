"""Tests for config schema validation — load_config() and _check_config_schema().

Covers YAML parsing failures, Pydantic schema rejections, and edge cases
that users hit when manually editing miniautogen.yaml.

Design note: _check_config_schema() always returns passed=True because it
receives an already-validated ProjectConfig. The real validation gate is
load_config(), which raises on malformed YAML or schema violations. These
tests cover both layers.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from miniautogen.cli.config import (
    CONFIG_FILENAME,
    WorkspaceConfig,
    load_config,
)
from miniautogen.cli.services.check_project import _check_config_schema


def _write_raw(path: Path, content: str) -> Path:
    """Write raw text to a config file, return the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def _valid_config_dict() -> dict:
    return {
        "project": {"name": "test-proj", "version": "0.1.0"},
        "defaults": {"engine": "default_api", "memory_profile": "default"},
        "engines": {
            "default_api": {
                "kind": "api",
                "provider": "litellm",
                "model": "gpt-4o-mini",
            },
        },
        "flows": {
            "main": {"target": "pipelines.main:build_pipeline"},
        },
    }


# ── _check_config_schema (post-validation) ──────────────────────────────


class TestCheckConfigSchemaPostValidation:
    """_check_config_schema receives an already-validated config and
    always returns passed=True. Verify the contract."""

    def test_valid_config_passes(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / CONFIG_FILENAME
        cfg_path.write_text(yaml.dump(_valid_config_dict()))
        config = load_config(cfg_path)
        result = _check_config_schema(config)
        assert result.passed is True
        assert result.name == "config_schema"
        assert result.category == "static"

    def test_minimal_config_passes(self, tmp_path: Path) -> None:
        """Minimal config with only required fields passes."""
        minimal = {"project": {"name": "minimal"}}
        cfg_path = tmp_path / CONFIG_FILENAME
        cfg_path.write_text(yaml.dump(minimal))
        config = load_config(cfg_path)
        result = _check_config_schema(config)
        assert result.passed is True


# ── load_config — YAML syntax errors ────────────────────────────────────


class TestMalformedYaml:
    """YAML syntax errors must raise before Pydantic ever sees the data."""

    def test_yaml_syntax_error_raises(self, tmp_path: Path) -> None:
        """Completely broken YAML syntax raises yaml.YAMLError."""
        cfg_path = _write_raw(
            tmp_path / CONFIG_FILENAME,
            "project:\n  name: test\n  bad_indent:\n- broken\n",
        )
        with pytest.raises(yaml.YAMLError):
            load_config(cfg_path)

    def test_yaml_tab_indentation_raises(self, tmp_path: Path) -> None:
        """Tabs in YAML raise a scanner error."""
        cfg_path = _write_raw(
            tmp_path / CONFIG_FILENAME,
            "project:\n\tname: test\n",
        )
        with pytest.raises(yaml.YAMLError):
            load_config(cfg_path)

    def test_yaml_duplicate_colon_raises(self, tmp_path: Path) -> None:
        """Malformed value with extra colons raises."""
        cfg_path = _write_raw(
            tmp_path / CONFIG_FILENAME,
            ":\n  bad: yaml: content:\n",
        )
        with pytest.raises(yaml.YAMLError):
            load_config(cfg_path)


# ── load_config — non-dict YAML ─────────────────────────────────────────


class TestNonDictYaml:
    """YAML that parses but is not a mapping must raise ValueError."""

    def test_yaml_list_raises_value_error(self, tmp_path: Path) -> None:
        cfg_path = _write_raw(
            tmp_path / CONFIG_FILENAME,
            "- item1\n- item2\n",
        )
        with pytest.raises(ValueError, match="expected mapping"):
            load_config(cfg_path)

    def test_yaml_scalar_raises_value_error(self, tmp_path: Path) -> None:
        cfg_path = _write_raw(
            tmp_path / CONFIG_FILENAME,
            "just a plain string\n",
        )
        with pytest.raises(ValueError, match="expected mapping"):
            load_config(cfg_path)

    def test_empty_file_raises_value_error(self, tmp_path: Path) -> None:
        """Empty YAML file (safe_load returns None) raises ValueError."""
        cfg_path = _write_raw(tmp_path / CONFIG_FILENAME, "")
        with pytest.raises(ValueError, match="expected mapping"):
            load_config(cfg_path)


# ── load_config — Pydantic schema violations ────────────────────────────


class TestPydanticSchemaRejections:
    """YAML that is valid mapping but violates WorkspaceConfig schema."""

    def test_missing_required_project_field(self, tmp_path: Path) -> None:
        """'project' is required — omitting it raises ValidationError."""
        cfg_path = _write_raw(
            tmp_path / CONFIG_FILENAME,
            yaml.dump({"engines": {}}),
        )
        with pytest.raises(ValidationError) as exc_info:
            load_config(cfg_path)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("project",) for e in errors)

    def test_missing_project_name(self, tmp_path: Path) -> None:
        """project.name is required."""
        cfg_path = _write_raw(
            tmp_path / CONFIG_FILENAME,
            yaml.dump({"project": {"version": "1.0.0"}}),
        )
        with pytest.raises(ValidationError) as exc_info:
            load_config(cfg_path)
        errors = exc_info.value.errors()
        assert any("name" in str(e["loc"]) for e in errors)

    def test_wrong_type_for_project(self, tmp_path: Path) -> None:
        """project must be a mapping, not a string."""
        cfg_path = _write_raw(
            tmp_path / CONFIG_FILENAME,
            yaml.dump({"project": "not-a-dict"}),
        )
        with pytest.raises(ValidationError):
            load_config(cfg_path)

    def test_wrong_type_for_engines(self, tmp_path: Path) -> None:
        """engines must be a dict of engine configs, not a list."""
        data = _valid_config_dict()
        data["engines"] = ["invalid", "list"]
        cfg_path = _write_raw(
            tmp_path / CONFIG_FILENAME,
            yaml.dump(data),
        )
        with pytest.raises(ValidationError):
            load_config(cfg_path)

    def test_wrong_type_for_flows(self, tmp_path: Path) -> None:
        """flows must be a dict, not a string."""
        data = _valid_config_dict()
        data["flows"] = "not-a-dict"
        cfg_path = _write_raw(
            tmp_path / CONFIG_FILENAME,
            yaml.dump(data),
        )
        with pytest.raises(ValidationError):
            load_config(cfg_path)

    def test_flow_missing_target_and_mode(self, tmp_path: Path) -> None:
        """Flow must have either 'target' or 'mode'."""
        data = _valid_config_dict()
        data["flows"]["broken"] = {"participants": ["agent1"]}
        cfg_path = _write_raw(
            tmp_path / CONFIG_FILENAME,
            yaml.dump(data),
        )
        with pytest.raises(ValidationError, match="target.*mode|mode.*target"):
            load_config(cfg_path)

    def test_engine_invalid_temperature_type(self, tmp_path: Path) -> None:
        """Engine temperature must be numeric, not a string."""
        data = _valid_config_dict()
        data["engines"]["default_api"]["temperature"] = "hot"
        cfg_path = _write_raw(
            tmp_path / CONFIG_FILENAME,
            yaml.dump(data),
        )
        with pytest.raises(ValidationError):
            load_config(cfg_path)


# ── load_config — extra/unknown fields ──────────────────────────────────


class TestExtraFields:
    """Pydantic default behavior: extra fields are allowed (ignored).
    Verify this does not cause rejection."""

    def test_extra_top_level_field_accepted(self, tmp_path: Path) -> None:
        data = _valid_config_dict()
        data["custom_metadata"] = {"author": "test"}
        cfg_path = _write_raw(
            tmp_path / CONFIG_FILENAME,
            yaml.dump(data),
        )
        # Should not raise — extra fields are tolerated by default
        config = load_config(cfg_path)
        assert config.project.name == "test-proj"

    def test_extra_engine_field_accepted(self, tmp_path: Path) -> None:
        data = _valid_config_dict()
        data["engines"]["default_api"]["custom_option"] = True
        cfg_path = _write_raw(
            tmp_path / CONFIG_FILENAME,
            yaml.dump(data),
        )
        config = load_config(cfg_path)
        assert "default_api" in config.engines


# ── load_config — backward compatibility (old keys) ─────────────────────


class TestBackwardCompatibility:
    """Old key names (engine_profiles, pipelines) still work."""

    def test_old_keys_engine_profiles_and_pipelines(
        self, tmp_path: Path,
    ) -> None:
        data = {
            "project": {"name": "compat"},
            "engine_profiles": {
                "default_api": {"provider": "litellm", "model": "gpt-4o"},
            },
            "pipelines": {
                "main": {"target": "mod:fn"},
            },
        }
        cfg_path = _write_raw(
            tmp_path / CONFIG_FILENAME,
            yaml.dump(data),
        )
        config = load_config(cfg_path)
        assert "default_api" in config.engines
        assert "main" in config.flows


# ── load_config — file-level errors ─────────────────────────────────────


class TestFileErrors:
    def test_nonexistent_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "does_not_exist.yaml")
