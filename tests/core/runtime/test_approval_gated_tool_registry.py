"""Tests for ApprovalGatedToolRegistry decorator."""

from __future__ import annotations

from typing import Any

import anyio
import pytest

from miniautogen.core.contracts.tool import ToolResult
from miniautogen.core.contracts.tool_registry import (
    ToolCall,
    ToolDefinition,
    ToolRegistryProtocol,
)
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.runtime.approval_gated_tool_registry import (
    ApprovalGatedToolRegistry,
)
from miniautogen.core.runtime.tool_registry import InMemoryToolRegistry


@pytest.fixture
def inner_registry() -> InMemoryToolRegistry:
    reg = InMemoryToolRegistry()
    reg.register(
        ToolDefinition(
            name="shell_command",
            description="Run a shell command",
            parameters={
                "type": "object",
                "properties": {"cmd": {"type": "string"}},
                "required": ["cmd"],
            },
        ),
        lambda params: ToolResult(success=True, output=f"ran: {params['cmd']}"),
    )
    reg.register(
        ToolDefinition(
            name="read_file",
            description="Read a file",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        ),
        lambda params: ToolResult(success=True, output=f"read: {params['path']}"),
    )
    return reg


@pytest.mark.anyio
async def test_granted_allows_execution(inner_registry: InMemoryToolRegistry) -> None:
    sink = InMemoryEventSink()
    approval_results: list[str] = []

    async def approval_tool(plan: str | dict) -> str:
        approval_results.append("granted")
        return "granted"

    gated = ApprovalGatedToolRegistry(
        inner=inner_registry,
        approval_tool=approval_tool,
        required_for={"shell_command"},
        agent_id="test_agent",
        event_sink=sink,
    )

    result = await gated.execute_tool(ToolCall(
        tool_name="shell_command",
        call_id="call-1",
        params={"cmd": "ls"},
    ))
    assert result.success is True
    assert result.output == "ran: ls"
    assert approval_results == ["granted"]


@pytest.mark.anyio
async def test_denied_blocks_execution(inner_registry: InMemoryToolRegistry) -> None:
    sink = InMemoryEventSink()
    approval_results: list[str] = []

    async def approval_tool(plan: str | dict) -> str:
        approval_results.append("denied")
        return "denied"

    gated = ApprovalGatedToolRegistry(
        inner=inner_registry,
        approval_tool=approval_tool,
        required_for={"shell_command"},
        agent_id="test_agent",
        event_sink=sink,
    )

    result = await gated.execute_tool(ToolCall(
        tool_name="shell_command",
        call_id="call-2",
        params={"cmd": "rm -rf /"},
    ))
    assert result.success is False
    assert "denied" in (result.error or "")
    assert approval_results == ["denied"]


@pytest.mark.anyio
async def test_unlisted_tool_skips_approval(inner_registry: InMemoryToolRegistry) -> None:
    sink = InMemoryEventSink()
    approval_results: list[str] = []

    async def approval_tool(plan: str | dict) -> str:
        approval_results.append("called")
        return "granted"

    gated = ApprovalGatedToolRegistry(
        inner=inner_registry,
        approval_tool=approval_tool,
        required_for={"shell_command"},
        agent_id="test_agent",
        event_sink=sink,
    )

    result = await gated.execute_tool(ToolCall(
        tool_name="read_file",
        call_id="call-3",
        params={"path": "/etc/passwd"},
    ))
    assert result.success is True
    assert approval_results == []


@pytest.mark.anyio
async def test_timeout_returns_error(inner_registry: InMemoryToolRegistry) -> None:
    sink = InMemoryEventSink()

    async def approval_tool(plan: str | dict) -> str:
        return "timeout"

    gated = ApprovalGatedToolRegistry(
        inner=inner_registry,
        approval_tool=approval_tool,
        required_for={"shell_command"},
        agent_id="test_agent",
        event_sink=sink,
    )

    result = await gated.execute_tool(ToolCall(
        tool_name="shell_command",
        call_id="call-4",
        params={"cmd": "danger"},
    ))
    assert result.success is False
    assert "timeout" in (result.error or "")


@pytest.mark.anyio
async def test_list_tools_delegates(inner_registry: InMemoryToolRegistry) -> None:
    sink = InMemoryEventSink()

    async def approval_tool(plan: str | dict) -> str:
        return "granted"

    gated = ApprovalGatedToolRegistry(
        inner=inner_registry,
        approval_tool=approval_tool,
        required_for={"shell_command"},
        agent_id="test_agent",
        event_sink=sink,
    )

    tools = gated.list_tools()
    names = {t.name for t in tools}
    assert "shell_command" in names
    assert "read_file" in names
