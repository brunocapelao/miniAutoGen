"""Tests for the `miniautogen dash` CLI command."""

from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from miniautogen.cli.main import cli


def test_dash_command_exists() -> None:
    """The dash command must be registered."""
    runner = CliRunner()
    result = runner.invoke(cli, ["dash", "--help"])
    assert result.exit_code == 0
    assert "Launch the TUI dashboard" in result.output or "dash" in result.output


def test_dash_command_without_textual_shows_error() -> None:
    """If textual is not installed, show a helpful error."""
    runner = CliRunner()
    with patch(
        "miniautogen.cli.commands.dash._check_textual_available",
        return_value=False,
    ):
        result = runner.invoke(cli, ["dash"])
        assert result.exit_code != 0 or "tui" in result.output.lower()
