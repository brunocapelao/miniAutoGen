"""Tests for the chat CLI command."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from click.testing import CliRunner

from miniautogen.cli.main import cli


def test_chat_help() -> None:
    """Chat command shows help text."""
    runner = CliRunner()
    result = runner.invoke(cli, ["chat", "--help"])
    assert result.exit_code == 0
    assert "Start an interactive chat session" in result.output


def _mock_session(agent_name: str = "coder") -> MagicMock:
    """Create a mock ChatSession."""
    session = MagicMock()
    session.agent_name = agent_name
    session.run_id = "chat-abc12345"
    session.is_closed = False
    session.history = []
    session.send = AsyncMock(return_value="Mock response")
    session.close = AsyncMock()
    session.clear_history = MagicMock()
    return session


def test_chat_quit(init_project: CliRunner) -> None:
    """/quit exits cleanly."""
    mock_session = _mock_session()

    with patch(
        "miniautogen.cli.commands.chat.run_async",
    ) as mock_run_async:
        # First call is ChatSession.create, rest are send/close
        mock_run_async.return_value = mock_session

        result = init_project.invoke(cli, ["chat"], input="/quit\n")

    assert result.exit_code == 0
    assert "Chat session ended" in result.output


def test_chat_send_and_quit(init_project: CliRunner) -> None:
    """Sends a message, gets a response, then quits."""
    mock_session = _mock_session()

    call_count = 0

    def side_effect(fn, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # ChatSession.create
            return mock_session
        if call_count == 2:
            # session.send
            return "Mock response"
        # session.close or others
        return None

    with patch(
        "miniautogen.cli.commands.chat.run_async",
        side_effect=side_effect,
    ):
        result = init_project.invoke(cli, ["chat"], input="Hello\n/quit\n")

    assert result.exit_code == 0
    assert "Mock response" in result.output
    assert "Chat session ended" in result.output


def test_chat_help_command(init_project: CliRunner) -> None:
    """/help shows available commands."""
    mock_session = _mock_session()

    with patch(
        "miniautogen.cli.commands.chat.run_async",
        return_value=mock_session,
    ):
        result = init_project.invoke(cli, ["chat"], input="/help\n/quit\n")

    assert result.exit_code == 0
    assert "/quit" in result.output
    assert "/clear" in result.output
    assert "/switch" in result.output


def test_chat_clear_command(init_project: CliRunner) -> None:
    """/clear clears history."""
    mock_session = _mock_session()

    with patch(
        "miniautogen.cli.commands.chat.run_async",
        return_value=mock_session,
    ):
        result = init_project.invoke(cli, ["chat"], input="/clear\n/quit\n")

    assert result.exit_code == 0
    assert "History cleared" in result.output
    mock_session.clear_history.assert_called_once()
