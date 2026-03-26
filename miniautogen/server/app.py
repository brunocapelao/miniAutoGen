"""FastAPI application factory for MiniAutoGen Console."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from miniautogen.gateway.security import verify_api_key
from miniautogen.server.provider_protocol import ConsoleDataProvider
from miniautogen.server.rate_limit import create_console_limiter
from miniautogen.server.routes.agents import agents_router
from miniautogen.server.routes.config import config_router
from miniautogen.server.routes.engines import engines_router
from miniautogen.server.routes.flows import flows_router
from miniautogen.server.routes.runs import runs_router
from miniautogen.server.routes.workspace import workspace_router
from miniautogen.server.event_broadcaster import GlobalEventBroadcaster
from miniautogen.server.routes.events import events_router
from miniautogen.server.ws import WebSocketEventSink, global_events_router, ws_router

logger = logging.getLogger(__name__)


def create_app(
    *,
    provider: ConsoleDataProvider | None = None,
    workspace_path: str | Path | None = None,
    mode: Literal["embedded", "standalone"] = "embedded",
    api_key: str | None = None,
) -> FastAPI:
    """Create the Console Server FastAPI application."""
    if provider is None:
        from miniautogen.tui.data_provider import DashDataProvider

        path = Path(workspace_path or ".").resolve()
        provider = DashDataProvider(path)

    # Resolve API key: explicit parameter > env var > None (open access)
    resolved_key = api_key or os.getenv("MINIAUTOGEN_API_KEY")
    if resolved_key is None:
        logger.warning(
            "Console Server running WITHOUT authentication. "
            "Set MINIAUTOGEN_API_KEY or pass api_key to enable auth."
        )

    app = FastAPI(title="MiniAutoGen Console", version="0.1.0")

    # Store API key for verify_api_key dependency
    app.state.api_key = resolved_key

    # Rate limiting (fresh instance per app to avoid shared state in tests)
    limiter = create_console_limiter()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Custom error handler: return ErrorResponse at top level, not nested in "detail"
    @app.exception_handler(HTTPException)
    async def custom_http_exception_handler(request, exc):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)

    # WebSocket (embedded mode only — live event streaming)
    event_sink = None
    if mode == "embedded":
        event_sink = WebSocketEventSink()

    # Global event broadcaster (always available)
    broadcaster = GlobalEventBroadcaster()
    app.state.event_broadcaster = broadcaster

    # Auth dependency applied to all API routes
    auth_deps = [Depends(verify_api_key)]

    # Routes (event_sink must be created before runs_router)
    app.include_router(workspace_router(provider), dependencies=auth_deps)
    app.include_router(agents_router(provider), dependencies=auth_deps)
    app.include_router(engines_router(provider), dependencies=auth_deps)
    app.include_router(flows_router(provider), dependencies=auth_deps)
    app.include_router(config_router(provider), dependencies=auth_deps)
    app.include_router(runs_router(provider, event_sink=event_sink, mode=mode), dependencies=auth_deps)
    app.include_router(events_router(), dependencies=auth_deps)

    if event_sink is not None:
        app.include_router(ws_router(event_sink))

    # Global events WebSocket (no auth — WebSocket clients handle auth differently)
    app.include_router(global_events_router(broadcaster))

    # Store event_sink on app for CLI integration
    app.state.event_sink = event_sink

    # CORS: only for development (console --dev mode)
    if os.getenv("MINIAUTOGEN_DEV"):
        dev_origins = [
            f"http://localhost:{p}" for p in range(3000, 3010)
        ] + [
            f"http://127.0.0.1:{p}" for p in range(3000, 3010)
        ] + [
            f"http://localhost:{p}" for p in range(8080, 8090)
        ] + [
            f"http://127.0.0.1:{p}" for p in range(8080, 8090)
        ]
        app.add_middleware(
            CORSMiddleware,
            allow_origins=dev_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Serve frontend static files (Next.js static export)
    # The console command copies build output to cli/server/static/
    cli_static_dir = Path(__file__).resolve().parent.parent / "cli" / "server" / "static"
    server_static_dir = Path(__file__).parent / "static"
    # Prefer cli/server/static (where console --build copies to), fall back to server/static
    static_dir = cli_static_dir if cli_static_dir.is_dir() else server_static_dir
    if static_dir.is_dir():
        from starlette.responses import FileResponse, Response
        from starlette.staticfiles import StaticFiles

        # Next.js static export generates {page}.html files (not {page}/index.html).
        # Starlette's StaticFiles(html=True) only looks for index.html in directories.
        # This catch-all tries {path}.html before falling back to 404.
        @app.get("/{path:path}")
        async def serve_frontend(path: str) -> Response:
            # Try exact file first (e.g., _next/static/...)
            exact = static_dir / path
            if exact.is_file():
                return FileResponse(exact)
            # Try {path}.html (e.g., /agents -> agents.html)
            html_file = static_dir / f"{path}.html"
            if html_file.is_file():
                return FileResponse(html_file)
            # Try {path}/index.html (e.g., / -> index.html)
            index_file = static_dir / path / "index.html"
            if index_file.is_file():
                return FileResponse(index_file)
            # Root index
            root_index = static_dir / "index.html"
            if not path and root_index.is_file():
                return FileResponse(root_index)
            # 404
            not_found = static_dir / "404.html"
            if not_found.is_file():
                return FileResponse(not_found, status_code=404)
            return Response("Not Found", status_code=404)

    return app
