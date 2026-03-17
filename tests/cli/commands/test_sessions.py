"""Tests for sessions CLI command."""

from pathlib import Path

import yaml
from click.testing import CliRunner

from miniautogen.cli.config import CONFIG_FILENAME
from miniautogen.cli.main import cli


def _make_project(tmp_path: Path) -> Path:
    config = {
        "project": {"name": "test"},
        "defaults": {"engine_profile": "default_api"},
        "engine_profiles": {
            "default_api": {"kind": "api", "provider": "litellm"},
        },
        "pipelines": {"main": {"target": "pipelines.main:build"}},
    }
    (tmp_path / CONFIG_FILENAME).write_text(yaml.dump(config))
    return tmp_path


def test_sessions_list_empty(tmp_path, monkeypatch) -> None:
    _make_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["sessions", "list"])
    assert result.exit_code == 0
    assert "no runs" in result.output.lower()


def test_sessions_list_json(tmp_path, monkeypatch) -> None:
    _make_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        cli, ["sessions", "list", "--format", "json"],
    )
    assert result.exit_code == 0
    assert "[]" in result.output


def test_sessions_clean_requires_flag(tmp_path, monkeypatch) -> None:
    _make_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["sessions", "clean"])
    assert result.exit_code != 0


def test_sessions_clean_with_yes(tmp_path, monkeypatch) -> None:
    _make_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["sessions", "clean", "--yes"])
    assert result.exit_code == 0
    assert "deleted" in result.output.lower()


def test_sessions_no_project(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["sessions", "list"])
    assert result.exit_code != 0
