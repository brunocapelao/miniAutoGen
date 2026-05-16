"""ApprovalGatedToolRegistry — ToolRegistryProtocol decorator for plan approval gates.

Wraps an existing ToolRegistryProtocol and intercepts tool calls for tools
listed in `required_for`. Before executing, calls the approval_tool function;
execution proceeds only if approval returns "granted".
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from miniautogen.core.contracts.tool import ToolResult
from miniautogen.core.contracts.tool_registry import (
    ToolCall,
    ToolDefinition,
    ToolRegistryProtocol,
)
from miniautogen.core.events.types import EventType


class ApprovalGatedToolRegistry:
    def __init__(
        self,
        *,
        inner: ToolRegistryProtocol,
        approval_tool: Callable[[str | dict], Awaitable[str]],
        required_for: set[str],
        agent_id: str,
        event_sink: Any,
    ) -> None:
        self._inner = inner
        self._approval_tool = approval_tool
        self._required_for = required_for
        self._agent_id = agent_id
        self._event_sink = event_sink

    def list_tools(self) -> list[ToolDefinition]:
        return self._inner.list_tools()

    def has_tool(self, name: str) -> bool:
        return self._inner.has_tool(name)

    async def execute_tool(self, call: ToolCall) -> ToolResult:
        if call.tool_name in self._required_for:
            plan_summary: dict[str, Any] = {
                "tool": call.tool_name,
                "params": call.params,
            }
            decision = await self._approval_tool(plan_summary)
            if decision != "granted":
                await self._emit_denied(call, decision)
                return ToolResult(
                    success=False,
                    error=f"Plan approval {decision} for {call.tool_name}",
                    output={"decision": decision, "tool": call.tool_name},
                )
        return await self._inner.execute_tool(call)

    async def _emit_denied(self, call: ToolCall, decision: str) -> None:
        if self._event_sink is None:
            return
        from miniautogen.core.contracts.events import ExecutionEvent

        event = ExecutionEvent(
            type=EventType.TOOL_FAILED.value,
            timestamp=datetime.now(timezone.utc),
            run_id="",
            correlation_id="",
            scope="approval_gated_tool_registry",
            payload={
                "tool": call.tool_name,
                "agent_id": self._agent_id,
                "decision": decision,
                "error": f"Plan approval {decision}",
            },
        )
        await self._event_sink.publish(event)
