"""Extended tests for pipeline CLI command — interactive wizards, update flags, edge cases."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from miniautogen.cli.main import cli


def _create_agent(name: str, role: str = "assistant") -> None:
    """Create a minimal agent YAML file in cwd/agents/."""
    agents_dir = Path.cwd() / "agents"
    agents_dir.mkdir(exist_ok=True)
    agent_file = agents_dir / f"{name}.yaml"
    agent_file.write_text(
        f"name: {name}\nrole: {role}\ngoal: test\n"
        f"engine_profile: default_api\n"
    )


# ---------------------------------------------------------------------------
# Interactive wizard: workflow mode
# ---------------------------------------------------------------------------


def test_pipeline_create_workflow_interactive_wizard(init_project) -> None:
    """When --mode is omitted, prompt for mode; workflow wizard asks for agents."""
    runner = init_project
    # Input sequence:
    #   1. mode prompt -> "workflow"
    #   2. agents to chain prompt -> "" (empty)
    #   3. confirm -> "y"
    result = runner.invoke(
        cli,
        ["pipeline", "create", "wiz"],
        input="workflow\n\ny\n",
    )
    assert result.exit_code == 0, result.output
    assert "created" in result.output.lower()


def test_pipeline_create_workflow_with_participants_flag(init_project) -> None:
    """Providing --participants skips the agent prompt in workflow mode."""
    runner = init_project
    # Create an agent first so validation passes
    _create_agent("a1")
    result = runner.invoke(
        cli,
        [
            "pipeline", "create", "wf2",
            "--mode", "workflow",
            "--participants", "a1",
        ],
        input="y\n",
    )
    assert result.exit_code == 0, result.output
    assert "created" in result.output.lower()


# ---------------------------------------------------------------------------
# Interactive wizard: deliberation mode
# ---------------------------------------------------------------------------


def test_pipeline_create_deliberation_interactive(init_project) -> None:
    """Deliberation wizard prompts for peers, leader, max_rounds."""
    runner = init_project
    # Create agent for leader/participant validation
    _create_agent("lead", "leader")
    result = runner.invoke(
        cli,
        ["pipeline", "create", "delib", "--mode", "deliberation"],
        # Prompts: participants -> "lead", leader -> "lead", max_rounds -> "5", confirm -> y
        input="lead\nlead\n5\ny\n",
    )
    assert result.exit_code == 0, result.output
    assert "created" in result.output.lower()


def test_pipeline_create_deliberation_with_flags(init_project) -> None:
    """When --participants, --leader, --max-rounds are given, skip prompts."""
    runner = init_project
    _create_agent("d1")
    result = runner.invoke(
        cli,
        [
            "pipeline", "create", "delib2",
            "--mode", "deliberation",
            "--participants", "d1",
            "--leader", "d1",
            "--max-rounds", "3",
        ],
        input="y\n",
    )
    assert result.exit_code == 0, result.output
    assert "created" in result.output.lower()


def test_pipeline_create_deliberation_invalid_max_rounds(init_project) -> None:
    """Non-integer max_rounds in interactive prompt is silently ignored."""
    runner = init_project
    _create_agent("ag")
    result = runner.invoke(
        cli,
        ["pipeline", "create", "delib3", "--mode", "deliberation"],
        # peers -> "ag", leader -> "ag", max_rounds -> "abc" (invalid), confirm -> y
        input="ag\nag\nabc\ny\n",
    )
    assert result.exit_code == 0, result.output
    assert "created" in result.output.lower()


# ---------------------------------------------------------------------------
# Interactive wizard: loop mode
# ---------------------------------------------------------------------------


def test_pipeline_create_loop_interactive(init_project) -> None:
    """Loop wizard prompts for participant agents and router agent."""
    runner = init_project
    _create_agent("router1", "router")
    result = runner.invoke(
        cli,
        ["pipeline", "create", "lp", "--mode", "loop"],
        # participants -> "router1", leader (router) -> "router1", confirm -> y
        input="router1\nrouter1\ny\n",
    )
    assert result.exit_code == 0, result.output
    assert "created" in result.output.lower()


def test_pipeline_create_loop_with_flags(init_project) -> None:
    """Providing --participants and --leader skips loop wizard prompts."""
    runner = init_project
    _create_agent("r1", "router")
    result = runner.invoke(
        cli,
        [
            "pipeline", "create", "lp2",
            "--mode", "loop",
            "--participants", "r1",
            "--leader", "r1",
        ],
        input="y\n",
    )
    assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# Interactive wizard: composite mode
# ---------------------------------------------------------------------------


def test_pipeline_create_composite_interactive(init_project) -> None:
    """Composite wizard lists existing pipelines and prompts for chain."""
    runner = init_project
    # "main" pipeline already exists from init
    result = runner.invoke(
        cli,
        ["pipeline", "create", "comp", "--mode", "composite"],
        # chain prompt -> "main", confirm -> y
        input="main\ny\n",
    )
    assert result.exit_code == 0, result.output
    assert "created" in result.output.lower()


def test_pipeline_create_composite_with_chain_flag(init_project) -> None:
    """Providing --chain-pipelines skips composite wizard prompt."""
    runner = init_project
    result = runner.invoke(
        cli,
        [
            "pipeline", "create", "comp2",
            "--mode", "composite",
            "--chain-pipelines", "main",
        ],
        input="y\n",
    )
    assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# Pipeline update: various flags
# ---------------------------------------------------------------------------


def test_pipeline_update_no_updates(init_project) -> None:
    """Calling update without any flags shows error."""
    runner = init_project
    result = runner.invoke(cli, ["pipeline", "update", "main"])
    assert result.exit_code != 0


def test_pipeline_update_participants(init_project) -> None:
    """Update --participants replaces the participant list."""
    runner = init_project
    _create_agent("p1")
    result = runner.invoke(
        cli,
        ["pipeline", "update", "main", "--participants", "p1"],
    )
    assert result.exit_code == 0, result.output
    assert "updated" in result.output.lower()


def test_pipeline_update_add_participant(init_project) -> None:
    """Update --add-participant adds a single agent."""
    runner = init_project
    _create_agent("newag")
    result = runner.invoke(
        cli,
        ["pipeline", "update", "main", "--add-participant", "newag"],
    )
    assert result.exit_code == 0, result.output


def test_pipeline_update_remove_participant(init_project) -> None:
    """Update --remove-participant removes a single agent."""
    runner = init_project
    result = runner.invoke(
        cli,
        ["pipeline", "update", "main", "--remove-participant", "nonexistent"],
    )
    assert result.exit_code == 0, result.output


def test_pipeline_update_leader(init_project) -> None:
    """Update --leader changes the leader agent."""
    runner = init_project
    _create_agent("lead2", "leader")
    result = runner.invoke(
        cli,
        ["pipeline", "update", "main", "--leader", "lead2"],
    )
    assert result.exit_code == 0, result.output


def test_pipeline_update_mode(init_project) -> None:
    """Update --mode changes the coordination mode."""
    runner = init_project
    result = runner.invoke(
        cli,
        ["pipeline", "update", "main", "--mode", "deliberation"],
    )
    assert result.exit_code == 0, result.output


def test_pipeline_update_dry_run_shows_diff(init_project) -> None:
    """Dry run displays participants diff."""
    runner = init_project
    _create_agent("x1")
    result = runner.invoke(
        cli,
        [
            "pipeline", "update", "main",
            "--add-participant", "x1",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "dry run" in result.output.lower()
    assert "participants" in result.output.lower()


# ---------------------------------------------------------------------------
# Pipeline show
# ---------------------------------------------------------------------------


def test_pipeline_show_text(init_project) -> None:
    """Show in text format prints key: value lines."""
    runner = init_project
    result = runner.invoke(cli, ["pipeline", "show", "main"])
    assert result.exit_code == 0
    # Should have at least the 'name' field
    assert "name" in result.output.lower() or "main" in result.output.lower()


def test_pipeline_show_json(init_project) -> None:
    """Show in json format prints JSON."""
    runner = init_project
    result = runner.invoke(cli, ["pipeline", "show", "main", "--format", "json"])
    assert result.exit_code == 0
    assert "{" in result.output


def test_pipeline_show_not_found(init_project) -> None:
    """Show for nonexistent pipeline exits with error."""
    runner = init_project
    result = runner.invoke(cli, ["pipeline", "show", "nope"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Pipeline list: empty
# ---------------------------------------------------------------------------


def test_pipeline_list_empty(tmp_path, monkeypatch) -> None:
    """List with no pipelines prints informational message."""
    import yaml
    from click.testing import CliRunner
    from miniautogen.cli.config import CONFIG_FILENAME

    monkeypatch.chdir(tmp_path)
    config = {
        "project": {"name": "test"},
        "defaults": {"engine_profile": "default_api"},
        "engine_profiles": {
            "default_api": {"kind": "api", "provider": "litellm"},
        },
        "pipelines": {},
    }
    (tmp_path / CONFIG_FILENAME).write_text(yaml.dump(config))
    runner = CliRunner()
    result = runner.invoke(cli, ["pipeline", "list"])
    assert result.exit_code == 0
    assert "no pipeline" in result.output.lower()


# ---------------------------------------------------------------------------
# Edge cases: missing project config
# ---------------------------------------------------------------------------


def test_pipeline_create_no_project(tmp_path, monkeypatch) -> None:
    """Creating a pipeline outside a project fails."""
    from click.testing import CliRunner

    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["pipeline", "create", "x", "--mode", "workflow"],
        input="y\n",
    )
    assert result.exit_code != 0


def test_pipeline_create_value_error(init_project) -> None:
    """When create_pipeline raises ValueError, exit code is non-zero."""
    runner = init_project
    # Duplicate name triggers ValueError
    result = runner.invoke(
        cli,
        ["pipeline", "create", "main", "--mode", "workflow"],
        input="y\n",
    )
    assert result.exit_code != 0


def test_pipeline_update_nonexistent(init_project) -> None:
    """Updating a nonexistent pipeline exits with error."""
    runner = init_project
    result = runner.invoke(
        cli,
        ["pipeline", "update", "ghost", "--mode", "loop"],
    )
    assert result.exit_code != 0
