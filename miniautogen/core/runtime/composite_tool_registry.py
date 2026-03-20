"""Composite tool registry that chains multiple registries."""
from __future__ import annotations

import logging
from collections.abc import Sequence

from miniautogen.core.contracts.tool import ToolResult
from miniautogen.core.contracts.tool_registry import (
    ToolCall,
    ToolDefinition,
    ToolRegistryProtocol,
)

logger = logging.getLogger(__name__)


class CompositeToolRegistry:
    """Chains multiple ToolRegistryProtocol implementations.

    First registry containing a tool wins (first-match precedence).
    Logs a warning when a tool in a later registry is shadowed by an
    earlier one.
    """

    def __init__(self, registries: Sequence[ToolRegistryProtocol]) -> None:
        self._registries = list(registries)

    def list_tools(self) -> list[ToolDefinition]:
        tools: list[ToolDefinition] = []
        seen: set[str] = set()
        for reg in self._registries:
            for tool in reg.list_tools():
                if tool.name not in seen:
                    tools.append(tool)
                    seen.add(tool.name)
                else:
                    logger.warning(
                        "Tool '%s' shadowed by earlier registry", tool.name
                    )
        return tools

    def has_tool(self, name: str) -> bool:
        return any(r.has_tool(name) for r in self._registries)

    async def execute_tool(self, call: ToolCall) -> ToolResult:
        for reg in self._registries:
            if reg.has_tool(call.tool_name):
                return await reg.execute_tool(call)
        return ToolResult(success=False, error=f"Unknown tool: {call.tool_name}")
