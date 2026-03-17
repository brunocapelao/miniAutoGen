"""Tests for the StoreProtocol structural contract."""

from __future__ import annotations

from typing import Any

import pytest

from miniautogen.core.contracts.store import StoreProtocol
from miniautogen.stores.in_memory_run_store import InMemoryRunStore

# --- Fake implementations ---


class _FakeStore:
    """Satisfies StoreProtocol structurally."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    async def save(self, key: str, payload: dict[str, Any]) -> None:
        self._data[key] = payload

    async def get(self, key: str) -> dict[str, Any] | None:
        return self._data.get(key)

    async def exists(self, key: str) -> bool:
        return key in self._data

    async def delete(self, key: str) -> bool:
        if key in self._data:
            del self._data[key]
            return True
        return False


class _BrokenStore:
    """Does NOT satisfy StoreProtocol — missing exists()."""

    async def save(self, key: str, payload: dict[str, Any]) -> None:
        pass

    async def get(self, key: str) -> dict[str, Any] | None:
        return None


# --- Protocol isinstance checks ---


def test_fake_store_satisfies_protocol() -> None:
    store = _FakeStore()
    assert isinstance(store, StoreProtocol)


def test_broken_store_does_not_satisfy_protocol() -> None:
    store = _BrokenStore()
    assert not isinstance(store, StoreProtocol)


def test_in_memory_run_store_does_not_satisfy_protocol() -> None:
    """InMemoryRunStore uses save_run/get_run, not save/get.

    This is a deliberate design decision: the protocol targets new
    code with generic key-value semantics, not existing ABC stores.
    """
    store = InMemoryRunStore()
    assert not isinstance(store, StoreProtocol)


# --- Functional tests ---


@pytest.mark.anyio
async def test_fake_store_save_and_get() -> None:
    store = _FakeStore()
    await store.save("run-1", {"status": "ok"})
    result = await store.get("run-1")
    assert result == {"status": "ok"}


@pytest.mark.anyio
async def test_fake_store_get_missing_key_returns_none() -> None:
    store = _FakeStore()
    assert await store.get("nonexistent") is None


@pytest.mark.anyio
async def test_fake_store_exists() -> None:
    store = _FakeStore()
    assert await store.exists("run-1") is False
    await store.save("run-1", {"status": "ok"})
    assert await store.exists("run-1") is True


@pytest.mark.anyio
async def test_fake_store_serialization_roundtrip() -> None:
    """Save then get returns the same dict."""
    store = _FakeStore()
    payload: dict[str, Any] = {
        "id": "run-42",
        "steps": [1, 2, 3],
        "nested": {"a": True},
    }
    await store.save("run-42", payload)
    assert await store.get("run-42") == payload


@pytest.mark.anyio
async def test_fake_store_delete() -> None:
    store = _FakeStore()
    await store.save("key1", {"data": "value"})
    assert await store.delete("key1") is True
    assert await store.get("key1") is None
    assert await store.delete("nonexistent") is False
