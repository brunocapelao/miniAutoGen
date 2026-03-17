"""Tests for agent CLI command group."""

import yaml
from click.testing import CliRunner

from miniautogen.cli.main import cli


def _init_project(tmp_path, monkeypatch):
    """Helper: init a project and chdir into it."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    runner.invoke(cli, ["init", "proj"])
    monkeypatch.chdir(tmp_path / "proj")
    return runner


def test_agent_create_silent(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, [
        "agent", "create", "writer",
        "--role", "Writer",
        "--goal", "Write articles",
        "--engine", "default_api",
    ])
    assert result.exit_code == 0, result.output
    assert "created" in result.output.lower()
    assert (tmp_path / "proj" / "agents" / "writer.yaml").is_file()


def test_agent_create_duplicate_fails(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    # Create first
    runner.invoke(cli, [
        "agent", "create", "writer",
        "--role", "Writer",
        "--goal", "Write",
        "--engine", "default_api",
    ])
    # Create again
    result = runner.invoke(cli, [
        "agent", "create", "writer",
        "--role", "Writer",
        "--goal", "Write",
        "--engine", "default_api",
    ])
    assert result.exit_code != 0


def test_agent_create_bad_engine(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, [
        "agent", "create", "writer",
        "--role", "Writer",
        "--goal", "Write",
        "--engine", "nonexistent_engine",
    ])
    assert result.exit_code != 0


def test_agent_list(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, ["agent", "list"])
    assert result.exit_code == 0
    # Default project has a researcher agent
    assert "researcher" in result.output.lower()


def test_agent_list_json(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, ["agent", "list", "--format", "json"])
    assert result.exit_code == 0
    assert '"name"' in result.output


def test_agent_show(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, ["agent", "show", "researcher"])
    assert result.exit_code == 0
    assert "role:" in result.output.lower() or "research" in result.output.lower()


def test_agent_show_json(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, ["agent", "show", "researcher", "--format", "json"])
    assert result.exit_code == 0
    assert '"role"' in result.output


def test_agent_show_not_found(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, ["agent", "show", "nonexistent"])
    assert result.exit_code != 0


def test_agent_update(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, [
        "agent", "update", "researcher",
        "--role", "Senior Researcher",
    ])
    assert result.exit_code == 0
    assert "updated" in result.output.lower()

    data = yaml.safe_load(
        (tmp_path / "proj" / "agents" / "researcher.yaml").read_text()
    )
    assert data["role"] == "Senior Researcher"


def test_agent_update_dry_run(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, [
        "agent", "update", "researcher",
        "--role", "Senior Researcher",
        "--dry-run",
    ])
    assert result.exit_code == 0
    assert "dry run" in result.output.lower()

    # Original unchanged
    data = yaml.safe_load(
        (tmp_path / "proj" / "agents" / "researcher.yaml").read_text()
    )
    assert data["role"] != "Senior Researcher"


def test_agent_delete(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, [
        "agent", "delete", "researcher", "--yes",
    ])
    assert result.exit_code == 0
    assert "deleted" in result.output.lower()
    assert not (tmp_path / "proj" / "agents" / "researcher.yaml").exists()


def test_agent_delete_not_found(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, [
        "agent", "delete", "nonexistent", "--yes",
    ])
    assert result.exit_code != 0
