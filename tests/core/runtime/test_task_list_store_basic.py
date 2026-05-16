"""Tests for InMemoryTaskListStore basic CRUD and status transitions."""

from __future__ import annotations

import anyio
import pytest

from miniautogen.core.contracts.store import StoreProtocol
from miniautogen.core.contracts.team_task import (
    StateConsistencyError,
    TaskEntry,
    TaskFilter,
    TaskStatus,
)
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.runtime.team_task_list import InMemoryTaskListStore


@pytest.fixture
def store() -> InMemoryTaskListStore:
    sink = InMemoryEventSink()
    return InMemoryTaskListStore(
        team_run_id="test-run-1",
        event_sink=sink,
    )


@pytest.mark.anyio
async def test_add_task(store: InMemoryTaskListStore) -> None:
    entry = TaskEntry(
        title="Test task",
        description="A test",
        created_by="lead",
    )
    task_id = await store.add(entry, actor="lead")
    assert task_id == entry.id


@pytest.mark.anyio
async def test_list_tasks(store: InMemoryTaskListStore) -> None:
    e1 = TaskEntry(title="Task 1", created_by="lead")
    e2 = TaskEntry(title="Task 2", created_by="lead", labels=["urgent"])
    await store.add(e1, actor="lead")
    await store.add(e2, actor="lead")

    all_tasks = await store.list_tasks()
    assert len(all_tasks) == 2

    filtered = await store.list_tasks(filter=TaskFilter(labels=["urgent"]))
    assert len(filtered) == 1
    assert filtered[0].title == "Task 2"


@pytest.mark.anyio
async def test_claim_and_update_status(store: InMemoryTaskListStore) -> None:
    entry = TaskEntry(title="Claimable", created_by="lead")
    task_id = await store.add(entry, actor="lead")

    claimed = await store.claim(task_id=task_id, teammate="alice")
    assert claimed is not None
    assert claimed.status == TaskStatus.IN_PROGRESS
    assert claimed.claimed_by == "alice"

    completed = await store.update_status(
        task_id, TaskStatus.COMPLETED, summary="done", actor="alice"
    )
    assert completed.status == TaskStatus.COMPLETED
    assert completed.result_summary == "done"


@pytest.mark.anyio
async def test_idempotent_same_status(store: InMemoryTaskListStore) -> None:
    entry = TaskEntry(title="Test", created_by="lead")
    task_id = await store.add(entry, actor="lead")
    await store.claim(task_id=task_id, teammate="alice")
    await store.update_status(
        task_id, TaskStatus.COMPLETED, summary="done", actor="alice"
    )
    result = await store.update_status(
        task_id, TaskStatus.COMPLETED, summary="still done", actor="alice"
    )
    assert result.status == TaskStatus.COMPLETED


@pytest.mark.anyio
async def test_invalid_transition_raises(store: InMemoryTaskListStore) -> None:
    entry = TaskEntry(title="Test", created_by="lead")
    task_id = await store.add(entry, actor="lead")
    await store.claim(task_id=task_id, teammate="alice")
    await store.update_status(
        task_id, TaskStatus.COMPLETED, summary="done", actor="alice"
    )

    with pytest.raises(StateConsistencyError):
        await store.update_status(
            task_id, TaskStatus.IN_PROGRESS, actor="alice"
        )


@pytest.mark.anyio
async def test_release_returns_to_pending(store: InMemoryTaskListStore) -> None:
    entry = TaskEntry(title="Test", created_by="lead")
    task_id = await store.add(entry, actor="lead")
    await store.claim(task_id=task_id, teammate="alice")
    released = await store.release(task_id, actor="alice")
    assert released.status == TaskStatus.PENDING
    assert released.claimed_by is None


@pytest.mark.anyio
async def test_storeprotocol_satisfied(store: InMemoryTaskListStore) -> None:
    assert isinstance(store, StoreProtocol)


@pytest.mark.anyio
async def test_storeprotocol_save_get_exists_delete(
    store: InMemoryTaskListStore,
) -> None:
    entry = TaskEntry(title="Store test", created_by="lead")
    task_id = await store.add(entry, actor="lead")

    saved = await store.get(task_id)
    assert saved is not None
    assert saved["title"] == "Store test"

    assert await store.exists(task_id) is True

    deleted = await store.delete(task_id)
    assert deleted is True
    assert await store.exists(task_id) is False


@pytest.mark.anyio
async def test_claim_by_non_claimer_fails(store: InMemoryTaskListStore) -> None:
    entry = TaskEntry(title="Test", created_by="lead")
    task_id = await store.add(entry, actor="lead")
    await store.claim(task_id=task_id, teammate="alice")
    with pytest.raises(StateConsistencyError, match="only claimer"):
        await store.update_status(
            task_id, TaskStatus.COMPLETED, summary="hacked", actor="bob"
        )


@pytest.mark.anyio
async def test_wait_for_completion(store: InMemoryTaskListStore) -> None:
    entry = TaskEntry(title="Waitable", created_by="lead")
    task_id = await store.add(entry, actor="lead")

    async def completer() -> None:
        await store.claim(task_id=task_id, teammate="alice")
        await store.update_status(
            task_id, TaskStatus.COMPLETED, summary="done", actor="alice"
        )

    async with anyio.create_task_group() as tg:
        tg.start_soon(completer)
        result = await store.wait_for(task_id, TaskStatus.COMPLETED)

    assert result.status == TaskStatus.COMPLETED
