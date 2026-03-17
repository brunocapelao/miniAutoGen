"""Structured timeout composition for nested cancel scopes.

Provides a TimeoutScope utility that manages nested anyio cancel
scopes. CRITICAL: cancel scopes CANNOT span yield points in async
generators. Use only around non-yielding code blocks.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TimeoutScope:
    """Hierarchical timeout configuration.

    Timeouts are nested: pipeline > turn > tool.
    Inner timeouts must be shorter than outer timeouts.
    """

    pipeline_seconds: float | None = None
    turn_seconds: float | None = None
    tool_seconds: float | None = None

    def __post_init__(self) -> None:
        if (
            self.pipeline_seconds is not None
            and self.turn_seconds is not None
            and self.turn_seconds >= self.pipeline_seconds
        ):
            msg = (
                f"turn_seconds ({self.turn_seconds}) must be less "
                f"than pipeline_seconds ({self.pipeline_seconds})"
            )
            raise ValueError(msg)
        if (
            self.turn_seconds is not None
            and self.tool_seconds is not None
            and self.tool_seconds >= self.turn_seconds
        ):
            msg = (
                f"tool_seconds ({self.tool_seconds}) must be less "
                f"than turn_seconds ({self.turn_seconds})"
            )
            raise ValueError(msg)
        if (
            self.pipeline_seconds is not None
            and self.tool_seconds is not None
            and self.turn_seconds is None
            and self.tool_seconds >= self.pipeline_seconds
        ):
            msg = (
                f"tool_seconds ({self.tool_seconds}) must be less "
                f"than pipeline_seconds ({self.pipeline_seconds})"
            )
            raise ValueError(msg)
