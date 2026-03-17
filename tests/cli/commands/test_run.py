"""Tests for run CLI command."""

from pathlib import Path

import yaml
from click.testing import CliRunner

from miniautogen.cli.config import CONFIG_FILENAME
from miniautogen.cli.main import cli


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


def test_run_success(tmp_path, monkeypatch) -> None:
    _make_runnable_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["run"])
    assert result.exit_code == 0
    assert "completed" in result.output.lower()


def test_run_json_format(tmp_path, monkeypatch) -> None:
    _make_runnable_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["run", "--format", "json"])
    assert result.exit_code == 0
    assert '"status": "completed"' in result.output


def test_run_missing_pipeline(tmp_path, monkeypatch) -> None:
    _make_runnable_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["run", "nonexistent"])
    assert result.exit_code != 0


def test_run_no_project(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["run"])
    assert result.exit_code != 0
