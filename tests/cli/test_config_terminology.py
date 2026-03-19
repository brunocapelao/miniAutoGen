"""Tests for DA-9 terminology migration in config schema."""

from __future__ import annotations

import warnings

import yaml

from miniautogen.cli.config import (
    CONFIG_FILENAME,
    DefaultsConfig,
    EngineConfig,
    FlowConfig,
    WorkspaceConfig,
    load_config,
)


def test_workspace_config_exists() -> None:
    """WorkspaceConfig should be importable and usable."""
    config = WorkspaceConfig(
        project={"name": "test", "version": "1.0.0"},
    )
    assert config.project.name == "test"


def test_workspace_config_accepts_engines_key() -> None:
    """The 'engines' key should be accepted in WorkspaceConfig."""
    config = WorkspaceConfig(
        project={"name": "test"},
        engines={"default": {"kind": "api", "provider": "litellm"}},
    )
    assert "default" in config.engines


def test_workspace_config_accepts_flows_key() -> None:
    """The 'flows' key should be accepted in WorkspaceConfig."""
    config = WorkspaceConfig(
        project={"name": "test"},
        flows={"main": {"target": "pipelines.main:build_pipeline"}},
    )
    assert "main" in config.flows


def test_workspace_config_backward_compat_engine_profiles() -> None:
    """The old 'engine_profiles' key should still work with deprecation warning."""
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        config = WorkspaceConfig(
            project={"name": "test"},
            engine_profiles={"default": {"kind": "api", "provider": "litellm"}},
        )
        assert "default" in config.engines


def test_workspace_config_backward_compat_pipelines() -> None:
    """The old 'pipelines' key should still work with deprecation warning."""
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        config = WorkspaceConfig(
            project={"name": "test"},
            pipelines={"main": {"target": "pipelines.main:build_pipeline"}},
        )
        assert "main" in config.flows


def test_flow_config_exists() -> None:
    """FlowConfig should be importable and usable."""
    fc = FlowConfig(target="flows.main:build")
    assert fc.target == "flows.main:build"


def test_engine_config_exists() -> None:
    """EngineConfig should be importable and usable."""
    ec = EngineConfig(kind="api", provider="openai")
    assert ec.provider == "openai"


def test_defaults_config_engine_field() -> None:
    """DefaultsConfig should accept 'engine' as the new field name."""
    dc = DefaultsConfig(engine="my_engine")
    assert dc.engine == "my_engine"


def test_defaults_config_backward_compat_engine_profile() -> None:
    """DefaultsConfig should accept old 'engine_profile' key."""
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        dc = DefaultsConfig(engine_profile="old_engine")
        assert dc.engine == "old_engine"


def test_load_config_old_yaml_keys(tmp_path) -> None:
    """Loading a YAML file with old keys should work (backward compat)."""
    data = {
        "project": {"name": "old-project", "version": "0.1.0"},
        "engine_profiles": {
            "default_api": {"kind": "api", "provider": "litellm"},
        },
        "pipelines": {"main": {"target": "pipelines.main:run"}},
    }
    config_file = tmp_path / CONFIG_FILENAME
    config_file.write_text(yaml.dump(data))
    config = load_config(config_file)
    assert "default_api" in config.engines
    assert "main" in config.flows


def test_project_config_alias_still_importable() -> None:
    """ProjectConfig should still be importable as a backward compat alias."""
    from miniautogen.cli.config import ProjectConfig

    config = ProjectConfig(project={"name": "test"})
    assert config.project.name == "test"
