"""FastAPI application factory for MiniAutoGen Console."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from miniautogen.server.routes.workspace import workspace_router
from miniautogen.server.routes.agents import agents_router
from miniautogen.server.routes.flows import flows_router
from miniautogen.server.routes.runs import runs_router
from miniautogen.server.ws import WebSocketEventSink, ws_router


def create_app(
    *,
    provider: Any | None = None,
    workspace_path: str | Path | None = None,
    mode: Literal["embedded", "standalone"] = "embedded",
) -> FastAPI:
    """Create the Console Server FastAPI application."""
    if provider is None:
        from miniautogen.tui.data_provider import DashDataProvider

        path = Path(workspace_path or ".").resolve()
        provider = DashDataProvider(path)

    app = FastAPI(title="MiniAutoGen Console", version="0.1.0")

    # Custom error handler: return ErrorResponse at top level, not nested in "detail"
    @app.exception_handler(HTTPException)
    async def custom_http_exception_handler(request, exc):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)

    # Routes
    app.include_router(workspace_router(provider))
    app.include_router(agents_router(provider))
    app.include_router(flows_router(provider))
    app.include_router(runs_router(provider))

    # WebSocket (embedded mode only — live event streaming)
    event_sink = None
    if mode == "embedded":
        event_sink = WebSocketEventSink()
        app.include_router(ws_router(event_sink))

    # Store event_sink on app for CLI integration
    app.state.event_sink = event_sink

    # CORS: only for development
    if os.getenv("MINIAUTOGEN_DEV"):
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
        )

    return app
