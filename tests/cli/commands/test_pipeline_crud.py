"""Tests for pipeline CRUD CLI command group."""

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


def test_pipeline_create_silent(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, [
        "pipeline", "create", "etl",
        "--mode", "workflow",
        "--target", "pipelines.etl:build_pipeline",
    ], input="\n")
    assert result.exit_code == 0, result.output
    assert "created" in result.output.lower()

    cfg = yaml.safe_load((tmp_path / "proj" / "miniautogen.yaml").read_text())
    assert "etl" in cfg["pipelines"]
    assert cfg["pipelines"]["etl"]["mode"] == "workflow"


def test_pipeline_create_duplicate_fails(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    # "main" already exists from init
    result = runner.invoke(cli, [
        "pipeline", "create", "main",
        "--mode", "workflow",
        "--participants", "",
    ])
    assert result.exit_code != 0


def test_pipeline_list(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, ["pipeline", "list"])
    assert result.exit_code == 0
    assert "main" in result.output


def test_pipeline_list_json(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, ["pipeline", "list", "--format", "json"])
    assert result.exit_code == 0
    assert '"name"' in result.output


def test_pipeline_show(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, ["pipeline", "show", "main"])
    assert result.exit_code == 0
    assert "target:" in result.output.lower() or "main" in result.output.lower()


def test_pipeline_show_json(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, ["pipeline", "show", "main", "--format", "json"])
    assert result.exit_code == 0
    assert '"name"' in result.output


def test_pipeline_show_not_found(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, ["pipeline", "show", "nonexistent"])
    assert result.exit_code != 0


def test_pipeline_update(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    # First create a pipeline with mode
    runner.invoke(cli, [
        "pipeline", "create", "etl",
        "--mode", "workflow",
        "--target", "pipelines.etl:build_pipeline",
    ], input="\n")
    result = runner.invoke(cli, [
        "pipeline", "update", "etl",
        "--max-rounds", "5",
    ])
    assert result.exit_code == 0
    assert "updated" in result.output.lower()


def test_pipeline_update_dry_run(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    runner.invoke(cli, [
        "pipeline", "create", "etl",
        "--mode", "workflow",
        "--target", "pipelines.etl:build_pipeline",
    ], input="\n")
    result = runner.invoke(cli, [
        "pipeline", "update", "etl",
        "--mode", "deliberation",
        "--dry-run",
    ])
    assert result.exit_code == 0
    assert "dry run" in result.output.lower()


def test_pipeline_update_not_found(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, [
        "pipeline", "update", "nonexistent",
        "--mode", "workflow",
    ])
    assert result.exit_code != 0
