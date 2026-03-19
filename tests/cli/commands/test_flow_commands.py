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
