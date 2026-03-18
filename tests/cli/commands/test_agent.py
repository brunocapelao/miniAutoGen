"""Tests for agent CLI command group."""

import yaml
from pathlib import Path

from miniautogen.cli.main import cli


def _agents_dir():
    return Path.cwd() / "agents"


def test_agent_create_silent(init_project) -> None:
    runner = init_project
    result = runner.invoke(cli, [
        "agent", "create", "writer",
        "--role", "Writer",
        "--goal", "Write articles",
        "--engine", "default_api",
    ], input="\n\ny\n")
    assert result.exit_code == 0, result.output
    assert "created" in result.output.lower()
    assert (_agents_dir() / "writer.yaml").is_file()


def test_agent_create_interactive(init_project) -> None:
    """Test interactive wizard prompts for all fields."""
    runner = init_project
    result = runner.invoke(
        cli,
        ["agent", "create", "myagent"],
        input="default_api\nAnalyst\nAnalyze data\n0.5\n4096\ny\n",
    )
    assert result.exit_code == 0, result.output
    assert "created" in result.output.lower()


def test_agent_create_with_temperature(init_project) -> None:
    runner = init_project
    result = runner.invoke(cli, [
        "agent", "create", "writer",
        "--role", "Writer",
        "--goal", "Write",
        "--engine", "default_api",
        "--temperature", "0.8",
    ], input="\ny\n")
    assert result.exit_code == 0, result.output
    data = yaml.safe_load(
        (_agents_dir() / "writer.yaml").read_text()
    )
    assert data.get("temperature") == 0.8


def test_agent_create_validates_schema(init_project) -> None:
    """Agent create validates against AgentSpec before writing."""
    runner = init_project
    result = runner.invoke(cli, [
        "agent", "create", "valid-agent",
        "--role", "Tester",
        "--goal", "Test things",
        "--engine", "default_api",
    ], input="\n\ny\n")
    assert result.exit_code == 0, result.output
    agent_path = _agents_dir() / "valid-agent.yaml"
    assert agent_path.is_file()


def test_agent_create_cancelled(init_project) -> None:
    """Test wizard cancellation at confirmation prompt."""
    runner = init_project
    result = runner.invoke(cli, [
        "agent", "create", "writer",
        "--role", "Writer",
        "--goal", "Write",
        "--engine", "default_api",
    ], input="\n\nn\n")
    assert result.exit_code == 0
    assert "cancelled" in result.output.lower()
    assert not (_agents_dir() / "writer.yaml").exists()


def test_agent_create_duplicate_fails(init_project) -> None:
    runner = init_project
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


def test_agent_create_bad_engine(init_project) -> None:
    runner = init_project
    result = runner.invoke(cli, [
        "agent", "create", "writer",
        "--role", "Writer",
        "--goal", "Write",
        "--engine", "nonexistent_engine",
    ], input="\n\ny\n")
    assert result.exit_code != 0


def test_agent_list(init_project) -> None:
    runner = init_project
    result = runner.invoke(cli, ["agent", "list"])
    assert result.exit_code == 0
    assert "researcher" in result.output.lower()


def test_agent_list_json(init_project) -> None:
    runner = init_project
    result = runner.invoke(cli, ["agent", "list", "--format", "json"])
    assert result.exit_code == 0
    assert '"name"' in result.output


def test_agent_show(init_project) -> None:
    runner = init_project
    result = runner.invoke(cli, ["agent", "show", "researcher"])
    assert result.exit_code == 0
    assert "role:" in result.output.lower() or "research" in result.output.lower()


def test_agent_show_json(init_project) -> None:
    runner = init_project
    result = runner.invoke(cli, ["agent", "show", "researcher", "--format", "json"])
    assert result.exit_code == 0
    assert '"role"' in result.output


def test_agent_show_not_found(init_project) -> None:
    runner = init_project
    result = runner.invoke(cli, ["agent", "show", "nonexistent"])
    assert result.exit_code != 0


def test_agent_update(init_project) -> None:
    runner = init_project
    result = runner.invoke(cli, [
        "agent", "update", "researcher",
        "--role", "Senior Researcher",
    ])
    assert result.exit_code == 0
    assert "updated" in result.output.lower()

    data = yaml.safe_load(
        (_agents_dir() / "researcher.yaml").read_text()
    )
    assert data["role"] == "Senior Researcher"


def test_agent_update_dry_run(init_project) -> None:
    runner = init_project
    result = runner.invoke(cli, [
        "agent", "update", "researcher",
        "--role", "Senior Researcher",
        "--dry-run",
    ])
    assert result.exit_code == 0
    assert "dry run" in result.output.lower()

    data = yaml.safe_load(
        (_agents_dir() / "researcher.yaml").read_text()
    )
    assert data["role"] != "Senior Researcher"


def test_agent_delete(init_project) -> None:
    runner = init_project
    result = runner.invoke(cli, [
        "agent", "delete", "researcher", "--yes",
    ])
    assert result.exit_code == 0
    assert "deleted" in result.output.lower()
    assert not (_agents_dir() / "researcher.yaml").exists()


def test_agent_delete_not_found(init_project) -> None:
    runner = init_project
    result = runner.invoke(cli, [
        "agent", "delete", "nonexistent", "--yes",
    ])
    assert result.exit_code != 0
