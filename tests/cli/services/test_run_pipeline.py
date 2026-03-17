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


def test_resolve_valid_target(tmp_path: Path) -> None:
    """Resolve a target within a project."""
    mod_dir = tmp_path / "mypkg"
    mod_dir.mkdir()
    (mod_dir / "__init__.py").write_text("")
    (mod_dir / "pipeline.py").write_text("def build(): return 'ok'")

    import sys
    sys.path.append(str(tmp_path))
    try:
        fn = resolve_pipeline_target("mypkg.pipeline:build", tmp_path)
        assert callable(fn)
    finally:
        sys.path.remove(str(tmp_path))


def test_resolve_rejects_outside_project(tmp_path: Path) -> None:
    with pytest.raises((ValueError, ImportError)):
        resolve_pipeline_target("os:system", tmp_path)


def test_resolve_rejects_path_traversal(tmp_path: Path) -> None:
    with pytest.raises((ValueError, ImportError)):
        resolve_pipeline_target("....etc.passwd:read", tmp_path)


def test_resolve_invalid_format(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="expected"):
        resolve_pipeline_target("no_colon_here", tmp_path)


def test_resolve_missing_module(tmp_path: Path) -> None:
    with pytest.raises(ImportError):
        resolve_pipeline_target("nonexistent.module:func", tmp_path)


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
