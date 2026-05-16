"""Tests for label-based task filtering in InMemoryTaskListStore."""

from __future__ import annotations

import pytest

from miniautogen.core.contracts.team_task import TaskEntry
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.runtime.team_task_list import InMemoryTaskListStore


@pytest.fixture
def store() -> InMemoryTaskListStore:
    return InMemoryTaskListStore(
        team_run_id="test-labels",
        event_sink=InMemoryEventSink(),
    )


@pytest.mark.anyio
async def test_claim_by_label_picks_matching(
    store: InMemoryTaskListStore,
) -> None:
    legal = TaskEntry(title="Legal doc", created_by="lead", labels=["legal"])
    sec = TaskEntry(title="Security audit", created_by="lead", labels=["security"])
    await store.add(legal, actor="lead")
    await store.add(sec, actor="lead")

    result = await store.claim(None, teammate="alice", labels=["legal"])
    assert result is not None
    assert result.title == "Legal doc"


@pytest.mark.anyio
async def test_claim_by_label_ignores_non_matching(
    store: InMemoryTaskListStore,
) -> None:
    sec = TaskEntry(title="Security audit", created_by="lead", labels=["security"])
    await store.add(sec, actor="lead")

    result = await store.claim(None, teammate="alice", labels=["legal"])
    assert result is None


@pytest.mark.anyio
async def test_claim_by_labels_any_match(
    store: InMemoryTaskListStore,
) -> None:
    legal = TaskEntry(title="Legal doc", created_by="lead", labels=["legal"])
    sec = TaskEntry(title="Security audit", created_by="lead", labels=["security"])
    await store.add(legal, actor="lead")
    await store.add(sec, actor="lead")

    result = await store.claim(
        None, teammate="alice", labels=["legal", "security"]
    )
    assert result is not None


@pytest.mark.anyio
async def test_task_list_filters_by_labels(
    store: InMemoryTaskListStore,
) -> None:
    from miniautogen.core.contracts.team_task import TaskFilter

    legal = TaskEntry(title="Legal doc", created_by="lead", labels=["legal"])
    sec = TaskEntry(title="Security", created_by="lead", labels=["security"])
    await store.add(legal, actor="lead")
    await store.add(sec, actor="lead")

    result = await store.list_tasks(filter=TaskFilter(labels=["security"]))
    assert len(result) == 1
    assert result[0].title == "Security"
