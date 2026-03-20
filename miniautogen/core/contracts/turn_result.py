"""Internal turn result model for AgentRuntime."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from miniautogen.core.contracts.tool_registry import ToolCall


class TurnResult(BaseModel):
    """Result of a single agent turn.

    INTERNAL — not part of the public AgentRuntime interface.
    Consumed by the AgentRuntime compositor to aggregate partial outputs
    from a driver turn into a structured summary before emitting events.
    """

    output: Any = None
    text: str = ""
    structured: dict[str, Any] = Field(default_factory=dict)
    messages: list[dict[str, Any]] = Field(default_factory=list)
    token_usage: dict[str, int] = Field(default_factory=dict)
    tool_calls: list[ToolCall] = Field(default_factory=list)
