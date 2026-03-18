"""Tests for miniautogen.cli.services.server_ops — targeting ~95% coverage."""

from __future__ import annotations

import os
import signal
import subprocess
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from miniautogen.cli.services.server_ops import (
    _pidfile,
    _portfile,
    _read_pid,
    _read_port,
    server_logs,
    server_status,
    start_server,
    stop_server,
)


# ---------------------------------------------------------------------------
# Helper: write a pidfile with optional port
# ---------------------------------------------------------------------------

def _write_pid(project_root: Path, pid: int) -> None:
    d = project_root / ".miniautogen"
    d.mkdir(parents=True, exist_ok=True)
    (d / "server.pid").write_text(str(pid))


def _write_port(project_root: Path, port: int) -> None:
    d = project_root / ".miniautogen"
    d.mkdir(parents=True, exist_ok=True)
    (d / "server.port").write_text(str(port))


def _write_log(project_root: Path, content: str) -> None:
    d = project_root / ".miniautogen"
    d.mkdir(parents=True, exist_ok=True)
    (d / "server.log").write_text(content)


# ===========================================================================
# _read_pid
# ===========================================================================


class TestReadPid:
    def test_missing_pidfile(self, tmp_path: Path) -> None:
        assert _read_pid(tmp_path) is None

    def test_valid_pid_alive(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_pid(tmp_path, 12345)
        monkeypatch.setattr(os, "kill", lambda pid, sig: None)  # process alive
        assert _read_pid(tmp_path) == 12345

    def test_stale_pid_dead_process(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_pid(tmp_path, 99999)

        def fake_kill(pid: int, sig: int) -> None:
            raise OSError("No such process")

        monkeypatch.setattr(os, "kill", fake_kill)
        result = _read_pid(tmp_path)
        assert result is None
        # pidfile should have been cleaned up
        assert not (tmp_path / ".miniautogen" / "server.pid").exists()

    def test_corrupt_pidfile(self, tmp_path: Path) -> None:
        d = tmp_path / ".miniautogen"
        d.mkdir(parents=True, exist_ok=True)
        (d / "server.pid").write_text("not-a-number")
        assert _read_pid(tmp_path) is None


# ===========================================================================
# _read_port
# ===========================================================================


class TestReadPort:
    def test_missing_portfile_returns_default(self, tmp_path: Path) -> None:
        assert _read_port(tmp_path) == 8080

    def test_valid_portfile(self, tmp_path: Path) -> None:
        _write_port(tmp_path, 9090)
        assert _read_port(tmp_path) == 9090

    def test_corrupt_portfile_returns_default(self, tmp_path: Path) -> None:
        d = tmp_path / ".miniautogen"
        d.mkdir(parents=True, exist_ok=True)
        (d / "server.port").write_text("garbage")
        assert _read_port(tmp_path) == 8080


# ===========================================================================
# start_server
# ===========================================================================


class TestStartServer:
    def test_already_running(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_pid(tmp_path, 11111)
        monkeypatch.setattr(os, "kill", lambda pid, sig: None)
        result = start_server(tmp_path)
        assert result["status"] == "already_running"
        assert result["pid"] == 11111

    def test_foreground_mode(self, tmp_path: Path) -> None:
        result = start_server(tmp_path, host="0.0.0.0", port=9000)
        assert result["status"] == "starting"
        assert result["mode"] == "foreground"
        assert result["host"] == "0.0.0.0"
        assert result["port"] == 9000
        assert "cmd" in result

    def test_daemon_mode(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_proc = MagicMock()
        mock_proc.pid = 42

        monkeypatch.setattr(
            subprocess, "Popen", lambda *a, **kw: mock_proc
        )

        result = start_server(tmp_path, port=7070, daemon=True)
        assert result["status"] == "started"
        assert result["pid"] == 42
        assert result["mode"] == "daemon"
        assert result["port"] == 7070
        # pidfile and portfile should be written
        assert (tmp_path / ".miniautogen" / "server.pid").read_text() == "42"
        assert (tmp_path / ".miniautogen" / "server.port").read_text() == "7070"

    def test_timeout_and_concurrency_flags(self, tmp_path: Path) -> None:
        """Foreground mode with timeout and max_concurrency appends correct flags."""
        result = start_server(tmp_path, timeout=30, max_concurrency=10)
        cmd = result["cmd"]
        assert "--timeout-keep-alive" in cmd
        assert "30" in cmd
        assert "--limit-concurrency" in cmd
        assert "10" in cmd


# ===========================================================================
# stop_server
# ===========================================================================


class TestStopServer:
    def test_no_server_running(self, tmp_path: Path) -> None:
        result = stop_server(tmp_path)
        assert result["status"] == "stopped"
        assert "No server" in result["message"]

    def test_stop_running_server(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_pid(tmp_path, 55555)
        _write_port(tmp_path, 8080)

        kill_calls: list[tuple[int, int]] = []

        def fake_kill(pid: int, sig: int) -> None:
            kill_calls.append((pid, sig))

        monkeypatch.setattr(os, "kill", fake_kill)

        result = stop_server(tmp_path)
        assert result["status"] == "stopped"
        assert result["pid"] == 55555
        # First call: signal 0 (alive check from _read_pid), second: SIGTERM
        assert (55555, signal.SIGTERM) in kill_calls
        # pidfile and portfile should be cleaned
        assert not (tmp_path / ".miniautogen" / "server.pid").exists()
        assert not (tmp_path / ".miniautogen" / "server.port").exists()

    def test_stop_server_kill_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_pid(tmp_path, 77777)

        call_count = 0

        def fake_kill(pid: int, sig: int) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # _read_pid alive check succeeds
                return
            # SIGTERM fails
            raise OSError("Operation not permitted")

        monkeypatch.setattr(os, "kill", fake_kill)

        result = stop_server(tmp_path)
        assert result["status"] == "error"
        assert "Failed to stop" in result["message"]


# ===========================================================================
# server_status
# ===========================================================================


class TestServerStatus:
    def test_stopped_no_pidfile(self, tmp_path: Path) -> None:
        result = server_status(tmp_path)
        assert result["status"] == "stopped"

    def test_stopped_corrupt_pidfile(self, tmp_path: Path) -> None:
        d = tmp_path / ".miniautogen"
        d.mkdir(parents=True, exist_ok=True)
        (d / "server.pid").write_text("not-a-number")
        result = server_status(tmp_path)
        assert result["status"] == "stopped"

    def test_stopped_stale_pid(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_pid(tmp_path, 99998)

        def fake_kill(pid: int, sig: int) -> None:
            raise OSError("No such process")

        monkeypatch.setattr(os, "kill", fake_kill)

        result = server_status(tmp_path)
        assert result["status"] == "stopped"
        assert "stale" in result["message"].lower()
        assert not (tmp_path / ".miniautogen" / "server.pid").exists()

    def test_running_health_ok(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_pid(tmp_path, 11111)
        _write_port(tmp_path, 8080)

        monkeypatch.setattr(os, "kill", lambda pid, sig: None)

        mock_response = MagicMock()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        monkeypatch.setattr(
            "urllib.request.urlopen", lambda *a, **kw: mock_response
        )

        result = server_status(tmp_path)
        assert result["status"] == "running"
        assert result["pid"] == 11111
        assert result["port"] == 8080

    def test_unreachable_url_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_pid(tmp_path, 22222)
        _write_port(tmp_path, 9090)

        monkeypatch.setattr(os, "kill", lambda pid, sig: None)
        monkeypatch.setattr(
            "urllib.request.urlopen",
            lambda *a, **kw: (_ for _ in ()).throw(
                urllib.error.URLError("Connection refused")
            ),
        )

        result = server_status(tmp_path)
        assert result["status"] == "unreachable"
        assert result["pid"] == 22222
        assert result["port"] == 9090

    def test_degraded_os_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_pid(tmp_path, 33333)
        _write_port(tmp_path, 7070)

        monkeypatch.setattr(os, "kill", lambda pid, sig: None)
        monkeypatch.setattr(
            "urllib.request.urlopen",
            lambda *a, **kw: (_ for _ in ()).throw(OSError("network down")),
        )

        result = server_status(tmp_path)
        assert result["status"] == "degraded"
        assert result["pid"] == 33333
        assert result["port"] == 7070


# ===========================================================================
# server_logs
# ===========================================================================


class TestServerLogs:
    def test_no_log_file(self, tmp_path: Path) -> None:
        result = server_logs(tmp_path)
        assert result == "(no log file found)"

    def test_log_file_with_content(self, tmp_path: Path) -> None:
        _write_log(tmp_path, "line1\nline2\nline3\n")
        result = server_logs(tmp_path, lines=50)
        assert "line1" in result
        assert "line2" in result
        assert "line3" in result

    def test_log_file_tail_limit(self, tmp_path: Path) -> None:
        """Only the last N lines should be returned."""
        content = "\n".join(f"line{i}" for i in range(100)) + "\n"
        _write_log(tmp_path, content)
        result = server_logs(tmp_path, lines=5)
        lines = result.split("\n")
        assert len(lines) == 5
        assert "line99" in lines[-1]
        assert "line95" in lines[0]

    def test_log_file_empty(self, tmp_path: Path) -> None:
        _write_log(tmp_path, "")
        result = server_logs(tmp_path, lines=10)
        assert result == ""
