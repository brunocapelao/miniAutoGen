"""Tests for the 6 team task tools registered via build_team_task_tools."""

from __future__ import annotations

import pytest

from miniautogen.core.contracts.tool_registry import ToolCall
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.runtime.team_task_list import InMemoryTaskListStore
from miniautogen.core.runtime.team_task_tools import build_team_task_tools
from miniautogen.core.runtime.tool_registry import InMemoryToolRegistry


@pytest.fixture
def store() -> InMemoryTaskListStore:
    return InMemoryTaskListStore(
        team_run_id="test-tools",
        event_sink=InMemoryEventSink(),
    )


@pytest.fixture
def registry(store: InMemoryTaskListStore) -> InMemoryToolRegistry:
    reg = InMemoryToolRegistry()
    for definition, handler in build_team_task_tools(store, "alice"):
        reg.register(definition, handler)
    return reg


@pytest.mark.anyio
async def test_task_add_tool(registry: InMemoryToolRegistry) -> None:
    result = await registry.execute_tool(
        ToolCall(
            tool_name="task_add",
            call_id="1",
            params={"title": "New task", "description": "Test"},
        )
    )
    assert result.success
    assert "task_id" in result.output


@pytest.mark.anyio
async def test_task_list_tool(registry: InMemoryToolRegistry) -> None:
    await registry.execute_tool(
        ToolCall(
            tool_name="task_add",
            call_id="1",
            params={"title": "Task 1"},
        )
    )
    result = await registry.execute_tool(
        ToolCall(tool_name="task_list", call_id="2", params={})
    )
    assert result.success
    assert len(result.output["tasks"]) == 1


@pytest.mark.anyio
async def test_task_claim_tool(registry: InMemoryToolRegistry) -> None:
    add_result = await registry.execute_tool(
        ToolCall(
            tool_name="task_add",
            call_id="1",
            params={"title": "Claimable task"},
        )
    )
    task_id = add_result.output["task_id"]

    claim_result = await registry.execute_tool(
        ToolCall(
            tool_name="task_claim",
            call_id="2",
            params={"task_id": task_id},
        )
    )
    assert claim_result.success
    assert claim_result.output["claimed"] is True


@pytest.mark.anyio
async def test_task_complete_tool(registry: InMemoryToolRegistry) -> None:
    add_result = await registry.execute_tool(
        ToolCall(
            tool_name="task_add",
            call_id="1",
            params={"title": "Doable task"},
        )
    )
    task_id = add_result.output["task_id"]
    await registry.execute_tool(
        ToolCall(
            tool_name="task_claim",
            call_id="2",
            params={"task_id": task_id},
        )
    )
    complete_result = await registry.execute_tool(
        ToolCall(
            tool_name="task_complete",
            call_id="3",
            params={"task_id": task_id, "summary": "All done"},
        )
    )
    assert complete_result.success
    assert complete_result.output["task"]["status"] == "completed"


@pytest.mark.anyio
async def test_task_fail_tool(registry: InMemoryToolRegistry) -> None:
    add_result = await registry.execute_tool(
        ToolCall(
            tool_name="task_add",
            call_id="1",
            params={"title": "Failable task"},
        )
    )
    task_id = add_result.output["task_id"]
    await registry.execute_tool(
        ToolCall(
            tool_name="task_claim",
            call_id="2",
            params={"task_id": task_id},
        )
    )
    fail_result = await registry.execute_tool(
        ToolCall(
            tool_name="task_fail",
            call_id="3",
            params={"task_id": task_id, "reason": "Not feasible"},
        )
    )
    assert fail_result.success
    assert fail_result.output["task"]["status"] == "failed"


@pytest.mark.anyio
async def test_task_view_tool(registry: InMemoryToolRegistry) -> None:
    add_result = await registry.execute_tool(
        ToolCall(
            tool_name="task_add",
            call_id="1",
            params={"title": "Viewable task"},
        )
    )
    task_id = add_result.output["task_id"]
    view_result = await registry.execute_tool(
        ToolCall(
            tool_name="task_view",
            call_id="2",
            params={"task_id": task_id},
        )
    )
    assert view_result.success
    assert view_result.output["task"]["title"] == "Viewable task"


@pytest.mark.anyio
async def test_complete_by_non_claimer_fails(
    store: InMemoryTaskListStore,
) -> None:
    alice_reg = InMemoryToolRegistry()
    for definition, handler in build_team_task_tools(store, "alice"):
        alice_reg.register(definition, handler)

    add_result = await alice_reg.execute_tool(
        ToolCall(
            tool_name="task_add",
            call_id="1",
            params={"title": "Protected task"},
        )
    )
    task_id = add_result.output["task_id"]
    await alice_reg.execute_tool(
        ToolCall(
            tool_name="task_claim",
            call_id="2",
            params={"task_id": task_id},
        )
    )

    bob_reg = InMemoryToolRegistry()
    for definition, handler in build_team_task_tools(store, "bob"):
        bob_reg.register(definition, handler)

    result = await bob_reg.execute_tool(
        ToolCall(
            tool_name="task_complete",
            call_id="3",
            params={"task_id": task_id, "summary": "hacked"},
        )
    )
    assert not result.success
