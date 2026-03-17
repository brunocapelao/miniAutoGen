"""Tests for server CLI command group."""

from click.testing import CliRunner

from miniautogen.cli.main import cli


def _init_project(tmp_path, monkeypatch):
    """Helper: init a project and chdir into it."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    runner.invoke(cli, ["init", "proj"])
    monkeypatch.chdir(tmp_path / "proj")
    return runner


def test_server_status_no_server(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, ["server", "status"])
    assert result.exit_code == 0
    assert "no server" in result.output.lower() or "stopped" in result.output.lower()


def test_server_stop_no_server(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, ["server", "stop"])
    assert result.exit_code == 0
    assert "no server" in result.output.lower() or "not running" in result.output.lower()


def test_server_logs_no_log(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, ["server", "logs"])
    assert result.exit_code == 0
    assert "no log" in result.output.lower()


def test_server_start_daemon(tmp_path, monkeypatch) -> None:
    """Test that daemon start attempts to launch (may fail without uvicorn)."""
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, ["server", "start", "--daemon"])
    # Will either start or fail gracefully
    # We just verify the command doesn't crash
    assert result.exit_code == 0 or "error" in result.output.lower()
