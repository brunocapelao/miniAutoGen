"""Tests for DA-9 backward compatibility.

Ensures old YAML keys, old class names, and old CLI commands
continue to work after the terminology migration.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from miniautogen.cli.config import (
    CONFIG_FILENAME,
    EngineConfig,
    EngineProfileConfig,
    FlowConfig,
    PipelineConfig,
    ProjectConfig,
    WorkspaceConfig,
    load_config,
)


class TestClassAliases:
    """Old class names should still be importable and usable."""

    def test_project_config_is_workspace_config(self) -> None:
        assert ProjectConfig is WorkspaceConfig

    def test_pipeline_config_is_flow_config(self) -> None:
        assert PipelineConfig is FlowConfig

    def test_engine_profile_config_is_engine_config(self) -> None:
        assert EngineProfileConfig is EngineConfig


class TestYAMLBackwardCompat:
    """Old YAML keys should load correctly."""

    def test_old_yaml_keys_load(self, tmp_path: Path) -> None:
        """A miniautogen.yaml with old keys should load."""
        data = {
            "project": {"name": "legacy"},
            "defaults": {"engine_profile": "default_api"},
            "engine_profiles": {
                "default_api": {"kind": "api", "provider": "litellm"},
            },
            "pipelines": {
                "main": {"target": "pipelines.main:build"},
            },
        }
        config_file = tmp_path / CONFIG_FILENAME
        config_file.write_text(yaml.dump(data))
        config = load_config(config_file)

        # New field names work
        assert "default_api" in config.engines
        assert "main" in config.flows

        # Old property aliases work
        assert "default_api" in config.engine_profiles
        assert "main" in config.pipelines

    def test_new_yaml_keys_load(self, tmp_path: Path) -> None:
        """A miniautogen.yaml with new keys should load."""
        data = {
            "project": {"name": "modern"},
            "defaults": {"engine": "default_api"},
            "engines": {
                "default_api": {"kind": "api", "provider": "litellm"},
            },
            "flows": {
                "main": {"target": "flows.main:build"},
            },
        }
        config_file = tmp_path / CONFIG_FILENAME
        config_file.write_text(yaml.dump(data))
        config = load_config(config_file)

        assert "default_api" in config.engines
        assert "main" in config.flows
        assert config.defaults.engine == "default_api"

    def test_mixed_yaml_keys_prefer_new(self, tmp_path: Path) -> None:
        """When both old and new keys present, new key wins."""
        data = {
            "project": {"name": "mixed"},
            "engines": {
                "new_engine": {"kind": "api", "provider": "openai"},
            },
            "engine_profiles": {
                "old_engine": {"kind": "api", "provider": "litellm"},
            },
        }
        config_file = tmp_path / CONFIG_FILENAME
        config_file.write_text(yaml.dump(data))
        config = load_config(config_file)

        # New key wins, old key is dropped
        assert "new_engine" in config.engines
        assert "old_engine" not in config.engines


class TestCLIBackwardCompat:
    """Old CLI commands should still work."""

    def test_pipeline_command_registered(self) -> None:
        from miniautogen.cli.main import cli

        # pipeline command should exist (hidden but functional)
        cmd = cli.get_command(None, "pipeline")
        assert cmd is not None
        assert cmd.hidden is True

    def test_flow_command_registered(self) -> None:
        from miniautogen.cli.main import cli

        # flow command should exist and be visible
        cmd = cli.get_command(None, "flow")
        assert cmd is not None
        assert cmd.hidden is not True


class TestPropertyAliases:
    """Backward compat properties should work."""

    def test_workspace_config_engine_profiles_property(self) -> None:
        config = WorkspaceConfig(
            project={"name": "test"},
            engines={"default": {"kind": "api", "provider": "litellm"}},
        )
        assert config.engine_profiles is config.engines

    def test_workspace_config_pipelines_property(self) -> None:
        config = WorkspaceConfig(
            project={"name": "test"},
            flows={"main": {"target": "flows.main:build"}},
        )
        assert config.pipelines is config.flows

    def test_defaults_engine_profile_property(self) -> None:
        config = WorkspaceConfig(
            project={"name": "test"},
            defaults={"engine": "my_engine"},
        )
        assert config.defaults.engine_profile == "my_engine"
