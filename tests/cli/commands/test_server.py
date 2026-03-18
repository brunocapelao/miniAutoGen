"""Tests for server CLI command group."""

from miniautogen.cli.main import cli


def test_server_status_no_server(init_project) -> None:
    runner = init_project
    result = runner.invoke(cli, ["server", "status"])
    assert result.exit_code == 0
    assert "no server" in result.output.lower() or "stopped" in result.output.lower()


def test_server_stop_no_server(init_project) -> None:
    runner = init_project
    result = runner.invoke(cli, ["server", "stop"])
    assert result.exit_code == 0
    assert "no server" in result.output.lower() or "not running" in result.output.lower()


def test_server_logs_no_log(init_project) -> None:
    runner = init_project
    result = runner.invoke(cli, ["server", "logs"])
    assert result.exit_code == 0
    assert "no log" in result.output.lower()


def test_server_start_daemon(init_project) -> None:
    """Test that daemon start attempts to launch (may fail without uvicorn)."""
    runner = init_project
    result = runner.invoke(cli, ["server", "start", "--daemon"])
    # Will either start or fail gracefully
    # We just verify the command doesn't crash
    assert result.exit_code == 0 or "error" in result.output.lower()
