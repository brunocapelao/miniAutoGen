"""Tests for doctor CLI command."""

from click.testing import CliRunner

from miniautogen.cli.main import cli


def test_doctor_runs(tmp_path, monkeypatch) -> None:
    """Doctor command runs and checks environment."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["doctor"])
    # Should at least check python version
    assert "python" in result.output.lower()


def test_doctor_json(tmp_path, monkeypatch) -> None:
    """Doctor command supports --format json."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["doctor", "--format", "json"])
    assert '"category"' in result.output
    assert '"passed"' in result.output


def test_doctor_checks_dependencies(tmp_path, monkeypatch) -> None:
    """Doctor checks for required dependencies."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["doctor"])
    assert "click" in result.output.lower()
    assert "pydantic" in result.output.lower()
