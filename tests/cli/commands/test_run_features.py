"""Tests for run command features: --input, --resume."""

from click.testing import CliRunner

from miniautogen.cli.main import cli


def _init_project(tmp_path, monkeypatch):
    """Helper: init a project and chdir into it."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    runner.invoke(cli, ["init", "proj"])
    monkeypatch.chdir(tmp_path / "proj")
    return runner


def test_run_with_input(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, [
        "run", "--input", "Analyze sales data",
    ])
    assert result.exit_code == 0, result.output
    assert "completed" in result.output.lower()


def test_run_with_input_file(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    input_file = tmp_path / "proj" / "input.txt"
    input_file.write_text("Process this data")
    result = runner.invoke(cli, [
        "run", "--input", f"@{input_file}",
    ])
    assert result.exit_code == 0, result.output


def test_run_with_input_file_not_found(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, [
        "run", "--input", "@nonexistent.txt",
    ])
    assert result.exit_code != 0


def test_run_with_resume_flag(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, [
        "run", "--resume", "run-abc123",
    ])
    # Should attempt to run (resume may fail gracefully)
    assert result.exit_code == 0, result.output
