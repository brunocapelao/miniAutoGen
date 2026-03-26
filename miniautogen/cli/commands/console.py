"""miniautogen console command — standalone web dashboard."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import click

from miniautogen.cli.output import echo_error, echo_info, echo_success, echo_warning

# Path to the console frontend source (relative to package root)
_CONSOLE_SRC = Path(__file__).resolve().parent.parent.parent.parent / "console"
_STATIC_DIR = Path(__file__).resolve().parent.parent / "server" / "static"


def _build_frontend() -> bool:
    """Build the Next.js frontend and copy to static dir.

    Returns True on success.
    """
    if not _CONSOLE_SRC.is_dir():
        echo_error(f"Console source not found at {_CONSOLE_SRC}")
        return False

    # Check if node_modules exist
    if not (_CONSOLE_SRC / "node_modules").is_dir():
        echo_info("Installing frontend dependencies...")
        result = subprocess.run(
            ["npm", "install"],
            cwd=str(_CONSOLE_SRC),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            echo_error(f"npm install failed: {result.stderr}")
            return False

    echo_info("Building frontend...")
    result = subprocess.run(
        ["npm", "run", "build"],
        cwd=str(_CONSOLE_SRC),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        echo_error(f"Frontend build failed: {result.stderr}")
        return False

    # Copy build output to static dir
    out_dir = _CONSOLE_SRC / "out"
    if not out_dir.is_dir():
        echo_error("Build output not found (console/out/)")
        return False

    # Clear and copy
    if _STATIC_DIR.is_dir():
        shutil.rmtree(_STATIC_DIR)
    shutil.copytree(out_dir, _STATIC_DIR)
    echo_success("Frontend built and deployed to server/static/")
    return True


def _is_frontend_built() -> bool:
    """Check if static dir has up-to-date content.

    Returns True only if the static dir exists with index.html AND
    is not stale (i.e., newer than the console/out/ build output).
    """
    index = _STATIC_DIR / "index.html"
    if not index.is_file():
        return False
    # Check if console/out/ exists and is newer (stale detection)
    out_dir = _CONSOLE_SRC / "out"
    if out_dir.is_dir():
        out_index = out_dir / "index.html"
        if out_index.is_file() and out_index.stat().st_mtime > index.stat().st_mtime:
            return False  # out/ is newer, need to re-copy
    return True


@click.command("console")
@click.option("--host", type=str, default="127.0.0.1", help="Host to bind to (default: 127.0.0.1).")
@click.option("--port", type=int, default=8080, help="Server port (default: 8080).")
@click.option(
    "--workspace",
    type=click.Path(exists=True, file_okay=False),
    default=".",
    help="Workspace directory (default: current directory).",
)
@click.option(
    "--db",
    type=str,
    default=None,
    envvar="MINIAUTOGEN_DB_URL",
    help="Database URL for persistent store (e.g. sqlite:///runs.db). Uses in-memory if omitted.",
)
@click.option(
    "--dev",
    is_flag=True,
    default=False,
    help="Dev mode: start backend API + Next.js dev server with hot reload.",
)
@click.option(
    "--no-build",
    is_flag=True,
    default=False,
    help="Skip frontend build (use existing static files).",
)
@click.option(
    "--no-open",
    is_flag=True,
    default=False,
    help="Don't open the browser automatically.",
)
def console_command(
    host: str,
    port: int,
    workspace: str,
    db: str | None,
    dev: bool,
    no_build: bool,
    no_open: bool,
) -> None:
    """Launch the MiniAutoGen Console dashboard.

    Starts a web dashboard for observing agents, flows, and run history.

    \b
    Production mode (default):
      Builds frontend, serves via FastAPI on a single port.
      miniautogen console --port 8080

    \b
    Dev mode (--dev):
      Starts FastAPI API on --port and Next.js dev server on port+1.
      miniautogen console --dev --port 8080
    """
    if host not in ("127.0.0.1", "localhost"):
        echo_warning(
            f"Binding to '{host}' exposes the server to the network. "
            "Set MINIAUTOGEN_API_KEY to enable authentication."
        )

    if dev:
        _run_dev_mode(host, port, workspace, db, no_open)
    else:
        _run_production_mode(host, port, workspace, db, no_build, no_open)


def _run_production_mode(
    host: str,
    port: int,
    workspace: str,
    db: str | None,
    no_build: bool,
    no_open: bool,
) -> None:
    """Build frontend + serve everything on one port."""
    import webbrowser

    import uvicorn

    from miniautogen.server.app import create_app
    from miniautogen.server.standalone_provider import StandaloneProvider
    from miniautogen.tui.data_provider import DashDataProvider

    # Build frontend if needed
    if not no_build and not _is_frontend_built():
        if not _build_frontend():
            echo_warning("Frontend build failed. API-only mode (no UI).")
    elif not no_build:
        echo_info("Frontend already built. Use --no-build to skip check.")

    path = Path(workspace).resolve()
    base_provider = DashDataProvider(path)
    run_store, event_store = _create_stores(db)

    provider = StandaloneProvider(
        base_provider=base_provider,
        run_store=run_store,
        event_store=event_store,
    )
    app = create_app(provider=provider, mode="standalone")

    url = f"http://{host}:{port}"
    echo_success(f"Console running at {url}")
    echo_info("Press Ctrl+C to stop.")
    if not no_open:
        webbrowser.open(url)

    uvicorn.run(app, host=host, port=port, log_level="info")


def _run_dev_mode(
    host: str,
    port: int,
    workspace: str,
    db: str | None,
    no_open: bool,
) -> None:
    """Start backend API + Next.js dev server in parallel."""
    import os
    import signal
    import webbrowser

    import uvicorn

    from miniautogen.server.app import create_app
    from miniautogen.server.standalone_provider import StandaloneProvider
    from miniautogen.tui.data_provider import DashDataProvider

    if not _CONSOLE_SRC.is_dir():
        echo_error(f"Console source not found at {_CONSOLE_SRC}")
        raise SystemExit(1)

    # Auto-install dependencies if needed
    if not (_CONSOLE_SRC / "node_modules").is_dir():
        echo_info("Installing frontend dependencies...")
        result = subprocess.run(
            ["npm", "install"],
            cwd=str(_CONSOLE_SRC),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            echo_error(f"npm install failed: {result.stderr}")
            raise SystemExit(1)
        echo_success("Dependencies installed.")

    path = Path(workspace).resolve()
    base_provider = DashDataProvider(path)
    run_store, event_store = _create_stores(db)

    provider = StandaloneProvider(
        base_provider=base_provider,
        run_store=run_store,
        event_store=event_store,
    )

    # Set MINIAUTOGEN_DEV to enable CORS for localhost:3000
    os.environ["MINIAUTOGEN_DEV"] = "1"
    app = create_app(provider=provider, mode="standalone")

    frontend_port = port + 1
    frontend_url = f"http://localhost:{frontend_port}"

    # Fork: child runs Next.js dev, parent runs uvicorn
    next_proc = subprocess.Popen(
        ["npm", "run", "dev", "--", "--port", str(frontend_port)],
        cwd=str(_CONSOLE_SRC),
        env={
            **os.environ,
            "NEXT_PUBLIC_API_URL": f"http://localhost:{port}/api/v1",
        },
    )

    echo_success(f"API server:  http://{host}:{port}")
    echo_success(f"Frontend:    {frontend_url}")
    echo_info("Press Ctrl+C to stop both.")

    if not no_open:
        # Small delay to let Next.js start
        import threading

        def _open_browser():
            import time
            time.sleep(3)
            webbrowser.open(frontend_url)

        threading.Thread(target=_open_browser, daemon=True).start()

    try:
        uvicorn.run(app, host=host, port=port, log_level="info")
    finally:
        echo_info("Stopping frontend dev server...")
        next_proc.terminate()
        try:
            next_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            next_proc.kill()


def _create_stores(db: str | None):
    """Create run/event stores based on --db flag."""
    if db:
        from miniautogen.cli.main import run_async
        from miniautogen.stores.sqlalchemy_event_store import SQLAlchemyEventStore
        from miniautogen.stores.sqlalchemy_run_store import SQLAlchemyRunStore

        run_store = SQLAlchemyRunStore(db)
        event_store = SQLAlchemyEventStore(db)
        run_async(run_store.init_db)
        run_async(event_store.init_db)
        # Mask credentials in log output
        from urllib.parse import urlparse

        parsed = urlparse(db)
        safe_url = db if not parsed.password else db.replace(f":{parsed.password}@", ":****@")
        echo_info(f"Using persistent store: {safe_url}")
    else:
        from miniautogen.stores.in_memory_event_store import InMemoryEventStore
        from miniautogen.stores.in_memory_run_store import InMemoryRunStore

        run_store = InMemoryRunStore()
        event_store = InMemoryEventStore()
        echo_info("Using in-memory store (no persistence)")

    return run_store, event_store
