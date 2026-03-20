"""Tests for DelegationRouterProtocol and PersistableMemory protocols."""

from __future__ import annotations

from typing import Any

import pytest

from miniautogen.core.contracts.delegation import (
    DelegationRouterProtocol,
    PersistableMemory,
)


# ---------------------------------------------------------------------------
# Fake implementations
# ---------------------------------------------------------------------------


class _FakeDelegationRouter:
    """Satisfies DelegationRouterProtocol structurally."""

    def __init__(self) -> None:
        # Simple allow-list: (from, to) pairs that are permitted
        self._allowed: set[tuple[str, str]] = {("agent_a", "agent_b")}

    def can_delegate(self, from_agent: str, to_agent: str) -> bool:
        return (from_agent, to_agent) in self._allowed

    async def delegate(
        self,
        from_agent: str,
        to_agent: str,
        input_data: Any,
        current_depth: int = 0,
    ) -> Any:
        return f"delegated:{from_agent}->{to_agent}:{input_data}"


class _BrokenRouter:
    """Does NOT satisfy DelegationRouterProtocol — missing delegate()."""

    def can_delegate(self, from_agent: str, to_agent: str) -> bool:
        return True


class _FakePersistableMemory:
    """Satisfies PersistableMemory structurally."""

    def __init__(self) -> None:
        self.loaded = False
        self.persisted = False

    async def load_from_disk(self) -> None:
        self.loaded = True

    async def persist_to_disk(self) -> None:
        self.persisted = True


class _BrokenPersistableMemory:
    """Does NOT satisfy PersistableMemory — missing persist_to_disk()."""

    async def load_from_disk(self) -> None:
        pass


# ---------------------------------------------------------------------------
# DelegationRouterProtocol isinstance checks
# ---------------------------------------------------------------------------


def test_delegation_router_protocol_is_runtime_checkable() -> None:
    router = _FakeDelegationRouter()
    assert isinstance(router, DelegationRouterProtocol)


def test_broken_router_does_not_satisfy_protocol() -> None:
    router = _BrokenRouter()
    assert not isinstance(router, DelegationRouterProtocol)


def test_router_can_delegate_returns_true_for_allowed_pair() -> None:
    router = _FakeDelegationRouter()
    assert router.can_delegate("agent_a", "agent_b") is True


def test_router_can_delegate_returns_false_for_disallowed_pair() -> None:
    router = _FakeDelegationRouter()
    assert router.can_delegate("agent_b", "agent_a") is False


@pytest.mark.anyio
async def test_router_delegate_returns_result() -> None:
    router = _FakeDelegationRouter()
    result = await router.delegate("agent_a", "agent_b", "hello")
    assert result == "delegated:agent_a->agent_b:hello"


@pytest.mark.anyio
async def test_router_delegate_accepts_depth_parameter() -> None:
    router = _FakeDelegationRouter()
    result = await router.delegate("agent_a", "agent_b", "data", current_depth=2)
    assert result is not None


# ---------------------------------------------------------------------------
# PersistableMemory isinstance checks
# ---------------------------------------------------------------------------


def test_persistable_memory_protocol_is_runtime_checkable() -> None:
    mem = _FakePersistableMemory()
    assert isinstance(mem, PersistableMemory)


def test_broken_persistable_memory_does_not_satisfy_protocol() -> None:
    mem = _BrokenPersistableMemory()
    assert not isinstance(mem, PersistableMemory)


@pytest.mark.anyio
async def test_persistable_memory_load_from_disk() -> None:
    mem = _FakePersistableMemory()
    assert mem.loaded is False
    await mem.load_from_disk()
    assert mem.loaded is True


@pytest.mark.anyio
async def test_persistable_memory_persist_to_disk() -> None:
    mem = _FakePersistableMemory()
    assert mem.persisted is False
    await mem.persist_to_disk()
    assert mem.persisted is True
