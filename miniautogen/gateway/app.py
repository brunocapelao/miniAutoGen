"""FastAPI application factory for MiniAutoGen HTTP gateway."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI

from miniautogen.gateway.security import verify_api_key


def create_app(
    run_store: Any = None,
    event_store: Any = None,
    title: str = "MiniAutoGen API",
    version: str = "0.1.0",
    api_key: str | None = None,
) -> FastAPI:
    """Create FastAPI app with run management routes.

    Args:
        run_store: RunStore implementation for persisting run metadata.
        event_store: EventStore implementation for persisting events.
        title: API title shown in OpenAPI docs.
        version: API version string.
        api_key: If set, all non-health routes require this key via X-API-Key header.

    Returns:
        Configured FastAPI application.
    """
    app = FastAPI(title=title, version=version)

    # Store dependencies in app.state for access by routes
    app.state.run_store = run_store
    app.state.event_store = event_store
    app.state.api_key = api_key

    # Include router with API key dependency on all routes
    from miniautogen.gateway.routes import router

    app.include_router(router, dependencies=[Depends(verify_api_key)])

    return app
