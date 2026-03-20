"""Tests for the 'flow' CLI command group (DA-9 rename from 'pipeline')."""

from __future__ import annotations

from miniautogen.cli.main import cli


def test_flow_list(init_project) -> None:
    """'flow list' should work like 'pipeline list'."""
    runner = init_project
    result = runner.invoke(cli, ["flow", "list"])
    assert result.exit_code == 0
    assert "main" in result.output


def test_flow_show(init_project) -> None:
    """'flow show main' should work."""
    runner = init_project
    result = runner.invoke(cli, ["flow", "show", "main"])
    assert result.exit_code == 0


def test_flow_create(init_project) -> None:
    """'flow create' should work."""
    runner = init_project
    result = runner.invoke(
        cli,
        ["flow", "create", "etl", "--mode", "workflow", "--target", "pipelines.etl:build_pipeline"],
        input="\ny\n",
    )
    assert result.exit_code == 0, result.output
    assert "created" in result.output.lower()


def test_pipeline_alias_still_works(init_project) -> None:
    """'pipeline list' should still work as a hidden alias."""
    runner = init_project
    result = runner.invoke(cli, ["pipeline", "list"])
    assert result.exit_code == 0
    assert "main" in result.output


def test_flow_help_uses_new_terminology(init_project) -> None:
    """'flow --help' should mention 'flow', not 'pipeline'."""
    runner = init_project
    result = runner.invoke(cli, ["flow", "--help"])
    assert result.exit_code == 0
    assert "flow" in result.output.lower()


def test_flow_delete_with_confirm(init_project) -> None:
    """'flow delete' should remove a flow after confirmation."""
    runner = init_project
    # First create a flow to delete
    result = runner.invoke(
        cli,
        ["flow", "create", "deleteme", "--mode", "workflow", "--target", "pipelines.deleteme:build_pipeline"],
        input="\ny\n",
    )
    assert result.exit_code == 0, result.output

    # Now delete it
    result = runner.invoke(cli, ["flow", "delete", "deleteme"], input="y\n")
    assert result.exit_code == 0, result.output
    assert "deleted" in result.output.lower()

    # Verify it's gone
    result = runner.invoke(cli, ["flow", "list"])
    assert "deleteme" not in result.output


def test_flow_delete_cancelled(init_project) -> None:
    """'flow delete' cancelled at prompt does not remove flow."""
    runner = init_project
    result = runner.invoke(
        cli,
        ["flow", "create", "keepme", "--mode", "workflow", "--target", "pipelines.keepme:build_pipeline"],
        input="\ny\n",
    )
    assert result.exit_code == 0, result.output

    result = runner.invoke(cli, ["flow", "delete", "keepme"], input="n\n")
    assert result.exit_code == 0
    assert "cancelled" in result.output.lower()

    # Verify it still exists
    result = runner.invoke(cli, ["flow", "list"])
    assert "keepme" in result.output


def test_flow_delete_yes_flag(init_project) -> None:
    """'flow delete --yes' skips confirmation."""
    runner = init_project
    result = runner.invoke(
        cli,
        ["flow", "create", "quickdel", "--mode", "workflow", "--target", "pipelines.quickdel:build_pipeline"],
        input="\ny\n",
    )
    assert result.exit_code == 0, result.output

    result = runner.invoke(cli, ["flow", "delete", "quickdel", "--yes"])
    assert result.exit_code == 0, result.output
    assert "deleted" in result.output.lower()


def test_flow_delete_nonexistent(init_project) -> None:
    """'flow delete' for nonexistent flow shows error."""
    runner = init_project
    result = runner.invoke(cli, ["flow", "delete", "nope", "--yes"])
    assert result.exit_code == 1
