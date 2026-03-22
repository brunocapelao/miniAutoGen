"""Tests for ExactCache and SemanticCache interceptors."""

from __future__ import annotations

import json
import time

import pytest

from miniautogen.core.contracts.run_context import RunContext
from miniautogen.policies.semantic_cache import (
    CacheStats,
    ExactCache,
    SemanticCache,
    _cosine_similarity,
)


def _make_context(run_id: str = "test-1") -> RunContext:
    from datetime import datetime, timezone
    return RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id=run_id,
    )


class TestCacheStats:
    def test_initial(self) -> None:
        stats = CacheStats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.total == 0
        assert stats.hit_rate == 0.0

    def test_hit_rate(self) -> None:
        stats = CacheStats()
        stats.hits = 3
        stats.misses = 7
        assert stats.total == 10
        assert stats.hit_rate == 0.3

    def test_to_dict(self) -> None:
        stats = CacheStats()
        stats.hits = 1
        d = stats.to_dict()
        assert d["hits"] == 1


class TestExactCache:
    @pytest.mark.anyio
    async def test_cache_miss_then_hit(self) -> None:
        cache = ExactCache(max_size=100)
        ctx = _make_context()

        # First call: miss
        result1 = await cache.before_step("input_a", ctx)
        assert result1 == "input_a"  # Not a sentinel
        # Simulate step execution
        result1 = await cache.after_step("output_a", ctx)
        assert result1 == "output_a"

        # Second call with same input: hit
        result2 = await cache.before_step("input_a", ctx)
        # Should be a sentinel (unwrapped through after_step)
        result2 = await cache.after_step(result2, ctx)
        assert result2 == "output_a"

        assert cache.stats.hits == 1
        assert cache.stats.misses == 1

    @pytest.mark.anyio
    async def test_different_inputs_miss(self) -> None:
        cache = ExactCache()
        ctx = _make_context()

        await cache.before_step("input_a", ctx)
        await cache.after_step("output_a", ctx)

        result = await cache.before_step("input_b", ctx)
        assert result == "input_b"
        assert cache.stats.misses == 2

    @pytest.mark.anyio
    async def test_ttl_expiry(self) -> None:
        cache = ExactCache(ttl_seconds=0.01)
        ctx = _make_context()

        await cache.before_step("input", ctx)
        await cache.after_step("output", ctx)

        # Wait for TTL to expire
        time.sleep(0.02)

        result = await cache.before_step("input", ctx)
        assert result == "input"
        assert cache.stats.evictions == 1

    @pytest.mark.anyio
    async def test_max_size_eviction(self) -> None:
        cache = ExactCache(max_size=2)

        for i in range(3):
            ctx = _make_context(f"run-{i}")
            await cache.before_step(f"input_{i}", ctx)
            await cache.after_step(f"output_{i}", ctx)

        assert cache.size <= 2
        assert cache.stats.evictions >= 1

    def test_invalidate(self) -> None:
        cache = ExactCache()
        # Manually populate using json.dumps-based hash
        import hashlib
        serialized = json.dumps("test_input", sort_keys=True, default=str)
        key = hashlib.sha256(f"default:{serialized}".encode()).hexdigest()
        from miniautogen.policies.semantic_cache import CacheEntry
        cache._cache[key] = CacheEntry(
            key=key, input_hash=key, result="val", created_at=time.monotonic(),
        )
        assert cache.invalidate("test_input") is True
        assert cache.invalidate("test_input") is False

    def test_clear(self) -> None:
        cache = ExactCache()
        from miniautogen.policies.semantic_cache import CacheEntry
        cache._cache["k"] = CacheEntry(
            key="k", input_hash="k", result="v", created_at=time.monotonic(),
        )
        assert cache.size == 1
        cache.clear()
        assert cache.size == 0

    @pytest.mark.anyio
    async def test_should_execute_always_true(self) -> None:
        cache = ExactCache()
        assert await cache.should_execute(_make_context()) is True

    @pytest.mark.anyio
    async def test_on_error_returns_none(self) -> None:
        cache = ExactCache()
        result = await cache.on_error(RuntimeError("oops"), _make_context())
        assert result is None

    @pytest.mark.anyio
    async def test_concurrent_runs_isolated(self) -> None:
        """Concurrent runs with different run_ids don't interfere."""
        cache = ExactCache(max_size=100)
        ctx_a = _make_context("run-a")
        ctx_b = _make_context("run-b")

        # Start two runs simultaneously
        await cache.before_step("input_a", ctx_a)
        await cache.before_step("input_b", ctx_b)

        # Complete them in reverse order
        await cache.after_step("output_b", ctx_b)
        await cache.after_step("output_a", ctx_a)

        # Verify both stored correctly
        assert cache.size == 2

        # Verify run-a cached correctly
        result = await cache.before_step("input_a", ctx_a)
        result = await cache.after_step(result, ctx_a)
        assert result == "output_a"

        # Verify run-b cached correctly
        result = await cache.before_step("input_b", ctx_b)
        result = await cache.after_step(result, ctx_b)
        assert result == "output_b"


class TestSemanticCache:
    @staticmethod
    async def _simple_embed(text: str) -> list[float]:
        """Simple deterministic embedding for testing."""
        import hashlib
        h = hashlib.md5(text.encode()).hexdigest()
        return [int(c, 16) / 15.0 for c in h[:8]]

    @pytest.mark.anyio
    async def test_cache_exact_hit(self) -> None:
        cache = SemanticCache(
            embedding_fn=self._simple_embed,
            similarity_threshold=0.99,
        )
        ctx = _make_context()

        await cache.before_step("hello world", ctx)
        await cache.after_step("response", ctx)

        # Same input should hit
        result = await cache.before_step("hello world", ctx)
        # Unwrap through after_step
        result = await cache.after_step(result, ctx)
        assert result == "response"
        assert cache.stats.hits == 1

    @pytest.mark.anyio
    async def test_cache_miss_different_input(self) -> None:
        cache = SemanticCache(
            embedding_fn=self._simple_embed,
            similarity_threshold=0.99,
        )
        ctx = _make_context()

        await cache.before_step("hello", ctx)
        await cache.after_step("r1", ctx)

        result = await cache.before_step("completely different", ctx)
        assert result == "completely different"

    @pytest.mark.anyio
    async def test_embedding_failure_skips_cache(self) -> None:
        async def failing_embed(text: str) -> list[float]:
            raise RuntimeError("embedding service down")

        cache = SemanticCache(
            embedding_fn=failing_embed,
            similarity_threshold=0.9,
        )
        ctx = _make_context()

        result = await cache.before_step("input", ctx)
        assert result == "input"
        assert cache.stats.misses == 1

    def test_invalid_threshold_raises(self) -> None:
        async def embed(t: str) -> list[float]:
            return [0.0]

        with pytest.raises(ValueError, match="similarity_threshold"):
            SemanticCache(embedding_fn=embed, similarity_threshold=1.5)

    @pytest.mark.anyio
    async def test_ttl_expiry(self) -> None:
        cache = SemanticCache(
            embedding_fn=self._simple_embed,
            similarity_threshold=0.99,
            ttl_seconds=0.01,
        )
        ctx = _make_context()

        await cache.before_step("input", ctx)
        await cache.after_step("output", ctx)

        time.sleep(0.02)

        result = await cache.before_step("input", ctx)
        assert result == "input"

    def test_clear(self) -> None:
        async def embed(t: str) -> list[float]:
            return [1.0]

        cache = SemanticCache(embedding_fn=embed, similarity_threshold=0.9)
        cache._entries.append(None)  # type: ignore
        cache.clear()
        assert cache.size == 0

    @pytest.mark.anyio
    async def test_concurrent_runs_isolated(self) -> None:
        """Concurrent runs with different run_ids don't interfere."""
        cache = SemanticCache(
            embedding_fn=self._simple_embed,
            similarity_threshold=0.99,
        )
        ctx_a = _make_context("run-a")
        ctx_b = _make_context("run-b")

        # Start two runs simultaneously
        await cache.before_step("input_a", ctx_a)
        await cache.before_step("input_b", ctx_b)

        # Complete them in reverse order
        await cache.after_step("output_b", ctx_b)
        await cache.after_step("output_a", ctx_a)

        # Verify both stored correctly
        assert cache.size == 2


class TestCosineSimilarity:
    def test_identical_vectors(self) -> None:
        assert _cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)

    def test_orthogonal_vectors(self) -> None:
        assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_opposite_vectors(self) -> None:
        assert _cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)

    def test_different_lengths(self) -> None:
        assert _cosine_similarity([1.0], [1.0, 2.0]) == 0.0

    def test_zero_vector(self) -> None:
        assert _cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0
