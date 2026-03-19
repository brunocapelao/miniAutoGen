"""Tests for CircuitBreakerRegistry — process-global circuit breaker state.

Verifies failure recording, threshold-based opening, is_open queries,
reset behavior, and isolation between independent keys.
"""

from __future__ import annotations

from miniautogen.core.runtime.circuit_breaker_registry import CircuitBreakerRegistry


class TestRecordFailure:
    """record_failure increments counts and opens at threshold."""

    def test_returns_false_below_threshold(self) -> None:
        registry = CircuitBreakerRegistry(default_threshold=3)
        assert registry.record_failure("key-a") is False
        assert registry.record_failure("key-a") is False

    def test_returns_true_when_circuit_opens(self) -> None:
        registry = CircuitBreakerRegistry(default_threshold=3)
        registry.record_failure("key-a")
        registry.record_failure("key-a")
        opened = registry.record_failure("key-a")
        assert opened is True

    def test_returns_false_after_already_open(self) -> None:
        registry = CircuitBreakerRegistry(default_threshold=2)
        registry.record_failure("key-a")
        registry.record_failure("key-a")  # opens
        # Further failures don't re-trigger "just opened"
        assert registry.record_failure("key-a") is False


class TestIsOpen:
    """is_open reflects circuit state."""

    def test_closed_by_default(self) -> None:
        registry = CircuitBreakerRegistry(default_threshold=5)
        assert registry.is_open("unknown-key") is False

    def test_open_after_threshold(self) -> None:
        registry = CircuitBreakerRegistry(default_threshold=2)
        registry.record_failure("key-a")
        assert registry.is_open("key-a") is False
        registry.record_failure("key-a")
        assert registry.is_open("key-a") is True


class TestReset:
    """reset clears counts and open state for a key."""

    def test_reset_closes_circuit(self) -> None:
        registry = CircuitBreakerRegistry(default_threshold=2)
        registry.record_failure("key-a")
        registry.record_failure("key-a")
        assert registry.is_open("key-a") is True

        registry.reset("key-a")
        assert registry.is_open("key-a") is False

    def test_reset_clears_count(self) -> None:
        registry = CircuitBreakerRegistry(default_threshold=3)
        registry.record_failure("key-a")
        registry.record_failure("key-a")
        registry.reset("key-a")

        # After reset, need 3 more failures to open
        assert registry.record_failure("key-a") is False
        assert registry.record_failure("key-a") is False
        assert registry.record_failure("key-a") is True

    def test_reset_unknown_key_is_noop(self) -> None:
        registry = CircuitBreakerRegistry(default_threshold=5)
        registry.reset("nonexistent")  # should not raise


class TestKeyIsolation:
    """Different keys have independent failure counts and open states."""

    def test_different_keys_independent(self) -> None:
        registry = CircuitBreakerRegistry(default_threshold=2)
        registry.record_failure("key-a")
        registry.record_failure("key-a")
        assert registry.is_open("key-a") is True
        assert registry.is_open("key-b") is False

    def test_reset_one_key_does_not_affect_other(self) -> None:
        registry = CircuitBreakerRegistry(default_threshold=2)
        registry.record_failure("key-a")
        registry.record_failure("key-a")
        registry.record_failure("key-b")
        registry.record_failure("key-b")

        registry.reset("key-a")
        assert registry.is_open("key-a") is False
        assert registry.is_open("key-b") is True
