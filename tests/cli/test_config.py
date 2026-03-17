"""Tests for CLI config loading."""

from pathlib import Path

import pytest
import yaml

from miniautogen.cli.config import (
    CONFIG_FILENAME,
    ProjectConfig,
    find_project_root,
    load_config,
)


def _write_config(path: Path, data: dict) -> Path:
    config_file = path / CONFIG_FILENAME
    config_file.write_text(yaml.dump(data))
    return config_file


def test_project_config_minimal() -> None:
    config = ProjectConfig(
        project={"name": "test", "version": "1.0.0"},
    )
    assert config.project.name == "test"
    assert config.defaults.engine_profile == "default_api"


def test_project_config_full() -> None:
    config = ProjectConfig(
        project={"name": "test", "version": "1.0.0"},
        defaults={"engine_profile": "gemini", "memory_profile": "research"},
        engine_profiles={
            "gemini": {
                "kind": "api",
                "provider": "gemini",
                "model": "gemini-2.5-pro",
            },
        },
        memory_profiles={
            "research": {"session": True, "retrieval": {"enabled": True}},
        },
        pipelines={"main": {"target": "pipelines.main:build"}},
        database={"url": "sqlite+aiosqlite:///test.db"},
    )
    assert config.engine_profiles["gemini"].provider == "gemini"
    assert config.memory_profiles["research"].session is True


def test_find_project_root_found(tmp_path: Path) -> None:
    _write_config(tmp_path, {"project": {"name": "test"}})
    result = find_project_root(tmp_path)
    assert result == tmp_path


def test_find_project_root_nested(tmp_path: Path) -> None:
    _write_config(tmp_path, {"project": {"name": "test"}})
    nested = tmp_path / "a" / "b" / "c"
    nested.mkdir(parents=True)
    result = find_project_root(nested)
    assert result == tmp_path


def test_find_project_root_not_found(tmp_path: Path) -> None:
    result = find_project_root(tmp_path)
    assert result is None


def test_load_config_valid(tmp_path: Path) -> None:
    data = {
        "project": {"name": "myproject", "version": "0.1.0"},
        "pipelines": {"main": {"target": "pipelines.main:run"}},
    }
    config_file = _write_config(tmp_path, data)
    config = load_config(config_file)
    assert config.project.name == "myproject"
    assert config.pipelines["main"].target == "pipelines.main:run"


def test_load_config_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "nonexistent.yaml")


def test_load_config_invalid_yaml(tmp_path: Path) -> None:
    config_file = tmp_path / CONFIG_FILENAME
    config_file.write_text("not a mapping")
    with pytest.raises(ValueError, match="expected mapping"):
        load_config(config_file)
