"""In-memory task list store for team kanban boards.

Implements TaskListStore domain API on top of StoreProtocol surface.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import anyio

from miniautogen.core.contracts.team_task import (
    ConfigurationError,
    StateConsistencyError,
    TaskEntry,
    TaskFilter,
    TaskStatus,
    is_valid_transition,
)
from miniautogen.core.events.types import EventType


def _event_for(status: TaskStatus) -> EventType:
    mapping = {
        TaskStatus.COMPLETED: EventType.TASK_COMPLETED,
        TaskStatus.FAILED: EventType.TASK_FAILED,
        TaskStatus.CANCELLED: EventType.TASK_RELEASED,
    }
    return mapping.get(status, EventType.TASK_RELEASED)


def _matches(entry: TaskEntry, filter: TaskFilter | None) -> bool:  # noqa: A002
    if filter is None:
        return True
    if filter.status is not None and entry.status != filter.status:
        return False
    if filter.assigned_to is not None and entry.assigned_to != filter.assigned_to:
        return False
    if filter.labels:
        if not any(label in entry.labels for label in filter.labels):
            return False
    return True


class InMemoryTaskListStore:
    """Per-team-run kanban store. Satisfies StoreProtocol structurally."""

    def __init__(
        self,
        team_run_id: str,
        event_sink: Any,
    ) -> None:
        self._team_run_id = team_run_id
        self._sink = event_sink
        self._tasks: dict[str, TaskEntry] = {}
        self._board_lock = anyio.Lock()
        self._completion_events: dict[str, anyio.Event] = {}

    # ---- StoreProtocol surface ----

    async def save(self, key: str, payload: dict[str, Any]) -> None:
        async with self._board_lock:
            self._tasks[key] = TaskEntry(**payload)

    async def get(self, key: str) -> dict[str, Any] | None:
        async with self._board_lock:
            entry = self._tasks.get(key)
            if entry is None:
                return None
            return entry.model_dump(mode="json")

    async def exists(self, key: str) -> bool:
        async with self._board_lock:
            return key in self._tasks

    async def delete(self, key: str) -> bool:
        async with self._board_lock:
            if key not in self._tasks:
                return False
            del self._tasks[key]
            self._completion_events.pop(key, None)
            return True

    # ---- Domain API ----

    async def add(
        self, entry: TaskEntry, *, actor: str
    ) -> str:
        async with self._board_lock:
            self._validate_no_cycle(entry, list(self._tasks.values()))
            self._tasks[entry.id] = entry
            self._completion_events[entry.id] = anyio.Event()
        await self._emit(EventType.TASK_ADDED, entry, actor)
        return entry.id

    async def list_tasks(
        self, filter: TaskFilter | None = None  # noqa: A002
    ) -> list[TaskEntry]:
        async with self._board_lock:
            return [
                entry.model_copy(deep=True)
                for entry in self._tasks.values()
                if _matches(entry, filter)
            ]

    async def claim(
        self,
        task_id: str | None,
        teammate: str,
        labels: list[str] | None = None,
    ) -> TaskEntry | None:
        async with self._board_lock:
            entry = self._pick_claimable(task_id, teammate, labels)
            if entry is None:
                return None
            if not self._deps_satisfied(entry):
                await self._emit(
                    EventType.TASK_BLOCKED_BY_DEPENDENCY, entry, teammate
                )
                return None
            entry.status = TaskStatus.IN_PROGRESS
            entry.claimed_by = teammate
            entry.claimed_at = datetime.now(timezone.utc)
            claimed = entry.model_copy(deep=True)
        await self._emit(EventType.TASK_CLAIMED, claimed, teammate)
        return claimed

    async def update_status(
        self,
        task_id: str,
        status: TaskStatus,
        summary: str | None = None,
        *,
        actor: str,
    ) -> TaskEntry:
        async with self._board_lock:
            entry = self._tasks[task_id]
            if not is_valid_transition(entry.status, status):
                raise StateConsistencyError(
                    f"Invalid transition: {entry.status.value} -> {status.value}"
                )
            if status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                if entry.claimed_by != actor:
                    raise StateConsistencyError(
                        "only claimer may complete/fail"
                    )
            entry.status = status
            entry.result_summary = summary
            entry.finished_at = datetime.now(timezone.utc)
            done = self._completion_events[task_id]
            snapshot = entry.model_copy(deep=True)
        done.set()
        await self._emit(_event_for(status), snapshot, actor)
        return snapshot

    async def release(
        self, task_id: str, *, actor: str
    ) -> TaskEntry:
        async with self._board_lock:
            entry = self._tasks[task_id]
            if entry.status != TaskStatus.IN_PROGRESS:
                return entry.model_copy(deep=True)
            entry.status = TaskStatus.PENDING
            entry.claimed_by = None
            entry.claimed_at = None
            snapshot = entry.model_copy(deep=True)
        await self._emit(EventType.TASK_RELEASED, snapshot, actor)
        return snapshot

    async def wait_for(
        self,
        task_id: str,
        target: TaskStatus,
        timeout: float | None = None,
    ) -> TaskEntry:
        with anyio.fail_after(timeout):
            while True:
                async with self._board_lock:
                    entry = self._tasks[task_id]
                    if entry.status == target:
                        return entry.model_copy(deep=True)
                    evt = self._completion_events[task_id]
                await evt.wait()

    # ---- Internal helpers ----

    def _pick_claimable(
        self,
        task_id: str | None,
        teammate: str,
        labels: list[str] | None,
    ) -> TaskEntry | None:
        if task_id is not None:
            entry = self._tasks.get(task_id)
            if entry is None:
                return None
            if entry.status != TaskStatus.PENDING:
                return None
            if entry.assigned_to is not None and entry.assigned_to != teammate:
                return None
            if labels:
                if not any(label in entry.labels for label in labels):
                    return None
            return entry

        candidates = [
            e
            for e in self._tasks.values()
            if e.status == TaskStatus.PENDING
        ]
        if labels:
            candidates = [
                e
                for e in candidates
                if any(label in e.labels for label in labels)
            ]
        if not candidates:
            return None
        return candidates[0]

    def _deps_satisfied(self, entry: TaskEntry) -> bool:
        for dep_id in entry.depends_on:
            dep = self._tasks.get(dep_id)
            if dep is None:
                continue
            if dep.status != TaskStatus.COMPLETED:
                return False
        return True

    def _validate_no_cycle(
        self, new_entry: TaskEntry, existing: list[TaskEntry]
    ) -> None:
        all_tasks = {e.id: e for e in existing}
        all_tasks[new_entry.id] = new_entry
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {}

        def dfs(task_id: str) -> None:
            color[task_id] = GRAY
            entry = all_tasks.get(task_id)
            if entry:
                for dep_id in entry.depends_on:
                    if dep_id not in all_tasks:
                        continue
                    if color.get(dep_id) == GRAY:
                        raise ConfigurationError(
                            f"Cycle detected: task {dep_id} depends on {task_id}"
                        )
                    if color.get(dep_id, WHITE) == WHITE:
                        dfs(dep_id)
            color[task_id] = BLACK

        for tid in all_tasks:
            if color.get(tid, WHITE) == WHITE:
                dfs(tid)

    async def _emit(
        self,
        event_type: EventType,
        entry: TaskEntry,
        actor: str,
    ) -> None:
        from miniautogen.core.contracts.events import ExecutionEvent

        event = ExecutionEvent(
            type=event_type.value,
            timestamp=datetime.now(timezone.utc),
            run_id=self._team_run_id,
            correlation_id=self._team_run_id,
            scope="team_task_list",
            payload={
                "task_id": entry.id,
                "team_run_id": self._team_run_id,
                "actor": actor,
                "title": entry.title,
                "status": entry.status.value,
                "claimed_by": entry.claimed_by,
                "depends_on": list(entry.depends_on),
            },
        )
        await self._sink.publish(event)
