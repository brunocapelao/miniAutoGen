"""Team task list tools for teammates to interact with the shared kanban board.

Builds 6 ToolDefinitions and handlers that wrap a TaskListStore.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from miniautogen.core.contracts.team_task import (
    ConfigurationError,
    StateConsistencyError,
    TaskEntry,
    TaskFilter,
    TaskStatus,
)
from miniautogen.core.contracts.tool import ToolResult
from miniautogen.core.contracts.tool_registry import ToolDefinition
from miniautogen.core.runtime.tool_registry import ToolHandler


def build_team_task_tools(
    store: Any,
    agent_name: str,
) -> list[tuple[ToolDefinition, ToolHandler]]:
    return [
        (_task_add_def(), _make_task_add_handler(store, agent_name)),
        (_task_list_def(), _make_task_list_handler(store)),
        (_task_claim_def(), _make_task_claim_handler(store, agent_name)),
        (_task_complete_def(), _make_task_complete_handler(store, agent_name)),
        (_task_fail_def(), _make_task_fail_handler(store, agent_name)),
        (_task_view_def(), _make_task_view_handler(store)),
    ]


def _task_add_def() -> ToolDefinition:
    return ToolDefinition(
        name="task_add",
        description="Add a new task to the shared team task list.",
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Task title"},
                "description": {"type": "string", "description": "Optional description"},
                "assigned_to": {"type": "string", "description": "Optional teammate to assign to"},
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional labels for filtering",
                },
                "depends_on": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Task IDs this task depends on",
                },
            },
            "required": ["title"],
        },
    )


def _make_task_add_handler(store: Any, agent_name: str) -> ToolHandler:
    async def handler(params: dict[str, Any]) -> ToolResult:
        title = params.get("title", "")
        if not title:
            return ToolResult(success=False, error="title is required")
        entry = TaskEntry(
            title=title,
            description=params.get("description"),
            assigned_to=params.get("assigned_to"),
            labels=params.get("labels") or [],
            depends_on=params.get("depends_on") or [],
            created_by=agent_name,
            created_at=datetime.now(),
        )
        try:
            task_id = await store.add(entry, actor=agent_name)
        except ConfigurationError as exc:
            return ToolResult(success=False, error=str(exc))
        return ToolResult(success=True, output={"task_id": task_id})

    return handler


def _task_list_def() -> ToolDefinition:
    return ToolDefinition(
        name="task_list",
        description="List tasks from the shared team task list with optional filters.",
        parameters={
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filter by status: pending, in_progress, completed, failed",
                },
                "assigned_to": {"type": "string", "description": "Filter by assigned teammate"},
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by labels (ANY match)",
                },
            },
        },
    )


def _make_task_list_handler(store: Any) -> ToolHandler:
    async def handler(params: dict[str, Any]) -> ToolResult:
        status_str = params.get("status")
        status: TaskStatus | None = None
        if status_str:
            try:
                status = TaskStatus(status_str)
            except ValueError:
                return ToolResult(success=False, error=f"Invalid status: {status_str}")
        task_filter = TaskFilter(
            status=status,
            assigned_to=params.get("assigned_to"),
            labels=params.get("labels") or [],
        )
        tasks = await store.list_tasks(filter=task_filter)
        return ToolResult(
            success=True,
            output={
                "tasks": [
                    t.model_dump(mode="json", exclude_none=True) for t in tasks
                ]
            },
        )

    return handler


def _task_claim_def() -> ToolDefinition:
    return ToolDefinition(
        name="task_claim",
        description="Claim a task by ID or claim the next available PENDING task matching labels.",
        parameters={
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Optional specific task ID to claim"},
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Claim first PENDING task matching these labels",
                },
            },
        },
    )


def _make_task_claim_handler(store: Any, agent_name: str) -> ToolHandler:
    async def handler(params: dict[str, Any]) -> ToolResult:
        task_id = params.get("task_id")
        labels = params.get("labels") or []
        entry = await store.claim(task_id, teammate=agent_name, labels=labels)
        if entry is None:
            return ToolResult(success=True, output={"claimed": False})
        return ToolResult(
            success=True,
            output={
                "claimed": True,
                "task": entry.model_dump(mode="json", exclude_none=True),
            },
        )

    return handler


def _task_complete_def() -> ToolDefinition:
    return ToolDefinition(
        name="task_complete",
        description="Mark a claimed task as completed with a summary.",
        parameters={
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task ID to mark as completed"},
                "summary": {"type": "string", "description": "Summary of the completed work"},
            },
            "required": ["task_id", "summary"],
        },
    )


def _make_task_complete_handler(store: Any, agent_name: str) -> ToolHandler:
    async def handler(params: dict[str, Any]) -> ToolResult:
        task_id = params.get("task_id", "")
        summary = params.get("summary", "")
        if not task_id:
            return ToolResult(success=False, error="task_id is required")
        try:
            entry = await store.update_status(
                task_id, TaskStatus.COMPLETED, summary=summary, actor=agent_name
            )
        except StateConsistencyError as exc:
            return ToolResult(success=False, error=str(exc))
        except KeyError:
            return ToolResult(success=False, error=f"Task not found: {task_id}")
        return ToolResult(
            success=True,
            output={"task": entry.model_dump(mode="json", exclude_none=True)},
        )

    return handler


def _task_fail_def() -> ToolDefinition:
    return ToolDefinition(
        name="task_fail",
        description="Mark a claimed task as failed with a reason.",
        parameters={
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task ID to mark as failed"},
                "reason": {"type": "string", "description": "Reason for failure"},
            },
            "required": ["task_id", "reason"],
        },
    )


def _make_task_fail_handler(store: Any, agent_name: str) -> ToolHandler:
    async def handler(params: dict[str, Any]) -> ToolResult:
        task_id = params.get("task_id", "")
        reason = params.get("reason", "")
        if not task_id:
            return ToolResult(success=False, error="task_id is required")
        try:
            entry = await store.update_status(
                task_id, TaskStatus.FAILED, summary=reason, actor=agent_name
            )
        except StateConsistencyError as exc:
            return ToolResult(success=False, error=str(exc))
        except KeyError:
            return ToolResult(success=False, error=f"Task not found: {task_id}")
        return ToolResult(
            success=True,
            output={"task": entry.model_dump(mode="json", exclude_none=True)},
        )

    return handler


def _task_view_def() -> ToolDefinition:
    return ToolDefinition(
        name="task_view",
        description="View a single task by ID.",
        parameters={
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task ID to view"},
            },
            "required": ["task_id"],
        },
    )


def _make_task_view_handler(store: Any) -> ToolHandler:
    async def handler(params: dict[str, Any]) -> ToolResult:
        task_id = params.get("task_id", "")
        if not task_id:
            return ToolResult(success=False, error="task_id is required")
        try:
            result = await store.get(task_id)
        except KeyError:
            return ToolResult(success=False, error=f"Task not found: {task_id}")
        if result is None:
            return ToolResult(success=False, error=f"Task not found: {task_id}")
        return ToolResult(success=True, output={"task": result})

    return handler
