"""Tool protocol and result model for the MiniAutoGen SDK.

Tools are capabilities that agents can invoke during execution.
The ToolProtocol defines the structural interface; any class with
matching attributes and methods satisfies it via duck typing.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, model_validator


class ToolResult(BaseModel):
    """Result returned by a tool execution.

    Callers must ensure ``output`` is JSON-serializable when the
    result will be persisted or forwarded through the event system.
    """

    success: bool
    output: Any = None
    error: str | None = None

    @model_validator(mode="after")
    def _check_consistency(self) -> ToolResult:
        if not self.success and self.error is None:
            msg = "ToolResult with success=False must include error"
            raise ValueError(msg)
        if self.success and self.error is not None:
            msg = "ToolResult with success=True must not include error"
            raise ValueError(msg)
        return self


@runtime_checkable
class ToolProtocol(Protocol):
    """Structural protocol for tools.

    Any class with a ``name`` property, a ``description`` property,
    and an async ``execute`` method satisfies this protocol.

    Implementations MUST validate ``params`` before processing.
    The dict may contain user-controlled data.
    """

    @property
    def name(self) -> str: ...

    @property
    def description(self) -> str: ...

    async def execute(self, params: dict[str, Any]) -> ToolResult: ...
