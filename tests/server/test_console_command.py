"""Tests for --console flag on the run command and the console subcommand."""

from __future__ import annotations

from click.testing import CliRunner

from miniautogen.cli.main import cli


def test_run_console_flag_exists():
    """The --console flag is accepted by the run command."""
    runner = CliRunner()
    result = runner.invoke(cli, ["run", "--help"])
    assert "--console" in result.output


def test_run_console_port_flag_exists():
    """The --port flag is accepted alongside --console."""
    runner = CliRunner()
    result = runner.invoke(cli, ["run", "--help"])
    assert "--port" in result.output


def test_console_command_exists():
    """The 'console' subcommand is registered."""
    runner = CliRunner()
    result = runner.invoke(cli, ["console", "--help"])
    assert result.exit_code == 0
    assert "--port" in result.output
    assert "--workspace" in result.output
