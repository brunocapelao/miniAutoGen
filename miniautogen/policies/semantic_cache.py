"""Semantic Cache -- reduces LLM costs by caching semantically similar requests.

Implements a RuntimeInterceptor that checks for cached responses before
allowing a step to execute. When a cache hit is found (exact or semantic
match), the cached result is returned without calling the LLM.

Two cache strategies:
1. **ExactCache**: Hash-based exact match on the input string.
2. **SemanticCache**: Uses embeddings to find semantically similar inputs
   within a configurable similarity threshold.

Both are optional RuntimeInterceptors that integrate with the existing
InterceptorPipeline without modifying coordination logic.

Usage::

    from miniautogen.policies.semantic_cache import ExactCache, SemanticCache

    # Simple hash-based cache
    cache = ExactCache(max_size=1000, ttl_seconds=3600)

    # Semantic similarity cache (requires embeddings)
    cache = SemanticCache(
        similarity_threshold=0.95,
        max_size=500,
        embedding_fn=my_embedding_function,
    )

.. stability:: experimental
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from miniautogen.core.contracts.run_context import RunContext
from miniautogen.observability import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class CacheEntry:
    """A single cache entry with metadata."""

    key: str
    input_hash: str
    result: Any
    created_at: float


class CacheStats:
    """Tracks cache performance metrics."""

    def __init__(self) -> None:
        self.hits: int = 0
        self.misses: int = 0
        self.evictions: int = 0

    @property
    def total(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.hits / self.total

    def to_dict(self) -> dict[str, Any]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "total": self.total,
            "hit_rate": self.hit_rate,
        }


class ExactCache:
    """RuntimeInterceptor that caches results based on exact input hash.

    Implements before_step to check cache and after_step to store results.
    Uses SHA-256 hash of the serialized input for lookup.

    Example::

        cache = ExactCache(max_size=1000, ttl_seconds=3600)
        pipeline = InterceptorPipeline(interceptors=[cache])
    """

    def __init__(
        self,
        *,
        max_size: int = 1000,
        ttl_seconds: float = 3600.0,
        namespace: str = "default",
    ) -> None:
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._namespace = namespace
        self._cache: dict[str, CacheEntry] = {}
        self._stats = CacheStats()
        self._pending_hashes: dict[str, str] = {}

    @property
    def stats(self) -> CacheStats:
        return self._stats

    @property
    def size(self) -> int:
        return len(self._cache)

    async def before_step(
        self,
        input: Any,
        context: RunContext,
    ) -> Any:
        """Check cache before step execution.

        If a cache hit is found, stores the result in the RunContext
        metadata so should_execute can bail and after_step can return it.
        """
        input_hash = self._compute_hash(input)
        self._pending_hashes[context.run_id] = input_hash

        entry = self._cache.get(input_hash)
        if entry is not None:
            # Check TTL
            if time.monotonic() - entry.created_at <= self._ttl_seconds:
                self._stats.hits += 1
                logger.info(
                    "cache_hit",
                    cache_type="exact",
                    run_id=context.run_id,
                    input_hash=input_hash[:12],
                )
                # Store cache hit in context for retrieval
                return _CacheHitSentinel(entry.result)
            else:
                # Expired entry
                del self._cache[input_hash]
                self._stats.evictions += 1

        self._stats.misses += 1
        logger.debug(
            "cache_miss",
            cache_type="exact",
            run_id=context.run_id,
            input_hash=input_hash[:12],
        )
        return input

    async def should_execute(
        self,
        context: RunContext,
    ) -> bool:
        """Always allow execution (cache hits are handled via sentinel)."""
        return True

    async def after_step(
        self,
        result: Any,
        context: RunContext,
    ) -> Any:
        """If cache hit, return cached result. Otherwise, store new result."""
        # If the result is a cache hit sentinel, unwrap it
        if isinstance(result, _CacheHitSentinel):
            return result.value

        # Store new result in cache
        input_hash = self._pending_hashes.pop(context.run_id, None)
        if input_hash is not None:
            self._evict_if_full()
            self._cache[input_hash] = CacheEntry(
                key=input_hash,
                input_hash=input_hash,
                result=result,
                created_at=time.monotonic(),
            )

        return result

    async def on_error(
        self,
        error: Exception,
        context: RunContext,
    ) -> Any:
        """Do not recover from errors (pass through)."""
        self._pending_hashes.pop(context.run_id, None)
        return None

    def invalidate(self, input: Any) -> bool:
        """Invalidate a specific cache entry.

        Returns True if the entry was found and removed.
        """
        input_hash = self._compute_hash(input)
        if input_hash in self._cache:
            del self._cache[input_hash]
            return True
        return False

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()

    def _compute_hash(self, input: Any) -> str:
        """Compute a deterministic hash of the input."""
        serialized = json.dumps(input, sort_keys=True, default=str)
        return hashlib.sha256(
            f"{self._namespace}:{serialized}".encode()
        ).hexdigest()

    def _evict_if_full(self) -> None:
        """Evict the oldest entry if cache is at capacity."""
        if len(self._cache) >= self._max_size:
            oldest_key = min(
                self._cache, key=lambda k: self._cache[k].created_at,
            )
            del self._cache[oldest_key]
            self._stats.evictions += 1


class SemanticCache:
    """RuntimeInterceptor that caches results based on semantic similarity.

    Uses embeddings to find semantically similar inputs. When the cosine
    similarity between a new input and a cached input exceeds the threshold,
    the cached result is returned.

    Requires an embedding function that maps text to a list of floats.

    Example::

        async def embed(text: str) -> list[float]:
            # Call your embedding API
            return await embedding_api.encode(text)

        cache = SemanticCache(
            embedding_fn=embed,
            similarity_threshold=0.95,
        )
    """

    def __init__(
        self,
        *,
        embedding_fn: Callable[[str], Awaitable[list[float]]],
        similarity_threshold: float = 0.95,
        max_size: int = 500,
        ttl_seconds: float = 3600.0,
        namespace: str = "default",
    ) -> None:
        if not 0.0 <= similarity_threshold <= 1.0:
            raise ValueError("similarity_threshold must be between 0.0 and 1.0")

        self._embedding_fn = embedding_fn
        self._threshold = similarity_threshold
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._namespace = namespace
        self._entries: list[_SemanticEntry] = []
        self._stats = CacheStats()
        self._pending: dict[str, tuple[str, list[float]]] = {}

    @property
    def stats(self) -> CacheStats:
        return self._stats

    @property
    def size(self) -> int:
        return len(self._entries)

    async def before_step(
        self,
        input: Any,
        context: RunContext,
    ) -> Any:
        """Check semantic cache for similar inputs."""
        input_text = str(input)

        try:
            embedding = await self._embedding_fn(input_text)
        except Exception:
            # If embedding fails, skip cache
            self._stats.misses += 1
            return input

        self._pending[context.run_id] = (input_text, embedding)

        # Remove expired entries
        now = time.monotonic()
        self._entries = [
            e for e in self._entries
            if now - e.created_at <= self._ttl_seconds
        ]

        # Find best match
        best_score = -1.0
        best_entry: _SemanticEntry | None = None

        for entry in self._entries:
            score = _cosine_similarity(embedding, entry.embedding)
            if score > best_score:
                best_score = score
                best_entry = entry

        if best_entry is not None and best_score >= self._threshold:
            self._stats.hits += 1
            logger.info(
                "cache_hit",
                cache_type="semantic",
                run_id=context.run_id,
                similarity=round(best_score, 4),
            )
            return _CacheHitSentinel(best_entry.result)

        self._stats.misses += 1
        return input

    async def should_execute(self, context: RunContext) -> bool:
        return True

    async def after_step(self, result: Any, context: RunContext) -> Any:
        if isinstance(result, _CacheHitSentinel):
            return result.value

        # Store new entry
        pending = self._pending.pop(context.run_id, None)
        if pending is not None:
            input_text, embedding = pending
            self._evict_if_full()
            self._entries.append(
                _SemanticEntry(
                    input_text=input_text,
                    embedding=embedding,
                    result=result,
                    created_at=time.monotonic(),
                )
            )

        return result

    async def on_error(self, error: Exception, context: RunContext) -> Any:
        self._pending.pop(context.run_id, None)
        return None

    def clear(self) -> None:
        """Clear all cache entries."""
        self._entries.clear()

    def _evict_if_full(self) -> None:
        if len(self._entries) >= self._max_size:
            self._entries.sort(key=lambda e: e.created_at)
            self._entries.pop(0)
            self._stats.evictions += 1


@dataclass
class _SemanticEntry:
    """Internal entry for semantic cache."""

    input_text: str
    embedding: list[float]
    result: Any
    created_at: float


class _CacheHitSentinel:
    """Sentinel value to signal a cache hit through the interceptor pipeline."""

    def __init__(self, value: Any) -> None:
        self.value = value


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
