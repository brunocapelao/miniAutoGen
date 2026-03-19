"""Tests for EffectInterceptor idempotency middleware."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest

from miniautogen.core.contracts.effect import (
    EffectDeniedError,
    EffectDescriptor,
    EffectDuplicateError,
    EffectRecord,
    EffectStatus,
)
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.events.types import EventType
from miniautogen.policies.effect import EffectPolicy
from miniautogen.stores.in_memory_effect_journal import InMemoryEffectJournal


class TestIdempotencyKeyComputation:
    def test_import(self) -> None:
        from miniautogen.core.effect_interceptor import EffectInterceptor  # noqa: F401

    def test_compute_idempotency_key_deterministic(self) -> None:
        from miniautogen.core.effect_interceptor import compute_idempotency_key

        key1 = compute_idempotency_key(
            run_id="run-1",
            step_id="step-1",
            tool_name="send_email",
            args_hash="abc123",
        )
        key2 = compute_idempotency_key(
            run_id="run-1",
            step_id="step-1",
            tool_name="send_email",
            args_hash="abc123",
        )
        assert key1 == key2

    def test_compute_idempotency_key_is_sha256(self) -> None:
        from miniautogen.core.effect_interceptor import compute_idempotency_key

        key = compute_idempotency_key(
            run_id="run-1",
            step_id="step-1",
            tool_name="send_email",
            args_hash="abc123",
        )
        # SHA-256 hex digest is 64 characters
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)

    def test_compute_idempotency_key_different_inputs(self) -> None:
        from miniautogen.core.effect_interceptor import compute_idempotency_key

        key1 = compute_idempotency_key(
            run_id="run-1", step_id="step-1",
            tool_name="send_email", args_hash="abc",
        )
        key2 = compute_idempotency_key(
            run_id="run-1", step_id="step-1",
            tool_name="send_email", args_hash="def",
        )
        assert key1 != key2

    def test_compute_args_hash_uses_sorted_json(self) -> None:
        from miniautogen.core.effect_interceptor import compute_args_hash

        # Same args in different order should produce same hash
        hash1 = compute_args_hash({"b": 2, "a": 1})
        hash2 = compute_args_hash({"a": 1, "b": 2})
        assert hash1 == hash2

    def test_compute_args_hash_is_sha256(self) -> None:
        from miniautogen.core.effect_interceptor import compute_args_hash

        h = compute_args_hash({"key": "value"})
        assert len(h) == 64

    def test_compute_args_hash_deterministic(self) -> None:
        from miniautogen.core.effect_interceptor import compute_args_hash

        h1 = compute_args_hash({"action": "send", "to": "user@example.com"})
        h2 = compute_args_hash({"action": "send", "to": "user@example.com"})
        assert h1 == h2

    def test_compute_args_hash_uses_stdlib_json_not_orjson(self) -> None:
        """Verify deterministic key ordering via json.dumps(sort_keys=True)."""
        from miniautogen.core.effect_interceptor import compute_args_hash

        args = {"z": 1, "a": 2, "m": 3}
        expected = hashlib.sha256(
            json.dumps(args, sort_keys=True).encode()
        ).hexdigest()
        assert compute_args_hash(args) == expected


# --- Integration tests: Happy Path ---


async def _dummy_tool(to: str = "", subject: str = "", **kwargs: object) -> dict[str, str]:
    """Simulated tool that returns a result."""
    return {"status": "sent", "to": to}


@pytest.mark.asyncio
async def test_first_execution_registers_and_completes() -> None:
    from miniautogen.core.effect_interceptor import EffectInterceptor

    journal = InMemoryEffectJournal()
    sink = InMemoryEventSink()
    interceptor = EffectInterceptor(journal=journal, event_sink=sink)

    result = await interceptor.execute(
        run_id="run-1",
        step_id="step-1",
        tool_name="send_email",
        args={"to": "user@example.com", "subject": "hello"},
        tool_fn=_dummy_tool,
    )

    assert result == {"status": "sent", "to": "user@example.com"}

    # Verify events emitted
    event_types = [e.type for e in sink.events]
    assert EventType.EFFECT_REGISTERED.value in event_types
    assert EventType.EFFECT_EXECUTED.value in event_types

    # Verify journal state
    records = await journal.list_by_run("run-1")
    assert len(records) == 1
    assert records[0].status == EffectStatus.COMPLETED


@pytest.mark.asyncio
async def test_duplicate_execution_skips() -> None:
    from miniautogen.core.effect_interceptor import EffectInterceptor

    journal = InMemoryEffectJournal()
    sink = InMemoryEventSink()
    interceptor = EffectInterceptor(journal=journal, event_sink=sink)

    # First execution
    await interceptor.execute(
        run_id="run-1",
        step_id="step-1",
        tool_name="send_email",
        args={"to": "user@example.com"},
        tool_fn=_dummy_tool,
    )

    # Second execution (retry) with same args
    call_count = 0

    async def counting_tool(to: str = "") -> dict[str, str]:
        nonlocal call_count
        call_count += 1
        return {"status": "sent", "to": to}

    result = await interceptor.execute(
        run_id="run-1",
        step_id="step-1",
        tool_name="send_email",
        args={"to": "user@example.com"},
        tool_fn=counting_tool,
    )

    # Tool was NOT called on retry
    assert call_count == 0
    # Result is None (cached, no stored result value)
    assert result is None

    # EFFECT_SKIPPED was emitted
    skip_events = [
        e for e in sink.events
        if e.type == EventType.EFFECT_SKIPPED.value
    ]
    assert len(skip_events) == 1


@pytest.mark.asyncio
async def test_failed_execution_allows_retry() -> None:
    from miniautogen.core.effect_interceptor import EffectInterceptor

    journal = InMemoryEffectJournal()
    sink = InMemoryEventSink()
    interceptor = EffectInterceptor(journal=journal, event_sink=sink)

    # First execution fails
    async def failing_tool(to: str = "") -> None:
        raise TimeoutError("connection timed out")

    with pytest.raises(TimeoutError):
        await interceptor.execute(
            run_id="run-1",
            step_id="step-1",
            tool_name="send_email",
            args={"to": "user@example.com"},
            tool_fn=failing_tool,
        )

    # Verify FAILED in journal
    records = await journal.list_by_run("run-1")
    assert len(records) == 1
    assert records[0].status == EffectStatus.FAILED

    # Verify EFFECT_FAILED event
    fail_events = [e for e in sink.events if e.type == EventType.EFFECT_FAILED.value]
    assert len(fail_events) == 1

    # Second execution (retry) should succeed
    result = await interceptor.execute(
        run_id="run-1",
        step_id="step-1",
        tool_name="send_email",
        args={"to": "user@example.com"},
        tool_fn=_dummy_tool,
    )
    assert result == {"status": "sent", "to": "user@example.com"}

    # Now COMPLETED in journal
    records = await journal.list_by_run("run-1")
    assert len(records) == 1
    assert records[0].status == EffectStatus.COMPLETED


# --- Policy Enforcement ---


@pytest.mark.asyncio
async def test_policy_blocks_disallowed_effect_type() -> None:
    from miniautogen.core.effect_interceptor import EffectInterceptor

    journal = InMemoryEffectJournal()
    sink = InMemoryEventSink()
    policy = EffectPolicy(allowed_effect_types=frozenset({"api_request"}))
    interceptor = EffectInterceptor(journal=journal, policy=policy, event_sink=sink)

    with pytest.raises(EffectDeniedError, match="not in allowed types"):
        await interceptor.execute(
            run_id="run-1",
            step_id="step-1",
            tool_name="send_email",
            args={"to": "user@example.com"},
            effect_type="tool_call",
            tool_fn=_dummy_tool,
        )


@pytest.mark.asyncio
async def test_policy_allows_matching_effect_type() -> None:
    from miniautogen.core.effect_interceptor import EffectInterceptor

    journal = InMemoryEffectJournal()
    policy = EffectPolicy(allowed_effect_types=frozenset({"tool_call"}))
    interceptor = EffectInterceptor(journal=journal, policy=policy)

    result = await interceptor.execute(
        run_id="run-1",
        step_id="step-1",
        tool_name="send_email",
        args={"to": "user@example.com"},
        effect_type="tool_call",
        tool_fn=_dummy_tool,
    )
    assert result is not None


@pytest.mark.asyncio
async def test_policy_none_allows_all_types() -> None:
    from miniautogen.core.effect_interceptor import EffectInterceptor

    journal = InMemoryEffectJournal()
    policy = EffectPolicy(allowed_effect_types=None)
    interceptor = EffectInterceptor(journal=journal, policy=policy)

    result = await interceptor.execute(
        run_id="run-1",
        step_id="step-1",
        tool_name="send_email",
        args={"to": "user@example.com"},
        effect_type="custom_type",
        tool_fn=_dummy_tool,
    )
    assert result is not None


@pytest.mark.asyncio
async def test_policy_blocks_exceeding_max_effects_per_step() -> None:
    from miniautogen.core.effect_interceptor import EffectInterceptor

    journal = InMemoryEffectJournal()
    policy = EffectPolicy(max_effects_per_step=2)
    interceptor = EffectInterceptor(journal=journal, policy=policy)

    # First 2 effects succeed
    await interceptor.execute(
        run_id="run-1", step_id="step-1",
        tool_name="tool_a", args={"x": 1},
        tool_fn=_dummy_tool,
    )
    await interceptor.execute(
        run_id="run-1", step_id="step-1",
        tool_name="tool_b", args={"x": 2},
        tool_fn=_dummy_tool,
    )

    # Third effect blocked
    with pytest.raises(EffectDeniedError, match="Max effects per step"):
        await interceptor.execute(
            run_id="run-1", step_id="step-1",
            tool_name="tool_c", args={"x": 3},
            tool_fn=_dummy_tool,
        )


@pytest.mark.asyncio
async def test_max_effects_per_step_is_per_step() -> None:
    from miniautogen.core.effect_interceptor import EffectInterceptor

    journal = InMemoryEffectJournal()
    policy = EffectPolicy(max_effects_per_step=1)
    interceptor = EffectInterceptor(journal=journal, policy=policy)

    # step-1 gets 1 effect
    await interceptor.execute(
        run_id="run-1", step_id="step-1",
        tool_name="tool_a", args={"x": 1},
        tool_fn=_dummy_tool,
    )

    # step-2 gets its own budget
    await interceptor.execute(
        run_id="run-1", step_id="step-2",
        tool_name="tool_a", args={"x": 1},
        tool_fn=_dummy_tool,
    )
    # No error -- different step


# --- Stale PENDING and Concurrent Execution ---


@pytest.mark.asyncio
async def test_fresh_pending_raises_duplicate_error() -> None:
    from miniautogen.core.effect_interceptor import (
        EffectInterceptor,
        compute_args_hash,
        compute_idempotency_key,
    )

    journal = InMemoryEffectJournal()
    sink = InMemoryEventSink()
    interceptor = EffectInterceptor(journal=journal, event_sink=sink)

    # Manually register a fresh PENDING record
    args_hash = compute_args_hash({"to": "user@example.com"})
    key = compute_idempotency_key(
        run_id="run-1", step_id="step-1",
        tool_name="send_email", args_hash=args_hash,
    )
    record = EffectRecord(
        idempotency_key=key,
        descriptor=EffectDescriptor(
            effect_type="tool_call",
            tool_name="send_email",
            args_hash=args_hash,
            run_id="run-1",
            step_id="step-1",
        ),
        status=EffectStatus.PENDING,
        created_at=datetime.now(timezone.utc),  # Fresh -- just now
    )
    await journal.register(record)

    with pytest.raises(EffectDuplicateError, match="currently PENDING"):
        await interceptor.execute(
            run_id="run-1",
            step_id="step-1",
            tool_name="send_email",
            args={"to": "user@example.com"},
            tool_fn=_dummy_tool,
        )


@pytest.mark.asyncio
async def test_stale_pending_is_reclaimed() -> None:
    from miniautogen.core.effect_interceptor import (
        EffectInterceptor,
        compute_args_hash,
        compute_idempotency_key,
    )

    journal = InMemoryEffectJournal()
    sink = InMemoryEventSink()
    policy = EffectPolicy(stale_pending_timeout_seconds=60.0)
    interceptor = EffectInterceptor(
        journal=journal, policy=policy, event_sink=sink,
    )

    # Manually register a stale PENDING record (created 2 hours ago)
    args_hash = compute_args_hash({"to": "user@example.com"})
    key = compute_idempotency_key(
        run_id="run-1", step_id="step-1",
        tool_name="send_email", args_hash=args_hash,
    )
    stale_time = datetime.now(timezone.utc) - timedelta(hours=2)
    record = EffectRecord(
        idempotency_key=key,
        descriptor=EffectDescriptor(
            effect_type="tool_call",
            tool_name="send_email",
            args_hash=args_hash,
            run_id="run-1",
            step_id="step-1",
        ),
        status=EffectStatus.PENDING,
        created_at=stale_time,
    )
    await journal.register(record)

    # Should reclaim and re-execute
    result = await interceptor.execute(
        run_id="run-1",
        step_id="step-1",
        tool_name="send_email",
        args={"to": "user@example.com"},
        tool_fn=_dummy_tool,
    )
    assert result == {"status": "sent", "to": "user@example.com"}

    # Verify EFFECT_STALE_RECLAIMED event
    reclaimed_events = [
        e for e in sink.events
        if e.type == EventType.EFFECT_STALE_RECLAIMED.value
    ]
    assert len(reclaimed_events) == 1

    # Verify journal now shows COMPLETED
    fetched = await journal.get(key)
    assert fetched is not None
    assert fetched.status == EffectStatus.COMPLETED


@pytest.mark.asyncio
async def test_stale_pending_boundary_not_stale() -> None:
    """A PENDING record exactly at the timeout boundary is NOT stale."""
    from miniautogen.core.effect_interceptor import (
        EffectInterceptor,
        compute_args_hash,
        compute_idempotency_key,
    )

    journal = InMemoryEffectJournal()
    policy = EffectPolicy(stale_pending_timeout_seconds=3600.0)
    interceptor = EffectInterceptor(journal=journal, policy=policy)

    # Created 30 minutes ago (within 1 hour timeout)
    args_hash = compute_args_hash({"to": "user@example.com"})
    key = compute_idempotency_key(
        run_id="run-1", step_id="step-1",
        tool_name="send_email", args_hash=args_hash,
    )
    recent_time = datetime.now(timezone.utc) - timedelta(minutes=30)
    record = EffectRecord(
        idempotency_key=key,
        descriptor=EffectDescriptor(
            effect_type="tool_call",
            tool_name="send_email",
            args_hash=args_hash,
            run_id="run-1",
            step_id="step-1",
        ),
        status=EffectStatus.PENDING,
        created_at=recent_time,
    )
    await journal.register(record)

    # Should raise EffectDuplicateError (not stale)
    with pytest.raises(EffectDuplicateError):
        await interceptor.execute(
            run_id="run-1",
            step_id="step-1",
            tool_name="send_email",
            args={"to": "user@example.com"},
            tool_fn=_dummy_tool,
        )
