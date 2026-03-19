"""API key authentication for the gateway."""

from __future__ import annotations

import secrets

from fastapi import HTTPException, Request, status


async def verify_api_key(request: Request) -> None:
    """FastAPI dependency that validates X-API-Key header.

    Reads the expected key from ``request.app.state.api_key``.
    If no key is configured (None), authentication is skipped.
    Health endpoint is always exempt.
    """
    expected_key: str | None = getattr(request.app.state, "api_key", None)
    if expected_key is None:
        return  # No key configured -- open access

    # Allow health checks without auth (load balancer probes)
    if request.url.path == "/health":
        return

    provided_key = request.headers.get("X-API-Key")
    if not provided_key or not secrets.compare_digest(provided_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key",
        )
