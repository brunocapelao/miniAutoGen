"""Team task list contracts for shared kanban between teammates.

Defines Status, TaskEntry, TaskFilter and config types for Spec 016.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


_VALID_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED},
    TaskStatus.IN_PROGRESS: {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.PENDING},
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: set(),
    TaskStatus.CANCELLED: set(),
}


def is_valid_transition(from_: TaskStatus, to: TaskStatus) -> bool:
    if from_ == to:
        return True
    return to in _VALID_TRANSITIONS.get(from_, set())


def validate_transition(from_: TaskStatus, to: TaskStatus) -> None:
    if not is_valid_transition(from_, to):
        raise StateConsistencyError(
            f"Invalid transition: {from_.value} -> {to.value}"
        )


class StateConsistencyError(Exception):
    """Raised when a task status transition is invalid."""


class ConfigurationError(Exception):
    """Raised when task DAG contains cycles or other config issues."""


class TaskEntry(BaseModel):
    model_config = {"frozen": False}

    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    description: str | None = None
    assigned_to: str | None = None
    labels: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    created_by: str
    claimed_by: str | None = None
    result_summary: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    claimed_at: datetime | None = None
    finished_at: datetime | None = None

    def model_copy(self, **kwargs: Any) -> TaskEntry:
        return super().model_copy(**kwargs)


class TaskFilter(BaseModel):
    status: TaskStatus | None = None
    assigned_to: str | None = None
    labels: list[str] = Field(default_factory=list)


class TaskEntrySpec(BaseModel):
    title: str
    description: str | None = None
    assigned_to: str | None = None
    labels: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    id: str | None = None


class TaskListConfig(BaseModel):
    enabled: bool = False
    initial_tasks: list[TaskEntrySpec] = Field(default_factory=list)
    idle_threshold_seconds: float = 5.0
    poll_interval_ms: int = 200
