"""Tests for task release on cancellation in InMemoryTaskListStore."""

from __future__ import annotations

import anyio
import pytest

from miniautogen.core.contracts.team_task import TaskEntry, TaskStatus
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.runtime.team_task_list import InMemoryTaskListStore


@pytest.fixture
def store() -> InMemoryTaskListStore:
    return InMemoryTaskListStore(
        team_run_id="test-cancel",
        event_sink=InMemoryEventSink(),
    )


@pytest.mark.anyio
async def test_release_on_cancel_returns_to_pending(
    store: InMemoryTaskListStore,
) -> None:
    entry = TaskEntry(title="Cancel me", created_by="lead")
    task_id = await store.add(entry, actor="lead")

    async def worker() -> None:
        claimed = await store.claim(task_id=task_id, teammate="alice")
        assert claimed is not None
        with anyio.CancelScope(shield=True):
            await store.release(task_id, actor="alice")

    await worker()

    tasks = await store.list_tasks()
    assert tasks[0].status == TaskStatus.PENDING


@pytest.mark.anyio
async def test_another_can_claim_after_release(
    store: InMemoryTaskListStore,
) -> None:
    entry = TaskEntry(title="Shared", created_by="lead")
    task_id = await store.add(entry, actor="lead")

    await store.claim(task_id=task_id, teammate="alice")
    await store.release(task_id, actor="alice")

    claimed = await store.claim(task_id=task_id, teammate="bob")
    assert claimed is not None
    assert claimed.claimed_by == "bob"


@pytest.mark.anyio
async def test_release_idempotent(
    store: InMemoryTaskListStore,
) -> None:
    entry = TaskEntry(title="Idempotent", created_by="lead")
    task_id = await store.add(entry, actor="lead")

    r1 = await store.release(task_id, actor="alice")
    assert r1.status == TaskStatus.PENDING

    r2 = await store.release(task_id, actor="alice")
    assert r2.status == TaskStatus.PENDING


@pytest.mark.anyio
async def test_cancellation_shield_prevents_leak(
    store: InMemoryTaskListStore,
) -> None:
    entry = TaskEntry(title="Shield test", created_by="lead")
    task_id = await store.add(entry, actor="lead")

    async def task_worker(name: str) -> None:
        claimed = await store.claim(task_id=task_id, teammate=name)
        if claimed is None:
            return
        try:
            with anyio.move_on_after(0.05):
                await anyio.sleep(10)
        except anyio.get_cancelled_exc_class():
            with anyio.CancelScope(shield=True):
                await store.release(task_id, actor=name)
            raise

    async with anyio.create_task_group() as tg:
        tg.start_soon(task_worker, "alice")
        await anyio.sleep(0.02)
        tg.cancel_scope.cancel()

    tasks = await store.list_tasks()
    pending = [t for t in tasks if t.status == TaskStatus.PENDING]
    assert len(pending) == 1
