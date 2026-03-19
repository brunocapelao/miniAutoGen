"""Tests for MemoryProvider protocol and InMemoryMemoryProvider."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from miniautogen.core.contracts.memory_provider import (
    InMemoryMemoryProvider,
    MemoryProvider,
)
from miniautogen.core.contracts.run_context import RunContext


def _make_context(run_id: str = "run-1") -> RunContext:
    return RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id="corr-1",
    )


# --- Protocol conformance ---


class _FakeMemoryProvider:
    """Satisfies MemoryProvider structurally."""

    async def get_context(
        self,
        agent_id: str,
        context: RunContext,
        max_tokens: int | None = None,
    ) -> list[dict[str, Any]]:
        return []

    async def save_turn(
        self,
        messages: list[dict[str, Any]],
        context: RunContext,
    ) -> None:
        pass

    async def distill(self, agent_id: str) -> None:
        pass


class _BrokenMemoryProvider:
    """Missing distill -- does NOT satisfy MemoryProvider."""

    async def get_context(
        self,
        agent_id: str,
        context: RunContext,
        max_tokens: int | None = None,
    ) -> list[dict[str, Any]]:
        return []

    async def save_turn(
        self,
        messages: list[dict[str, Any]],
        context: RunContext,
    ) -> None:
        pass


def test_memory_provider_is_runtime_checkable() -> None:
    provider = _FakeMemoryProvider()
    assert isinstance(provider, MemoryProvider)


def test_broken_memory_provider_not_satisfied() -> None:
    provider = _BrokenMemoryProvider()
    assert not isinstance(provider, MemoryProvider)


def test_in_memory_provider_satisfies_protocol() -> None:
    provider = InMemoryMemoryProvider()
    assert isinstance(provider, MemoryProvider)


# --- InMemoryMemoryProvider behaviour ---


@pytest.mark.anyio
async def test_in_memory_provider_starts_empty() -> None:
    provider = InMemoryMemoryProvider()
    ctx = _make_context()
    result = await provider.get_context("agent-1", ctx)
    assert result == []


@pytest.mark.anyio
async def test_in_memory_provider_save_and_retrieve() -> None:
    provider = InMemoryMemoryProvider()
    ctx = _make_context()
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]
    await provider.save_turn(messages, ctx)

    result = await provider.get_context("agent-1", ctx)
    assert len(result) == 2
    assert result[0]["content"] == "hello"
    assert result[1]["content"] == "hi there"


@pytest.mark.anyio
async def test_in_memory_provider_multiple_turns() -> None:
    provider = InMemoryMemoryProvider()
    ctx = _make_context()
    await provider.save_turn([{"role": "user", "content": "turn 1"}], ctx)
    await provider.save_turn([{"role": "user", "content": "turn 2"}], ctx)

    result = await provider.get_context("agent-1", ctx)
    assert len(result) == 2
    assert result[0]["content"] == "turn 1"
    assert result[1]["content"] == "turn 2"


@pytest.mark.anyio
async def test_in_memory_provider_max_tokens_limits() -> None:
    provider = InMemoryMemoryProvider()
    ctx = _make_context()
    # Save many messages
    for i in range(20):
        await provider.save_turn(
            [{"role": "user", "content": f"message {i}"}],
            ctx,
        )

    # max_tokens limits the number of messages returned (simple token estimate)
    result = await provider.get_context("agent-1", ctx, max_tokens=50)
    assert len(result) < 20  # Should be limited


@pytest.mark.anyio
async def test_in_memory_provider_different_runs_isolated() -> None:
    provider = InMemoryMemoryProvider()
    ctx1 = _make_context("run-1")
    ctx2 = _make_context("run-2")

    await provider.save_turn([{"role": "user", "content": "run1 msg"}], ctx1)
    await provider.save_turn([{"role": "user", "content": "run2 msg"}], ctx2)

    result1 = await provider.get_context("agent-1", ctx1)
    result2 = await provider.get_context("agent-1", ctx2)
    assert len(result1) == 1
    assert result1[0]["content"] == "run1 msg"
    assert len(result2) == 1
    assert result2[0]["content"] == "run2 msg"


@pytest.mark.anyio
async def test_in_memory_provider_distill_is_noop() -> None:
    provider = InMemoryMemoryProvider()
    ctx = _make_context()
    await provider.save_turn([{"role": "user", "content": "msg"}], ctx)

    # distill should not raise
    await provider.distill("agent-1")

    # Data should still be there
    result = await provider.get_context("agent-1", ctx)
    assert len(result) == 1
