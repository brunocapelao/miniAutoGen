"""Shared fixtures for gateway tests."""

from __future__ import annotations

import pytest

from miniautogen.gateway.rate_limit import limiter


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Reset rate limiter storage before each test to prevent cross-test interference."""
    limiter.reset()
