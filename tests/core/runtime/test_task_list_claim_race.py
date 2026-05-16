"""Tests for atomic claim race conditions in InMemoryTaskListStore."""

from __future__ import annotations

import anyio
import pytest

from miniautogen.core.contracts.team_task import TaskEntry
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.runtime.team_task_list import InMemoryTaskListStore


@pytest.fixture
def store() -> InMemoryTaskListStore:
    sink = InMemoryEventSink()
    return InMemoryTaskListStore(
        team_run_id="test-race",
        event_sink=sink,
    )


@pytest.mark.anyio
async def test_10_teammates_compete_for_1_task(
    store: InMemoryTaskListStore,
) -> None:
    entry = TaskEntry(title="Hot task", created_by="lead")
    task_id = await store.add(entry, actor="lead")

    results: list[bool] = []

    async def contender(name: str) -> None:
        result = await store.claim(task_id=task_id, teammate=name)
        results.append(result is not None)

    async with anyio.create_task_group() as tg:
        for i in range(10):
            tg.start_soon(contender, f"teammate-{i}")

    wins = sum(1 for r in results if r)
    assert wins == 1, f"Expected exactly 1 winner, got {wins}"


@pytest.mark.anyio
async def test_5_teammates_compete_for_2_tasks_with_labels(
    store: InMemoryTaskListStore,
) -> None:
    t1 = TaskEntry(title="Legal review", created_by="lead", labels=["legal"])
    t2 = TaskEntry(title="Security audit", created_by="lead", labels=["security"])
    await store.add(t1, actor="lead")
    await store.add(t2, actor="lead")

    claims: list[str] = []
    lock = anyio.Lock()

    async def contender(name: str) -> None:
        result = await store.claim(None, teammate=name, labels=["legal", "security"])
        if result is not None:
            async with lock:
                claims.append(name)

    async with anyio.create_task_group() as tg:
        for i in range(5):
            tg.start_soon(contender, f"worker-{i}")

    assert len(claims) <= 2


@pytest.mark.anyio
async def test_double_claim_returns_none(store: InMemoryTaskListStore) -> None:
    entry = TaskEntry(title="Singular", created_by="lead")
    task_id = await store.add(entry, actor="lead")

    r1 = await store.claim(task_id=task_id, teammate="alice")
    assert r1 is not None

    r2 = await store.claim(task_id=task_id, teammate="bob")
    assert r2 is None
