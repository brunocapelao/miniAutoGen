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
    ], input="\n\ny\n")
    assert result.exit_code == 0, result.output
    assert "created" in result.output.lower()
    assert (tmp_path / "proj" / "agents" / "writer.yaml").is_file()


def test_agent_create_interactive(tmp_path, monkeypatch) -> None:
    """Test interactive wizard prompts for all fields."""
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(
        cli,
        ["agent", "create", "myagent"],
        input="default_api\nAnalyst\nAnalyze data\n0.5\n4096\ny\n",
    )
    assert result.exit_code == 0, result.output
    assert "created" in result.output.lower()


def test_agent_create_with_temperature(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, [
        "agent", "create", "writer",
        "--role", "Writer",
        "--goal", "Write",
        "--engine", "default_api",
        "--temperature", "0.8",
    ], input="\ny\n")
    assert result.exit_code == 0, result.output
    data = yaml.safe_load(
        (tmp_path / "proj" / "agents" / "writer.yaml").read_text()
    )
    assert data.get("temperature") == 0.8


def test_agent_create_validates_schema(tmp_path, monkeypatch) -> None:
    """Agent create validates against AgentSpec before writing."""
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, [
        "agent", "create", "valid-agent",
        "--role", "Tester",
        "--goal", "Test things",
        "--engine", "default_api",
    ], input="\n\ny\n")
    assert result.exit_code == 0, result.output
    agent_path = tmp_path / "proj" / "agents" / "valid-agent.yaml"
    assert agent_path.is_file()


def test_agent_create_cancelled(tmp_path, monkeypatch) -> None:
    """Test wizard cancellation at confirmation prompt."""
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, [
        "agent", "create", "writer",
        "--role", "Writer",
        "--goal", "Write",
        "--engine", "default_api",
    ], input="\n\nn\n")
    assert result.exit_code == 0
    assert "cancelled" in result.output.lower()
    assert not (tmp_path / "proj" / "agents" / "writer.yaml").exists()


def test_agent_create_duplicate_fails(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    runner.invoke(cli, [
        "agent", "create", "writer",
        "--role", "Writer",
        "--goal", "Write",
        "--engine", "default_api",
    ], input="\n\ny\n")
    result = runner.invoke(cli, [
        "agent", "create", "writer",
        "--role", "Writer",
        "--goal", "Write",
        "--engine", "default_api",
    ], input="\n\ny\n")
    assert result.exit_code != 0


def test_agent_create_bad_engine(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, [
        "agent", "create", "writer",
        "--role", "Writer",
        "--goal", "Write",
        "--engine", "nonexistent_engine",
    ], input="\n\ny\n")
    assert result.exit_code != 0


def test_agent_list(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, ["agent", "list"])
    assert result.exit_code == 0
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
