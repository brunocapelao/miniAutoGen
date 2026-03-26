"""Tests for the send CLI command."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

from miniautogen.cli.main import cli


def test_send_no_message_no_stdin() -> None:
    """Error when no message is provided and stdin is a TTY."""
    runner = CliRunner()
    result = runner.invoke(cli, ["send"])
    assert result.exit_code != 0
    assert "No message provided" in result.output or "No message provided" in (result.stderr or "")


def test_send_with_message(init_project: CliRunner) -> None:
    """Happy path: sends a message and prints the response."""
    mock_result = {
        "agent": "coder",
        "message": "Hello",
        "response": "Hi there!",
        "run_id": "send-abc12345",
    }

    with patch(
        "miniautogen.cli.services.send_service.send_message",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        result = init_project.invoke(cli, ["send", "Hello"])

    assert result.exit_code == 0
    assert "Hi there!" in result.output


def test_send_json_format(init_project: CliRunner) -> None:
    """JSON format outputs a JSON dict with agent, message, response."""
    mock_result = {
        "agent": "coder",
        "message": "Hello",
        "response": "Hi there!",
        "run_id": "send-abc12345",
    }

    with patch(
        "miniautogen.cli.services.send_service.send_message",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        result = init_project.invoke(cli, ["send", "--format", "json", "Hello"])

    assert result.exit_code == 0
    assert '"agent"' in result.output
    assert '"response"' in result.output


def test_send_empty_message() -> None:
    """Error on empty message string."""
    runner = CliRunner()
    result = runner.invoke(cli, ["send", ""])
    assert result.exit_code != 0
    assert "No message provided" in result.output or "No message provided" in (result.stderr or "")
