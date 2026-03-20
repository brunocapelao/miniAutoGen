"""Tool registry protocol and supporting models."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from miniautogen.core.contracts.tool import ToolProtocol, ToolResult


class ToolDefinition(BaseModel):
    """Serializable tool definition for injection into driver prompts."""

    name: str
    description: str
    parameters: dict[str, Any] | None = None  # JSON Schema

    @classmethod
    def from_protocol(cls, tool: ToolProtocol) -> ToolDefinition:
        """Build a ToolDefinition from any object satisfying ToolProtocol."""
        return cls(name=tool.name, description=tool.description)


class ToolCall(BaseModel):
    """A tool invocation request from the driver."""

    tool_name: str
    call_id: str
    params: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class ToolRegistryProtocol(Protocol):
    """Registry of tools available to an agent.

    Implementations manage a named collection of tools and expose them
    in a serializable form so that backends (LLM drivers) can inject
    them into prompts and execute invocations at runtime.
    """

    def list_tools(self) -> list[ToolDefinition]: ...

    async def execute_tool(self, call: ToolCall) -> ToolResult: ...

    def has_tool(self, name: str) -> bool: ...
