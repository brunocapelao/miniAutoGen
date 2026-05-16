"""Tests for task dependency chain resolution in InMemoryTaskListStore."""

from __future__ import annotations

import anyio
import pytest

from miniautogen.core.contracts.team_task import (
    ConfigurationError,
    TaskEntry,
    TaskStatus,
)
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.runtime.team_task_list import InMemoryTaskListStore


@pytest.fixture
def store() -> InMemoryTaskListStore:
    return InMemoryTaskListStore(
        team_run_id="test-deps",
        event_sink=InMemoryEventSink(),
    )


@pytest.mark.anyio
async def test_task_with_unmet_dep_cannot_be_claimed(
    store: InMemoryTaskListStore,
) -> None:
    a = TaskEntry(title="Task A", created_by="lead")
    a_id = await store.add(a, actor="lead")

    b = TaskEntry(title="Task B", created_by="lead", depends_on=[a_id])
    b_id = await store.add(b, actor="lead")

    result = await store.claim(task_id=b_id, teammate="alice")
    assert result is None, "B should not be claimable before A is done"


@pytest.mark.anyio
async def test_task_becomes_claimable_after_dep_met(
    store: InMemoryTaskListStore,
) -> None:
    a = TaskEntry(title="Task A", created_by="lead")
    a_id = await store.add(a, actor="lead")
    b = TaskEntry(title="Task B", created_by="lead", depends_on=[a_id])
    b_id = await store.add(b, actor="lead")

    await store.claim(task_id=a_id, teammate="alice")
    await store.update_status(a_id, TaskStatus.COMPLETED, summary="done", actor="alice")

    result = await store.claim(task_id=b_id, teammate="bob")
    assert result is not None
    assert result.status == TaskStatus.IN_PROGRESS


@pytest.mark.anyio
async def test_transitive_dependency_chain(
    store: InMemoryTaskListStore,
) -> None:
    a = TaskEntry(title="Task A", created_by="lead")
    a_id = await store.add(a, actor="lead")
    b = TaskEntry(title="Task B", created_by="lead", depends_on=[a_id])
    b_id = await store.add(b, actor="lead")
    c = TaskEntry(title="Task C", created_by="lead", depends_on=[b_id])
    c_id = await store.add(c, actor="lead")

    assert await store.claim(task_id=b_id, teammate="alice") is None
    assert await store.claim(task_id=c_id, teammate="alice") is None

    await store.claim(task_id=a_id, teammate="alice")
    await store.update_status(a_id, TaskStatus.COMPLETED, summary="done", actor="alice")

    assert await store.claim(task_id=b_id, teammate="bob") is not None
    await store.update_status(b_id, TaskStatus.COMPLETED, summary="done", actor="bob")

    assert await store.claim(task_id=c_id, teammate="charlie") is not None


@pytest.mark.anyio
async def test_cross_dependency_cycle_detected(
    store: InMemoryTaskListStore,
) -> None:
    a = TaskEntry(
        title="A",
        created_by="lead",
        id="a",
        depends_on=["future-task"],
    )
    a_id = await store.add(a, actor="lead")

    future = TaskEntry(
        title="Future",
        created_by="lead",
        id="future-task",
        depends_on=[a_id],
    )
    with pytest.raises(ConfigurationError, match="Cycle"):
        await store.add(future, actor="lead")


@pytest.mark.anyio
async def test_failed_dep_blocks_downstream_forever(
    store: InMemoryTaskListStore,
) -> None:
    a = TaskEntry(title="Task A", created_by="lead")
    a_id = await store.add(a, actor="lead")
    b = TaskEntry(title="Task B", created_by="lead", depends_on=[a_id])
    b_id = await store.add(b, actor="lead")

    await store.claim(task_id=a_id, teammate="alice")
    await store.update_status(a_id, TaskStatus.FAILED, summary="oops", actor="alice")

    with pytest.raises(TimeoutError):
        with anyio.fail_after(0.3):
            await store.wait_for(b_id, TaskStatus.COMPLETED)


@pytest.mark.anyio
async def test_cycle_detected_on_add(store: InMemoryTaskListStore) -> None:
    cycle_id = "self-cycle"
    cycle_entry = TaskEntry(
        title="Self-cycle",
        created_by="lead",
        depends_on=[cycle_id],
        id=cycle_id,
    )

    with pytest.raises(ConfigurationError, match="Cycle"):
        await store.add(cycle_entry, actor="lead")
