"""Tests for check CLI command."""

from pathlib import Path

import yaml
from click.testing import CliRunner

from miniautogen.cli.config import CONFIG_FILENAME
from miniautogen.cli.main import cli


def _make_valid_project(tmp_path: Path) -> Path:
    config = {
        "project": {"name": "test", "version": "0.1.0"},
        "defaults": {"engine_profile": "default_api", "memory_profile": "default"},
        "engine_profiles": {
            "default_api": {"kind": "api", "provider": "litellm", "model": "gpt-4o-mini"},
        },
        "memory_profiles": {"default": {"session": True}},
        "pipelines": {"main": {"target": "pipelines.main:build_pipeline"}},
    }
    (tmp_path / CONFIG_FILENAME).write_text(yaml.dump(config))
    (tmp_path / "pipelines").mkdir()
    (tmp_path / "pipelines" / "main.py").write_text("def build_pipeline(): pass")
    return tmp_path


def test_check_passes_valid_project(tmp_path, monkeypatch) -> None:
    _make_valid_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["check"])
    assert result.exit_code == 0
    assert "passed" in result.output.lower()


def test_check_json_format(tmp_path, monkeypatch) -> None:
    _make_valid_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["check", "--format", "json"])
    assert result.exit_code == 0
    assert '"passed": true' in result.output


def test_check_no_project(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["check"])
    assert result.exit_code != 0
