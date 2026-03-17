"""MCP server binding specification for the MiniAutoGen SDK.

Defines how an agent connects to external MCP servers for
tools, data, and workflow integration.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class McpExposeConfig(BaseModel):
    """Controls which MCP tools are exposed."""

    tools_mode: str = "allowlist"
    allow: list[str] = Field(default_factory=list)


class McpPolicy(BaseModel):
    """Execution policy for MCP operations."""

    approval: str = "on_write"
    timeout_seconds: float = 60.0


class McpServerBinding(BaseModel):
    """Declarative MCP server binding.

    This is the canonical schema for MCP binding YAML files
    under the ``mcp/`` directory. It defines connection
    parameters, exposed tools, and execution policies.
    """

    id: str
    transport: str = "stdio"  # stdio | sse | streamable-http
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    expose: McpExposeConfig = Field(
        default_factory=McpExposeConfig,
    )
    policy: McpPolicy = Field(default_factory=McpPolicy)
