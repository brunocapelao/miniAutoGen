"""Tests for completions CLI command — bash, zsh, fish shells and error handling."""

from __future__ import annotations

from unittest.mock import patch, MagicMock
import subprocess

from click.testing import CliRunner

from miniautogen.cli.main import cli


def test_completions_bash_with_output() -> None:
    """Completions for bash prints subprocess stdout when available."""
    fake_result = MagicMock()
    fake_result.stdout = "# bash completion script\ncomplete -F ..."
    fake_result.returncode = 0

    with patch("subprocess.run", return_value=fake_result):
        runner = CliRunner()
        result = runner.invoke(cli, ["completions", "bash"])

    assert result.exit_code == 0, result.output
    assert "bash completion script" in result.output


def test_completions_zsh_with_output() -> None:
    """Completions for zsh prints subprocess stdout when available."""
    fake_result = MagicMock()
    fake_result.stdout = "# zsh completion script\ncompdef ..."
    fake_result.returncode = 0

    with patch("subprocess.run", return_value=fake_result):
        runner = CliRunner()
        result = runner.invoke(cli, ["completions", "zsh"])

    assert result.exit_code == 0, result.output
    assert "zsh completion script" in result.output


def test_completions_fish_with_output() -> None:
    """Completions for fish prints subprocess stdout when available."""
    fake_result = MagicMock()
    fake_result.stdout = "# fish completion\ncomplete -c miniautogen"
    fake_result.returncode = 0

    with patch("subprocess.run", return_value=fake_result):
        runner = CliRunner()
        result = runner.invoke(cli, ["completions", "fish"])

    assert result.exit_code == 0, result.output
    assert "fish completion" in result.output


def test_completions_bash_empty_output_shows_instructions() -> None:
    """When subprocess produces no output, print installation instructions."""
    fake_result = MagicMock()
    fake_result.stdout = ""
    fake_result.returncode = 0

    with patch("subprocess.run", return_value=fake_result):
        runner = CliRunner()
        result = runner.invoke(cli, ["completions", "bash"])

    assert result.exit_code == 0, result.output
    assert "~/.bashrc" in result.output


def test_completions_zsh_empty_output_shows_instructions() -> None:
    """When subprocess produces no output for zsh, print zsh instructions."""
    fake_result = MagicMock()
    fake_result.stdout = ""
    fake_result.returncode = 0

    with patch("subprocess.run", return_value=fake_result):
        runner = CliRunner()
        result = runner.invoke(cli, ["completions", "zsh"])

    assert result.exit_code == 0, result.output
    assert "~/.zshrc" in result.output


def test_completions_fish_empty_output_shows_instructions() -> None:
    """When subprocess produces no output for fish, print fish instructions."""
    fake_result = MagicMock()
    fake_result.stdout = ""
    fake_result.returncode = 0

    with patch("subprocess.run", return_value=fake_result):
        runner = CliRunner()
        result = runner.invoke(cli, ["completions", "fish"])

    assert result.exit_code == 0, result.output
    assert "fish" in result.output.lower()


def test_completions_subprocess_exception_shows_instructions() -> None:
    """When subprocess.run raises an exception, fall back to instructions."""
    with patch("subprocess.run", side_effect=OSError("command not found")):
        runner = CliRunner()
        result = runner.invoke(cli, ["completions", "bash"])

    assert result.exit_code == 0, result.output
    assert "~/.bashrc" in result.output


def test_completions_invalid_shell() -> None:
    """Passing an invalid shell name fails with usage error."""
    runner = CliRunner()
    result = runner.invoke(cli, ["completions", "powershell"])
    assert result.exit_code != 0
    assert "invalid" in result.output.lower() or "error" in result.output.lower() or "Usage" in result.output
