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


def _portfile(project_root: Path) -> Path:
    d = project_root / ".miniautogen"
    d.mkdir(parents=True, exist_ok=True)
    return d / "server.port"


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


def _read_port(project_root: Path) -> int:
    """Read the port the server was started on."""
    pf = _portfile(project_root)
    if pf.is_file():
        try:
            return int(pf.read_text().strip())
        except (ValueError, OSError):
            pass
    return 8080


def start_server(
    project_root: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8080,
    daemon: bool = False,
    timeout: int | None = None,
    max_concurrency: int | None = None,
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

    # Build uvicorn command
    cmd = [
        sys.executable, "-m", "uvicorn",
        "miniautogen.gateway:app",
        "--host", host,
        "--port", str(port),
    ]
    if timeout is not None:
        cmd.extend(["--timeout-keep-alive", str(timeout)])
    if max_concurrency is not None:
        cmd.extend(["--limit-concurrency", str(max_concurrency)])

    if daemon:
        log_path = _logfile(project_root)
        log_fd = log_path.open("a")
        proc = subprocess.Popen(
            cmd,
            stdout=log_fd,
            stderr=log_fd,
            start_new_session=True,
            cwd=str(project_root),
        )
        _pidfile(project_root).write_text(str(proc.pid))
        _portfile(project_root).write_text(str(port))
        return {
            "status": "started",
            "pid": proc.pid,
            "host": host,
            "port": port,
            "mode": "daemon",
            "message": f"Server started in daemon mode (PID {proc.pid})",
        }
    else:
        # Foreground mode — return info before blocking
        return {
            "status": "starting",
            "host": host,
            "port": port,
            "mode": "foreground",
            "cmd": cmd,
            "message": f"Starting server on {host}:{port} (foreground)...",
        }


def stop_server(
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
    _portfile(project_root).unlink(missing_ok=True)
    return {"status": "stopped", "pid": pid, "message": f"Server stopped (PID {pid})."}


def server_status(
    project_root: Path,
) -> dict[str, Any]:
    """Check the gateway server status.

    Returns one of 4 states:
    - running: process active, health check OK
    - degraded: process active, health check failing
    - unreachable: PID file exists, process not responding to signals
    - stopped: no process active
    """
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

    port = _read_port(project_root)

    # Try health check
    import urllib.error
    import urllib.request

    try:
        url = f"http://127.0.0.1:{port}/health"
        req = urllib.request.Request(url, method="GET")
        urllib.request.urlopen(req, timeout=2)
        return {
            "status": "running",
            "pid": pid,
            "port": port,
            "message": f"Server running (PID {pid}), health check OK.",
        }
    except urllib.error.URLError:
        # Process alive but HTTP not responding — unreachable
        return {
            "status": "unreachable",
            "pid": pid,
            "port": port,
            "message": f"Server process active (PID {pid}) but not responding on port {port}.",
        }
    except OSError:
        return {
            "status": "degraded",
            "pid": pid,
            "port": port,
            "message": f"Server process active (PID {pid}) but health check failed.",
        }


def server_logs(
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
