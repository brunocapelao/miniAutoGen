"""Tests for the status CLI command."""

from __future__ import annotations

import json

from click.testing import CliRunner

from miniautogen.cli.main import cli


def _init_project(tmp_path, monkeypatch) -> None:
    """Helper: init a project and chdir into it."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "myproject"])
    assert result.exit_code == 0, result.output
    monkeypatch.chdir(tmp_path / "myproject")


def test_status_text_output(tmp_path, monkeypatch) -> None:
    """Text output shows project name and resource counts."""
    _init_project(tmp_path, monkeypatch)
    runner = CliRunner()
    result = runner.invoke(cli, ["status"])
    assert result.exit_code == 0, result.output
    assert "myproject" in result.output
    assert "Workspace:" in result.output
    assert "Agents:" in result.output
    assert "Engines:" in result.output
    assert "Flows:" in result.output
    assert "Server:" in result.output


def test_status_json_output(tmp_path, monkeypatch) -> None:
    """JSON output contains expected top-level keys."""
    _init_project(tmp_path, monkeypatch)
    runner = CliRunner()
    result = runner.invoke(cli, ["status", "--format", "json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert "project" in data
    assert "server" in data
    assert "agents" in data
    assert "engines" in data
    assert "flows" in data
    assert data["project"]["name"] == "myproject"


def test_status_no_project(tmp_path, monkeypatch) -> None:
    """Error when no miniautogen.yaml exists."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["status"])
    assert result.exit_code != 0
    assert "miniautogen.yaml" in result.output or "No" in result.output


def test_status_shows_agent_names(tmp_path, monkeypatch) -> None:
    """Text output includes agent names from the agents/ directory."""
    _init_project(tmp_path, monkeypatch)
    runner = CliRunner()
    result = runner.invoke(cli, ["status"])
    assert result.exit_code == 0, result.output
    # The init scaffold creates a 'researcher' agent
    assert "researcher" in result.output
