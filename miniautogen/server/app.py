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
from miniautogen.server.routes.flows import flows_router
from miniautogen.server.routes.runs import runs_router
from miniautogen.server.routes.workspace import workspace_router
from miniautogen.server.ws import WebSocketEventSink, ws_router

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

    # Auth dependency applied to all API routes
    auth_deps = [Depends(verify_api_key)]

    # Routes (event_sink must be created before runs_router)
    app.include_router(workspace_router(provider), dependencies=auth_deps)
    app.include_router(agents_router(provider), dependencies=auth_deps)
    app.include_router(flows_router(provider), dependencies=auth_deps)
    app.include_router(runs_router(provider, event_sink=event_sink, mode=mode), dependencies=auth_deps)

    if event_sink is not None:
        app.include_router(ws_router(event_sink))

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

    # Serve frontend static files (Next.js build output)
    static_dir = Path(__file__).parent / "static"
    if static_dir.is_dir():
        from starlette.staticfiles import StaticFiles
        app.mount("/", StaticFiles(directory=str(static_dir), html=True))

    return app
