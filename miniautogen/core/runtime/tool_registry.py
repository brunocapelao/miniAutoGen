"""In-memory tool registry implementation."""
from __future__ import annotations

import inspect
from typing import Any, Awaitable, Callable

from miniautogen.core.contracts.tool import ToolResult
from miniautogen.core.contracts.tool_registry import (
    ToolCall, ToolDefinition, ToolRegistryProtocol,
)

ToolHandler = Callable[[dict[str, Any]], ToolResult | Awaitable[ToolResult]]


class InMemoryToolRegistry:
    """In-memory tool registry for testing and programmatic use."""

    def __init__(self) -> None:
        self._definitions: dict[str, ToolDefinition] = {}
        self._handlers: dict[str, ToolHandler] = {}

    def register(self, definition: ToolDefinition, handler: ToolHandler) -> None:
        self._definitions[definition.name] = definition
        self._handlers[definition.name] = handler

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._definitions.values())

    def has_tool(self, name: str) -> bool:
        return name in self._definitions

    async def execute_tool(self, call: ToolCall) -> ToolResult:
        handler = self._handlers.get(call.tool_name)
        if handler is None:
            return ToolResult(success=False, error=f"Unknown tool: {call.tool_name}")
        try:
            result = handler(call.params)
            if inspect.isawaitable(result):
                result = await result
            return result
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
