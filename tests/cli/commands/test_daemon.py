"""Tests for daemon CLI commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from miniautogen.cli.main import cli


_MOCK_CONFIG = patch(
    "miniautogen.cli.commands.daemon.require_project_config",
    return_value=("/tmp/project", MagicMock()),
)


# ------------------------------------------------------------------
# Help
# ------------------------------------------------------------------


def test_daemon_help_lists_all_subcommands():
    runner = CliRunner()
    result = runner.invoke(cli, ["daemon", "--help"])
    assert result.exit_code == 0
    for cmd in ["start", "stop", "restart", "status", "logs"]:
        assert cmd in result.output


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------


def test_daemon_status_stopped():
    runner = CliRunner()
    with _MOCK_CONFIG:
        with patch(
            "miniautogen.cli.services.server_ops.server_status",
            return_value={"status": "stopped", "message": "No server running."},
        ):
            result = runner.invoke(cli, ["daemon", "status"])
    assert result.exit_code == 0
    assert "stopped" in result.output.lower()


def test_daemon_status_running():
    runner = CliRunner()
    with _MOCK_CONFIG:
        with patch(
            "miniautogen.cli.services.server_ops.server_status",
            return_value={
                "status": "running",
                "pid": 1234,
                "port": 8080,
                "message": "Server running.",
            },
        ):
            result = runner.invoke(cli, ["daemon", "status"])
    assert result.exit_code == 0
    assert "running" in result.output.lower()
    assert "1234" in result.output
    assert "8080" in result.output


def test_daemon_status_json():
    runner = CliRunner()
    with _MOCK_CONFIG:
        with patch(
            "miniautogen.cli.services.server_ops.server_status",
            return_value={
                "status": "running",
                "pid": 1234,
                "port": 8080,
                "message": "Server running.",
            },
        ):
            result = runner.invoke(cli, ["daemon", "status", "--format", "json"])
    assert result.exit_code == 0
    assert '"status"' in result.output
    assert '"running"' in result.output


# ------------------------------------------------------------------
# Start
# ------------------------------------------------------------------


def test_daemon_start_success():
    runner = CliRunner()
    with _MOCK_CONFIG:
        with patch(
            "miniautogen.cli.services.server_ops.start_server",
            return_value={
                "status": "started",
                "pid": 5678,
                "host": "127.0.0.1",
                "port": 8080,
                "mode": "daemon",
                "message": "Server started in daemon mode (PID 5678)",
            },
        ):
            result = runner.invoke(cli, ["daemon", "start"])
    assert result.exit_code == 0
    assert "started" in result.output.lower()


def test_daemon_start_already_running():
    runner = CliRunner()
    with _MOCK_CONFIG:
        with patch(
            "miniautogen.cli.services.server_ops.start_server",
            return_value={
                "status": "already_running",
                "pid": 1111,
                "message": "Server already running (PID 1111)",
            },
        ):
            result = runner.invoke(cli, ["daemon", "start"])
    assert result.exit_code == 0
    assert "already running" in result.output.lower()


def test_daemon_start_json():
    runner = CliRunner()
    with _MOCK_CONFIG:
        with patch(
            "miniautogen.cli.services.server_ops.start_server",
            return_value={
                "status": "started",
                "pid": 5678,
                "host": "127.0.0.1",
                "port": 8080,
                "mode": "daemon",
                "message": "Server started in daemon mode (PID 5678)",
            },
        ):
            result = runner.invoke(cli, ["daemon", "start", "--format", "json"])
    assert result.exit_code == 0
    assert '"started"' in result.output


def test_daemon_start_error():
    runner = CliRunner()
    with _MOCK_CONFIG:
        with patch(
            "miniautogen.cli.services.server_ops.start_server",
            side_effect=RuntimeError("bind failed"),
        ):
            result = runner.invoke(cli, ["daemon", "start"])
    assert result.exit_code == 1
    assert "failed" in result.output.lower()


# ------------------------------------------------------------------
# Stop
# ------------------------------------------------------------------


def test_daemon_stop_success():
    runner = CliRunner()
    with _MOCK_CONFIG:
        with patch(
            "miniautogen.cli.services.server_ops.stop_server",
            return_value={
                "status": "stopped",
                "pid": 1234,
                "message": "Server stopped (PID 1234).",
            },
        ):
            result = runner.invoke(cli, ["daemon", "stop"])
    assert result.exit_code == 0
    assert "stopped" in result.output.lower()


def test_daemon_stop_not_running():
    runner = CliRunner()
    with _MOCK_CONFIG:
        with patch(
            "miniautogen.cli.services.server_ops.stop_server",
            return_value={"status": "stopped", "message": "No server running."},
        ):
            result = runner.invoke(cli, ["daemon", "stop"])
    assert result.exit_code == 0
    assert "no server running" in result.output.lower()


# ------------------------------------------------------------------
# Restart
# ------------------------------------------------------------------


def test_daemon_restart_success():
    runner = CliRunner()
    with _MOCK_CONFIG:
        with patch(
            "miniautogen.cli.services.server_ops.stop_server",
            return_value={"status": "stopped", "pid": 1234, "message": "Stopped."},
        ):
            with patch(
                "miniautogen.cli.services.server_ops.start_server",
                return_value={
                    "status": "started",
                    "pid": 9999,
                    "host": "127.0.0.1",
                    "port": 8080,
                    "mode": "daemon",
                    "message": "Server started in daemon mode (PID 9999)",
                },
            ):
                result = runner.invoke(cli, ["daemon", "restart"])
    assert result.exit_code == 0
    assert "restarted" in result.output.lower()


# ------------------------------------------------------------------
# Logs
# ------------------------------------------------------------------


def test_daemon_logs_default():
    runner = CliRunner()
    with _MOCK_CONFIG:
        with patch(
            "miniautogen.cli.services.server_ops.server_logs",
            return_value="line1\nline2\nline3",
        ):
            result = runner.invoke(cli, ["daemon", "logs"])
    assert result.exit_code == 0
    assert "line1" in result.output
    assert "line3" in result.output


def test_daemon_logs_custom_lines():
    runner = CliRunner()
    with _MOCK_CONFIG:
        with patch(
            "miniautogen.cli.services.server_ops.server_logs",
            return_value="log output",
        ) as mock_logs:
            result = runner.invoke(cli, ["daemon", "logs", "-n", "10"])
    assert result.exit_code == 0
    mock_logs.assert_called_once_with("/tmp/project", lines=10)


def test_daemon_logs_no_file():
    runner = CliRunner()
    with _MOCK_CONFIG:
        with patch(
            "miniautogen.cli.services.server_ops.server_logs",
            return_value="(no log file found)",
        ):
            result = runner.invoke(cli, ["daemon", "logs"])
    assert result.exit_code == 0
    assert "no log file found" in result.output
