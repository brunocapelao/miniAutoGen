"""Tests for run command features: --input, --resume."""

from pathlib import Path

from miniautogen.cli.main import cli


def test_run_with_input(init_project) -> None:
    runner = init_project
    result = runner.invoke(cli, [
        "run", "--input", "Analyze sales data",
    ])
    assert result.exit_code == 0, result.output
    assert "completed" in result.output.lower()


def test_run_with_input_file(init_project) -> None:
    runner = init_project
    project_root = Path.cwd()
    input_file = project_root / "input.txt"
    input_file.write_text("Process this data")
    result = runner.invoke(cli, [
        "run", "--input", f"@{input_file}",
    ])
    assert result.exit_code == 0, result.output


def test_run_with_input_file_not_found(init_project) -> None:
    runner = init_project
    result = runner.invoke(cli, [
        "run", "--input", "@nonexistent.txt",
    ])
    assert result.exit_code != 0


def test_run_with_resume_flag(init_project) -> None:
    runner = init_project
    result = runner.invoke(cli, [
        "run", "--resume", "run-abc123",
    ])
    # Resume should fail explicitly when checkpoint store is not configured
    assert result.exit_code != 0
    assert "checkpoint" in result.output.lower() or "resume" in result.output.lower()
