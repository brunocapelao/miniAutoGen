"""Tests for CompositeToolRegistry."""
from __future__ import annotations

import pytest

from miniautogen.core.contracts.tool import ToolResult
from miniautogen.core.contracts.tool_registry import (
    ToolCall,
    ToolDefinition,
    ToolRegistryProtocol,
)
from miniautogen.core.runtime.composite_tool_registry import CompositeToolRegistry


class FakeRegistry:
    """Simple in-memory ToolRegistryProtocol for testing."""

    def __init__(self, tools: dict[str, str]) -> None:
        # tools: {name: description}
        self._tools = {
            name: ToolDefinition(name=name, description=desc)
            for name, desc in tools.items()
        }

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    async def execute_tool(self, call: ToolCall) -> ToolResult:
        if call.tool_name in self._tools:
            return ToolResult(success=True, output=f"from-{self._tools[call.tool_name].description}")
        return ToolResult(success=False, error=f"Unknown tool: {call.tool_name}")


def test_implements_protocol():
    reg = CompositeToolRegistry([])
    assert isinstance(reg, ToolRegistryProtocol)


def test_list_tools_empty_registries():
    reg = CompositeToolRegistry([])
    assert reg.list_tools() == []


def test_list_tools_single_registry():
    r1 = FakeRegistry({"tool_a": "Registry A"})
    reg = CompositeToolRegistry([r1])
    tools = reg.list_tools()
    assert len(tools) == 1
    assert tools[0].name == "tool_a"


def test_list_tools_deduplicates_shadowed_tools():
    r1 = FakeRegistry({"tool_a": "A1", "tool_b": "B1"})
    r2 = FakeRegistry({"tool_a": "A2", "tool_c": "C2"})
    reg = CompositeToolRegistry([r1, r2])
    tools = reg.list_tools()
    names = [t.name for t in tools]
    # tool_a appears only once (from r1), tool_b and tool_c also present
    assert names.count("tool_a") == 1
    assert set(names) == {"tool_a", "tool_b", "tool_c"}


def test_list_tools_first_registry_wins_description():
    r1 = FakeRegistry({"shared": "from-first"})
    r2 = FakeRegistry({"shared": "from-second"})
    reg = CompositeToolRegistry([r1, r2])
    tools = reg.list_tools()
    assert len(tools) == 1
    assert tools[0].description == "from-first"


def test_has_tool_found_in_first_registry():
    r1 = FakeRegistry({"tool_a": "A"})
    reg = CompositeToolRegistry([r1])
    assert reg.has_tool("tool_a")


def test_has_tool_found_in_second_registry():
    r1 = FakeRegistry({"tool_a": "A"})
    r2 = FakeRegistry({"tool_b": "B"})
    reg = CompositeToolRegistry([r1, r2])
    assert reg.has_tool("tool_b")


def test_has_tool_not_found():
    r1 = FakeRegistry({"tool_a": "A"})
    reg = CompositeToolRegistry([r1])
    assert not reg.has_tool("nonexistent")


def test_has_tool_empty_registries():
    reg = CompositeToolRegistry([])
    assert not reg.has_tool("anything")


@pytest.mark.anyio
async def test_execute_tool_first_registry_wins():
    r1 = FakeRegistry({"shared": "first"})
    r2 = FakeRegistry({"shared": "second"})
    reg = CompositeToolRegistry([r1, r2])
    result = await reg.execute_tool(ToolCall(tool_name="shared", call_id="1", params={}))
    assert result.success
    assert "first" in result.output


@pytest.mark.anyio
async def test_execute_tool_falls_through_to_second_registry():
    r1 = FakeRegistry({"tool_a": "A"})
    r2 = FakeRegistry({"tool_b": "B"})
    reg = CompositeToolRegistry([r1, r2])
    result = await reg.execute_tool(ToolCall(tool_name="tool_b", call_id="2", params={}))
    assert result.success
    assert "B" in result.output


@pytest.mark.anyio
async def test_execute_tool_unknown_returns_error():
    r1 = FakeRegistry({"tool_a": "A"})
    reg = CompositeToolRegistry([r1])
    result = await reg.execute_tool(ToolCall(tool_name="unknown", call_id="3", params={}))
    assert not result.success
    assert "unknown" in result.error.lower() or "Unknown" in result.error


@pytest.mark.anyio
async def test_execute_tool_empty_registries_returns_error():
    reg = CompositeToolRegistry([])
    result = await reg.execute_tool(ToolCall(tool_name="anything", call_id="4", params={}))
    assert not result.success
    assert result.error is not None


def test_list_tools_logs_warning_for_shadowed_tools(caplog):
    import logging
    r1 = FakeRegistry({"tool_a": "A1"})
    r2 = FakeRegistry({"tool_a": "A2"})
    reg = CompositeToolRegistry([r1, r2])
    with caplog.at_level(logging.WARNING, logger="miniautogen.core.runtime.composite_tool_registry"):
        reg.list_tools()
    assert any("tool_a" in record.message and "shadow" in record.message.lower()
               for record in caplog.records)
