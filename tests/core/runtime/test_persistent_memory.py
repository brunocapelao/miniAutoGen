"""Tests for PersistentMemoryProvider.

Validates that PersistentMemoryProvider:
- satisfies both MemoryProvider and PersistableMemory protocols
- persists in-memory state to disk and reloads it correctly
- handles edge cases (empty dir, nonexistent dir, search)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from miniautogen.core.contracts.delegation import PersistableMemory
from miniautogen.core.contracts.memory_provider import MemoryProvider
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.runtime.persistent_memory import PersistentMemoryProvider


def _make_run_context(run_id: str = "test-run") -> RunContext:
    """Build a minimal RunContext for tests."""
    return RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id="test-corr",
    )


def test_satisfies_memory_provider(tmp_path: Path) -> None:
    pmp = PersistentMemoryProvider(memory_dir=tmp_path / "memory")
    assert isinstance(pmp, MemoryProvider)


def test_satisfies_persistable_memory(tmp_path: Path) -> None:
    pmp = PersistentMemoryProvider(memory_dir=tmp_path / "memory")
    assert isinstance(pmp, PersistableMemory)


@pytest.mark.anyio()
async def test_save_and_get_context(tmp_path: Path) -> None:
    pmp = PersistentMemoryProvider(memory_dir=tmp_path / "memory")
    ctx = _make_run_context("run-abc")

    await pmp.save_turn([{"role": "user", "content": "hello"}], ctx)
    result = await pmp.get_context("agent-1", ctx)

    assert result == [{"role": "user", "content": "hello"}]


@pytest.mark.anyio()
async def test_persist_and_reload(tmp_path: Path) -> None:
    memory_dir = tmp_path / "memory"
    pmp = PersistentMemoryProvider(memory_dir=memory_dir)
    ctx = _make_run_context("run-xyz")

    await pmp.save_turn([{"role": "user", "content": "hello"}], ctx)
    await pmp.persist_to_disk()

    # Verify files exist on disk
    assert memory_dir.exists()
    assert (memory_dir / "context.json").exists()

    # Create new instance and reload
    pmp2 = PersistentMemoryProvider(memory_dir=memory_dir)
    await pmp2.load_from_disk()

    # Verify data was recovered
    context = await pmp2.get_context("agent-1", ctx)
    assert len(context) > 0
    assert context[0]["content"] == "hello"


@pytest.mark.anyio()
async def test_persist_creates_directory(tmp_path: Path) -> None:
    memory_dir = tmp_path / "nonexistent" / "memory"
    pmp = PersistentMemoryProvider(memory_dir=memory_dir)
    await pmp.persist_to_disk()
    assert memory_dir.exists()


@pytest.mark.anyio()
async def test_load_from_empty_dir(tmp_path: Path) -> None:
    memory_dir = tmp_path / "empty_memory"
    memory_dir.mkdir()
    pmp = PersistentMemoryProvider(memory_dir=memory_dir)
    await pmp.load_from_disk()  # Should not raise
    # Store should remain empty
    ctx = _make_run_context("any-run")
    result = await pmp.get_context("agent-1", ctx)
    assert result == []


@pytest.mark.anyio()
async def test_search(tmp_path: Path) -> None:
    pmp = PersistentMemoryProvider(memory_dir=tmp_path / "memory")
    ctx = _make_run_context("run-search")

    await pmp.save_turn([{"role": "user", "content": "hello world"}], ctx)
    await pmp.save_turn([{"role": "assistant", "content": "goodbye moon"}], ctx)

    results = await pmp.search("hello")
    assert len(results) > 0
    assert any("hello" in str(r.get("content", "")) for r in results)


@pytest.mark.anyio()
async def test_search_no_matches(tmp_path: Path) -> None:
    pmp = PersistentMemoryProvider(memory_dir=tmp_path / "memory")
    ctx = _make_run_context("run-nomatch")

    await pmp.save_turn([{"role": "user", "content": "hello world"}], ctx)

    results = await pmp.search("zzznomatch")
    assert results == []


@pytest.mark.anyio()
async def test_multiple_runs_persisted(tmp_path: Path) -> None:
    memory_dir = tmp_path / "memory"
    pmp = PersistentMemoryProvider(memory_dir=memory_dir)

    ctx1 = _make_run_context("run-1")
    ctx2 = _make_run_context("run-2")

    await pmp.save_turn([{"role": "user", "content": "run one"}], ctx1)
    await pmp.save_turn([{"role": "user", "content": "run two"}], ctx2)
    await pmp.persist_to_disk()

    pmp2 = PersistentMemoryProvider(memory_dir=memory_dir)
    await pmp2.load_from_disk()

    result1 = await pmp2.get_context("agent", ctx1)
    result2 = await pmp2.get_context("agent", ctx2)

    assert result1[0]["content"] == "run one"
    assert result2[0]["content"] == "run two"


@pytest.mark.anyio()
async def test_distill_no_op(tmp_path: Path) -> None:
    """distill should not raise (no-op, inherited from InMemoryMemoryProvider)."""
    pmp = PersistentMemoryProvider(memory_dir=tmp_path / "memory")
    await pmp.distill("agent-1")  # Should not raise


@pytest.mark.anyio()
async def test_persist_overwrites_previous(tmp_path: Path) -> None:
    """Second persist replaces first — no duplicate entries on reload."""
    memory_dir = tmp_path / "memory"
    pmp = PersistentMemoryProvider(memory_dir=memory_dir)
    ctx = _make_run_context("run-ow")

    await pmp.save_turn([{"role": "user", "content": "first"}], ctx)
    await pmp.persist_to_disk()

    await pmp.save_turn([{"role": "assistant", "content": "second"}], ctx)
    await pmp.persist_to_disk()

    pmp2 = PersistentMemoryProvider(memory_dir=memory_dir)
    await pmp2.load_from_disk()
    result = await pmp2.get_context("agent", ctx)

    assert len(result) == 2
    assert result[0]["content"] == "first"
    assert result[1]["content"] == "second"
