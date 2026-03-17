"""Tool specification for the MiniAutoGen SDK.

ToolSpec is the declarative schema for tool YAML files.
It describes the tool's interface and execution target.
This is distinct from ToolProtocol, which is the runtime
interface that tool implementations must satisfy.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ToolExecution(BaseModel):
    """How the tool is executed."""

    kind: str = "python"  # python | mcp | http
    target: str = ""  # e.g. miniautogen.tools.web_search:execute


class ToolPolicy(BaseModel):
    """Execution policy for a tool."""

    approval: str = "none"  # none | always | on_write
    timeout_seconds: float = 30.0


class ToolSpec(BaseModel):
    """Declarative tool specification.

    This is the canonical schema for tool YAML files under
    the ``tools/`` directory. It describes the tool's interface
    (input schema) and execution target.

    Note: ToolSpec describes a tool *declaration*. ToolProtocol
    describes a tool *implementation* at runtime. The resolver
    bridges the two.
    """

    name: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    execution: ToolExecution = Field(
        default_factory=ToolExecution,
    )
    policy: ToolPolicy = Field(default_factory=ToolPolicy)
