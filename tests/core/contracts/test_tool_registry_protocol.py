"""Tests for ToolRegistryProtocol, ToolDefinition, and ToolCall."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from miniautogen.core.contracts.tool_registry import (
    ToolCall,
    ToolDefinition,
    ToolRegistryProtocol,
)
from miniautogen.core.contracts.tool import ToolProtocol, ToolResult


# ---------------------------------------------------------------------------
# Fake implementations
# ---------------------------------------------------------------------------


class _FakeTool:
    """Satisfies ToolProtocol structurally."""

    @property
    def name(self) -> str:
        return "fake_tool"

    @property
    def description(self) -> str:
        return "A fake tool for testing."

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        return ToolResult(success=True, output=params)


class _FakeRegistry:
    """Satisfies ToolRegistryProtocol structurally."""

    def __init__(self) -> None:
        self._tools: dict[str, _FakeTool] = {"fake_tool": _FakeTool()}

    def list_tools(self) -> list[ToolDefinition]:
        return [ToolDefinition(name="fake_tool", description="A fake tool for testing.")]

    async def execute_tool(self, call: ToolCall) -> ToolResult:
        tool = self._tools.get(call.tool_name)
        if tool is None:
            return ToolResult(success=False, error=f"Tool '{call.tool_name}' not found")
        return await tool.execute(call.params)

    def has_tool(self, name: str) -> bool:
        return name in self._tools


class _BrokenRegistry:
    """Does NOT satisfy ToolRegistryProtocol — missing has_tool()."""

    def list_tools(self) -> list[ToolDefinition]:
        return []

    async def execute_tool(self, call: ToolCall) -> ToolResult:
        return ToolResult(success=True, output=None)


# ---------------------------------------------------------------------------
# ToolDefinition tests
# ---------------------------------------------------------------------------


def test_tool_definition_minimal_fields() -> None:
    defn = ToolDefinition(name="my_tool", description="Does something")
    assert defn.name == "my_tool"
    assert defn.description == "Does something"
    assert defn.parameters is None


def test_tool_definition_with_json_schema_parameters() -> None:
    schema = {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    }
    defn = ToolDefinition(name="search", description="Search tool", parameters=schema)
    assert defn.parameters == schema


def test_tool_definition_requires_name() -> None:
    with pytest.raises(ValidationError):
        ToolDefinition(description="No name")  # type: ignore[call-arg]


def test_tool_definition_requires_description() -> None:
    with pytest.raises(ValidationError):
        ToolDefinition(name="no_description")  # type: ignore[call-arg]


def test_tool_definition_from_protocol() -> None:
    tool = _FakeTool()
    defn = ToolDefinition.from_protocol(tool)
    assert defn.name == tool.name
    assert defn.description == tool.description
    assert defn.parameters is None


def test_tool_definition_serialization_roundtrip() -> None:
    original = ToolDefinition(name="my_tool", description="Does something")
    data = original.model_dump()
    restored = ToolDefinition.model_validate(data)
    assert restored == original


# ---------------------------------------------------------------------------
# ToolCall tests
# ---------------------------------------------------------------------------


def test_tool_call_minimal_fields() -> None:
    call = ToolCall(tool_name="my_tool", call_id="call-001")
    assert call.tool_name == "my_tool"
    assert call.call_id == "call-001"
    assert call.params == {}


def test_tool_call_with_params() -> None:
    call = ToolCall(tool_name="search", call_id="call-002", params={"query": "hello"})
    assert call.params == {"query": "hello"}


def test_tool_call_requires_tool_name() -> None:
    with pytest.raises(ValidationError):
        ToolCall(call_id="call-003")  # type: ignore[call-arg]


def test_tool_call_requires_call_id() -> None:
    with pytest.raises(ValidationError):
        ToolCall(tool_name="my_tool")  # type: ignore[call-arg]


def test_tool_call_serialization_roundtrip() -> None:
    original = ToolCall(tool_name="calc", call_id="call-004", params={"x": 1, "y": 2})
    data = original.model_dump()
    restored = ToolCall.model_validate(data)
    assert restored == original


# ---------------------------------------------------------------------------
# ToolRegistryProtocol isinstance checks
# ---------------------------------------------------------------------------


def test_tool_registry_protocol_is_runtime_checkable() -> None:
    registry = _FakeRegistry()
    assert isinstance(registry, ToolRegistryProtocol)


def test_broken_registry_does_not_satisfy_protocol() -> None:
    registry = _BrokenRegistry()
    assert not isinstance(registry, ToolRegistryProtocol)


# ---------------------------------------------------------------------------
# Async execution via registry
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_registry_execute_tool_returns_tool_result() -> None:
    registry = _FakeRegistry()
    call = ToolCall(tool_name="fake_tool", call_id="call-100", params={"key": "value"})
    result = await registry.execute_tool(call)
    assert isinstance(result, ToolResult)
    assert result.success is True
    assert result.output == {"key": "value"}


@pytest.mark.anyio
async def test_registry_execute_missing_tool_returns_failure() -> None:
    registry = _FakeRegistry()
    call = ToolCall(tool_name="nonexistent", call_id="call-101")
    result = await registry.execute_tool(call)
    assert result.success is False
    assert result.error is not None


def test_registry_has_tool_returns_true_for_existing() -> None:
    registry = _FakeRegistry()
    assert registry.has_tool("fake_tool") is True


def test_registry_has_tool_returns_false_for_missing() -> None:
    registry = _FakeRegistry()
    assert registry.has_tool("nonexistent") is False


def test_registry_list_tools_returns_definitions() -> None:
    registry = _FakeRegistry()
    tools = registry.list_tools()
    assert len(tools) == 1
    assert isinstance(tools[0], ToolDefinition)
    assert tools[0].name == "fake_tool"
