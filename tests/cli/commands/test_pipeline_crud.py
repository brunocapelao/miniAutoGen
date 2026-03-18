"""Tests for pipeline CRUD CLI command group."""

import yaml
from pathlib import Path

from miniautogen.cli.main import cli


def test_pipeline_create_silent(init_project) -> None:
    runner = init_project
    result = runner.invoke(cli, [
        "pipeline", "create", "etl",
        "--mode", "workflow",
        "--target", "pipelines.etl:build_pipeline",
    ], input="\ny\n")
    assert result.exit_code == 0, result.output
    assert "created" in result.output.lower()

    cfg = yaml.safe_load((Path.cwd() / "miniautogen.yaml").read_text())
    assert "etl" in cfg["pipelines"]
    assert cfg["pipelines"]["etl"]["mode"] == "workflow"


def test_pipeline_create_cancelled(init_project) -> None:
    """Test pipeline creation cancellation."""
    runner = init_project
    result = runner.invoke(cli, [
        "pipeline", "create", "etl",
        "--mode", "workflow",
        "--target", "pipelines.etl:build_pipeline",
    ], input="\nn\n")
    assert result.exit_code == 0
    assert "cancelled" in result.output.lower()


def test_pipeline_create_duplicate_fails(init_project) -> None:
    runner = init_project
    # "main" already exists from init
    result = runner.invoke(cli, [
        "pipeline", "create", "main",
        "--mode", "workflow",
        "--participants", "",
    ], input="y\n")
    assert result.exit_code != 0


def test_pipeline_list(init_project) -> None:
    runner = init_project
    result = runner.invoke(cli, ["pipeline", "list"])
    assert result.exit_code == 0
    assert "main" in result.output


def test_pipeline_list_json(init_project) -> None:
    runner = init_project
    result = runner.invoke(cli, ["pipeline", "list", "--format", "json"])
    assert result.exit_code == 0
    assert '"name"' in result.output


def test_pipeline_show(init_project) -> None:
    runner = init_project
    result = runner.invoke(cli, ["pipeline", "show", "main"])
    assert result.exit_code == 0
    assert "target:" in result.output.lower() or "main" in result.output.lower()


def test_pipeline_show_json(init_project) -> None:
    runner = init_project
    result = runner.invoke(cli, ["pipeline", "show", "main", "--format", "json"])
    assert result.exit_code == 0
    assert '"name"' in result.output


def test_pipeline_show_not_found(init_project) -> None:
    runner = init_project
    result = runner.invoke(cli, ["pipeline", "show", "nonexistent"])
    assert result.exit_code != 0


def test_pipeline_update(init_project) -> None:
    runner = init_project
    # First create a pipeline with mode
    runner.invoke(cli, [
        "pipeline", "create", "etl",
        "--mode", "workflow",
        "--target", "pipelines.etl:build_pipeline",
    ], input="\ny\n")
    result = runner.invoke(cli, [
        "pipeline", "update", "etl",
        "--max-rounds", "5",
    ])
    assert result.exit_code == 0
    assert "updated" in result.output.lower()


def test_pipeline_update_dry_run(init_project) -> None:
    runner = init_project
    runner.invoke(cli, [
        "pipeline", "create", "etl",
        "--mode", "workflow",
        "--target", "pipelines.etl:build_pipeline",
    ], input="\ny\n")
    result = runner.invoke(cli, [
        "pipeline", "update", "etl",
        "--mode", "deliberation",
        "--dry-run",
    ])
    assert result.exit_code == 0
    assert "dry run" in result.output.lower()


def test_pipeline_update_not_found(init_project) -> None:
    runner = init_project
    result = runner.invoke(cli, [
        "pipeline", "update", "nonexistent",
        "--mode", "workflow",
    ])
    assert result.exit_code != 0
