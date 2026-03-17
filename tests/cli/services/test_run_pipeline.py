"""Tests for run_pipeline service."""

from pathlib import Path

import pytest
import yaml

from miniautogen.cli.config import CONFIG_FILENAME, load_config
from miniautogen.cli.services.run_pipeline import (
    execute_pipeline,
    resolve_pipeline_target,
)


def _make_runnable_project(tmp_path: Path) -> Path:
    config = {
        "project": {"name": "test"},
        "defaults": {"engine_profile": "default_api"},
        "engine_profiles": {
            "default_api": {"kind": "api", "provider": "litellm"},
        },
        "pipelines": {"main": {"target": "pipelines.main:build_pipeline"}},
    }
    (tmp_path / CONFIG_FILENAME).write_text(yaml.dump(config))
    pipelines_dir = tmp_path / "pipelines"
    pipelines_dir.mkdir()
    (pipelines_dir / "__init__.py").write_text("")
    (pipelines_dir / "main.py").write_text(
        "class P:\n"
        "    async def run(self, state):\n"
        '        return {**state, "done": True}\n'
        "def build_pipeline():\n"
        "    return P()\n"
    )
    return tmp_path


def test_resolve_valid_target() -> None:
    # Use a known stdlib module
    fn = resolve_pipeline_target("os.path:join")
    assert callable(fn)


def test_resolve_invalid_format() -> None:
    with pytest.raises(ValueError, match="expected"):
        resolve_pipeline_target("no_colon_here")


def test_resolve_missing_module() -> None:
    with pytest.raises(ModuleNotFoundError):
        resolve_pipeline_target("nonexistent.module:func")


@pytest.mark.anyio
async def test_execute_pipeline_success(tmp_path: Path) -> None:
    project = _make_runnable_project(tmp_path)
    config = load_config(project / CONFIG_FILENAME)
    result = await execute_pipeline(config, "main", project)
    assert result["status"] == "completed"


@pytest.mark.anyio
async def test_execute_pipeline_not_found(tmp_path: Path) -> None:
    project = _make_runnable_project(tmp_path)
    config = load_config(project / CONFIG_FILENAME)
    with pytest.raises(KeyError, match="nonexistent"):
        await execute_pipeline(config, "nonexistent", project)
