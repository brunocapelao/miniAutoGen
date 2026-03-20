import pytest
from miniautogen.core.contracts.tool_registry import (
    ToolRegistryProtocol, ToolDefinition, ToolCall,
)
from miniautogen.core.contracts.tool import ToolResult
from miniautogen.core.runtime.tool_registry import InMemoryToolRegistry


def test_implements_protocol():
    reg = InMemoryToolRegistry()
    assert isinstance(reg, ToolRegistryProtocol)


def test_empty_registry():
    reg = InMemoryToolRegistry()
    assert reg.list_tools() == []
    assert not reg.has_tool("read_file")


def test_register_and_list():
    reg = InMemoryToolRegistry()
    td = ToolDefinition(name="read_file", description="Read a file")

    async def handler(params):
        return ToolResult(success=True, output="content")

    reg.register(td, handler=handler)
    assert reg.has_tool("read_file")
    assert len(reg.list_tools()) == 1
    assert reg.list_tools()[0].name == "read_file"


@pytest.mark.anyio
async def test_execute_tool():
    reg = InMemoryToolRegistry()
    td = ToolDefinition(name="echo", description="Echo input")

    async def echo_handler(params):
        return ToolResult(success=True, output=params.get("text", ""))

    reg.register(td, handler=echo_handler)
    result = await reg.execute_tool(
        ToolCall(tool_name="echo", call_id="1", params={"text": "hello"})
    )
    assert result.success
    assert result.output == "hello"


@pytest.mark.anyio
async def test_execute_unknown_tool():
    reg = InMemoryToolRegistry()
    result = await reg.execute_tool(
        ToolCall(tool_name="unknown", call_id="1", params={})
    )
    assert not result.success
    assert "unknown" in result.error.lower()


@pytest.mark.anyio
async def test_execute_tool_handler_error():
    reg = InMemoryToolRegistry()
    td = ToolDefinition(name="fail", description="Always fails")

    async def fail_handler(params):
        raise RuntimeError("boom")

    reg.register(td, handler=fail_handler)
    result = await reg.execute_tool(
        ToolCall(tool_name="fail", call_id="1", params={})
    )
    assert not result.success
    assert "boom" in result.error


@pytest.mark.anyio
async def test_sync_handler_support():
    """Sync handlers should also work (wrapped internally)."""
    reg = InMemoryToolRegistry()
    td = ToolDefinition(name="sync_tool", description="Sync tool")

    def sync_handler(params):
        return ToolResult(success=True, output="sync result")

    reg.register(td, handler=sync_handler)
    result = await reg.execute_tool(
        ToolCall(tool_name="sync_tool", call_id="1", params={})
    )
    assert result.success
    assert result.output == "sync result"
