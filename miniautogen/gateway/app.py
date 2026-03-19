"""FastAPI application factory for MiniAutoGen HTTP gateway."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI


def create_app(
    run_store: Any = None,
    event_store: Any = None,
    title: str = "MiniAutoGen API",
    version: str = "0.1.0",
) -> FastAPI:
    """Create FastAPI app with run management routes.

    Args:
        run_store: RunStore implementation for persisting run metadata.
        event_store: EventStore implementation for persisting events.
        title: API title shown in OpenAPI docs.
        version: API version string.

    Returns:
        Configured FastAPI application.
    """
    app = FastAPI(title=title, version=version)

    # Store dependencies in app.state for access by routes
    app.state.run_store = run_store
    app.state.event_store = event_store

    # Include router
    from miniautogen.gateway.routes import router

    app.include_router(router)

    return app
