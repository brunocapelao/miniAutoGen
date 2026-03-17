"""Server/gateway management service for the CLI."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any


def _pidfile(project_root: Path) -> Path:
    d = project_root / ".miniautogen"
    d.mkdir(parents=True, exist_ok=True)
    return d / "server.pid"


def _logfile(project_root: Path) -> Path:
    d = project_root / ".miniautogen"
    d.mkdir(parents=True, exist_ok=True)
    return d / "server.log"


def _read_pid(project_root: Path) -> int | None:
    """Read PID from pidfile, returning None if stale or missing."""
    pf = _pidfile(project_root)
    if not pf.is_file():
        return None
    try:
        pid = int(pf.read_text().strip())
    except (ValueError, OSError):
        return None
    # Check if process is alive
    try:
        os.kill(pid, 0)
    except OSError:
        # Stale PID — clean up
        pf.unlink(missing_ok=True)
        return None
    return pid


async def start_server(
    project_root: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8080,
    daemon: bool = False,
) -> dict[str, Any]:
    """Start the gateway server.

    Returns status information about the started server.
    """
    existing_pid = _read_pid(project_root)
    if existing_pid is not None:
        return {
            "status": "already_running",
            "pid": existing_pid,
            "message": f"Server already running (PID {existing_pid})",
        }

    if daemon:
        log_path = _logfile(project_root)
        log_fd = log_path.open("a")
        proc = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn",
                "miniautogen.gateway:app",
                "--host", host,
                "--port", str(port),
            ],
            stdout=log_fd,
            stderr=log_fd,
            start_new_session=True,
            cwd=str(project_root),
        )
        _pidfile(project_root).write_text(str(proc.pid))
        return {
            "status": "started",
            "pid": proc.pid,
            "host": host,
            "port": port,
            "mode": "daemon",
            "message": f"Server started in daemon mode (PID {proc.pid})",
        }
    else:
        # Foreground mode — exec uvicorn in-process
        # This will block, so we return info before
        return {
            "status": "starting",
            "host": host,
            "port": port,
            "mode": "foreground",
            "message": f"Starting server on {host}:{port} (foreground)...",
        }


async def stop_server(
    project_root: Path,
) -> dict[str, Any]:
    """Stop the gateway daemon."""
    pid = _read_pid(project_root)
    if pid is None:
        return {"status": "stopped", "message": "No server running."}

    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as exc:
        return {"status": "error", "message": f"Failed to stop PID {pid}: {exc}"}

    _pidfile(project_root).unlink(missing_ok=True)
    return {"status": "stopped", "pid": pid, "message": f"Server stopped (PID {pid})."}


async def server_status(
    project_root: Path,
) -> dict[str, Any]:
    """Check the gateway server status."""
    pf = _pidfile(project_root)
    if not pf.is_file():
        return {"status": "stopped", "message": "No server running."}

    try:
        pid = int(pf.read_text().strip())
    except (ValueError, OSError):
        return {"status": "stopped", "message": "No server running."}

    # Check if process is alive
    try:
        os.kill(pid, 0)
    except OSError:
        pf.unlink(missing_ok=True)
        return {"status": "stopped", "message": "Server not running (stale PID cleaned)."}

    # Try health check
    import urllib.request
    import urllib.error

    try:
        url = "http://127.0.0.1:8080/health"
        req = urllib.request.Request(url, method="GET")
        urllib.request.urlopen(req, timeout=2)
        return {
            "status": "running",
            "pid": pid,
            "message": f"Server running (PID {pid}), health check OK.",
        }
    except (urllib.error.URLError, OSError):
        return {
            "status": "degraded",
            "pid": pid,
            "message": f"Server process active (PID {pid}) but health check failed.",
        }


async def server_logs(
    project_root: Path,
    lines: int = 50,
) -> str:
    """Read recent server logs."""
    log_path = _logfile(project_root)
    if not log_path.is_file():
        return "(no log file found)"

    content = log_path.read_text()
    all_lines = content.splitlines()
    return "\n".join(all_lines[-lines:])
