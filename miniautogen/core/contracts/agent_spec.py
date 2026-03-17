"""Declarative agent specification for the MiniAutoGen SDK.

AgentSpec defines the identity, capabilities, and policies of an agent.
It is the canonical schema for agent YAML files. The runtime resolves
an AgentSpec into a ResolvedAgentProfile before execution.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SkillRef(BaseModel):
    """Reference to skills attached to an agent."""

    attached: list[str] = Field(default_factory=list)


class ToolAccessConfig(BaseModel):
    """Controls which tools an agent can use."""

    mode: str = "allowlist"  # allowlist | denylist | all
    allow: list[str] = Field(default_factory=list)
    deny: list[str] = Field(default_factory=list)


class McpAccessConfig(BaseModel):
    """Controls which MCP servers and tools an agent can access."""

    servers: list[str] = Field(default_factory=list)
    tools_mode: str = "allowlist"
    allow: list[str] = Field(default_factory=list)
    deny: list[str] = Field(default_factory=list)


class MemoryConfig(BaseModel):
    """Memory policy for an agent."""

    profile: str = "default"
    session_memory: bool = True
    retrieval_memory: bool = False
    max_context_tokens: int = 16000


class DelegationConfig(BaseModel):
    """Delegation policy for an agent."""

    allow_delegation: bool = False
    can_delegate_to: list[str] = Field(default_factory=list)
    context_isolation: bool = True


class RuntimeConfig(BaseModel):
    """Runtime limits for an agent."""

    max_turns: int = 10
    timeout_seconds: float = 300.0
    retry_policy: str = "standard"


class PermissionsConfig(BaseModel):
    """Security permissions for an agent."""

    shell: str = "deny"
    network: str = "allow"
    filesystem: dict[str, Any] = Field(
        default_factory=lambda: {"read": True, "write": False},
    )


class AgentSpec(BaseModel):
    """Declarative agent specification.

    Defines what an agent IS (identity, capabilities, policies)
    independently of HOW it runs (engine profile).

    This is the canonical schema for agent YAML files under
    the ``agents/`` directory of a MiniAutoGen project.
    """

    id: str
    version: str = "1.0.0"
    name: str
    description: str = ""
    role: str = ""
    goal: str = ""
    backstory: str | None = None

    skills: SkillRef = Field(default_factory=SkillRef)
    tool_access: ToolAccessConfig = Field(
        default_factory=ToolAccessConfig,
    )
    mcp_access: McpAccessConfig = Field(
        default_factory=McpAccessConfig,
    )
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    delegation: DelegationConfig = Field(
        default_factory=DelegationConfig,
    )
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    permissions: PermissionsConfig = Field(
        default_factory=PermissionsConfig,
    )
    engine_profile: str | None = None
    vendor_extensions: dict[str, Any] = Field(
        default_factory=dict,
    )
