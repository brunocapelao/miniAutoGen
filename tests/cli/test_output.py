"""Tests for CLI output formatting."""

import click
from click.testing import CliRunner

from miniautogen.cli.output import (
    echo_error,
    echo_info,
    echo_json,
    echo_success,
    echo_table,
    echo_warning,
)


def _capture(func, *args):
    @click.command()
    def cmd():
        func(*args)
    runner = CliRunner()
    return runner.invoke(cmd)


def test_echo_success() -> None:
    result = _capture(echo_success, "done")
    assert "done" in result.output


def test_echo_error() -> None:
    result = _capture(echo_error, "fail")
    # error goes to stderr, but CliRunner mixes them
    assert result.exit_code == 0


def test_echo_info() -> None:
    result = _capture(echo_info, "info msg")
    assert "info msg" in result.output


def test_echo_warning() -> None:
    result = _capture(echo_warning, "warn msg")
    assert "warn msg" in result.output


def test_echo_json() -> None:
    result = _capture(echo_json, {"key": "value"})
    assert '"key": "value"' in result.output


def test_echo_table() -> None:
    result = _capture(
        echo_table,
        ["Name", "Status"],
        [["agent1", "ok"], ["agent2", "fail"]],
    )
    assert "Name" in result.output
    assert "agent1" in result.output
    assert "agent2" in result.output


def test_echo_table_empty() -> None:
    result = _capture(echo_table, ["A"], [])
    assert "no data" in result.output
