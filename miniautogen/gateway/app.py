"""FastAPI application factory for MiniAutoGen HTTP gateway."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import JSONResponse

from miniautogen.gateway.rate_limit import limiter
from miniautogen.gateway.security import verify_api_key


MAX_BODY_SIZE = 1 * 1024 * 1024  # 1MB


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests with body larger than MAX_BODY_SIZE bytes."""

    async def dispatch(self, request: StarletteRequest, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_BODY_SIZE:
            return JSONResponse(
                status_code=413,
                content={"detail": f"Request body too large. Maximum size is {MAX_BODY_SIZE} bytes."},
            )

        # For chunked transfer or missing content-length, read and check
        if request.method in ("POST", "PUT", "PATCH"):
            body = await request.body()
            if len(body) > MAX_BODY_SIZE:
                return JSONResponse(
                    status_code=413,
                    content={"detail": f"Request body too large. Maximum size is {MAX_BODY_SIZE} bytes."},
                )

        return await call_next(request)


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

    # Body size limit middleware
    app.add_middleware(BodySizeLimitMiddleware)

    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Include router with API key dependency on all routes
    from miniautogen.gateway.routes import router

    app.include_router(router, dependencies=[Depends(verify_api_key)])

    return app
