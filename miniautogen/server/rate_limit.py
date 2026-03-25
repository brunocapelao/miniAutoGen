"""Rate limiting configuration for the Console Server."""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address


def create_console_limiter() -> Limiter:
    """Create a fresh rate limiter instance with default limits."""
    return Limiter(
        key_func=get_remote_address,
        default_limits=["60/minute"],
    )
