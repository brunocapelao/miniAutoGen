"""Process-global circuit breaker state shared across flows.

When one flow opens a circuit breaker for a backend/endpoint,
all other flows see it immediately. This prevents cascading failures
where multiple concurrent flows hammer a failing backend.
"""

from __future__ import annotations


class CircuitBreakerRegistry:
    """Process-global circuit breaker state shared across flows.

    When one flow opens a circuit breaker for a backend/endpoint,
    all other flows see it immediately.
    """

    def __init__(self, default_threshold: int = 5) -> None:
        self._counts: dict[str, int] = {}
        self._threshold = default_threshold
        self._open: set[str] = set()

    def record_failure(self, key: str) -> bool:
        """Record failure, return True if circuit just opened."""
        self._counts[key] = self._counts.get(key, 0) + 1
        if (
            self._counts[key] >= self._threshold
            and key not in self._open
        ):
            self._open.add(key)
            return True
        return False

    def is_open(self, key: str) -> bool:
        """Check whether the circuit breaker for *key* is open."""
        return key in self._open

    def reset(self, key: str) -> None:
        """Reset failure count and close the circuit for *key*."""
        self._counts.pop(key, None)
        self._open.discard(key)
