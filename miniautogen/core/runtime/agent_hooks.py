"""Built-in AgentHook implementations for the Agent Runtime layer.

All hooks are async (AnyIO canonical -- this is an invariant).
Hooks are composable and stateless where possible.

See docs/pt/architecture/07-agent-anatomy.md section 6.1.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.events.event_sink import EventSink
from miniautogen.core.events.types import EventType
from miniautogen.policies.budget import BudgetExceededError, BudgetTracker
from miniautogen.policies.permission import PermissionPolicy, check_permission


class BudgetGuardHook:
    """Aborts agent turn if budget is exceeded.

    Checks the BudgetTracker before each turn. If the budget
    has already been exceeded, raises BudgetExceededError.
    """

    def __init__(self, *, tracker: BudgetTracker) -> None:
        self._tracker = tracker

    async def before_turn(
        self,
        messages: list[dict[str, Any]],
        context: RunContext,
    ) -> list[dict[str, Any]]:
        if not self._tracker.check():
            raise BudgetExceededError(
                f"Budget exceeded: spent {self._tracker.spent:.4f}, "
                f"limit {self._tracker.policy.max_cost}"
            )
        return messages

    async def after_event(
        self,
        event: ExecutionEvent,
        context: RunContext,
    ) -> ExecutionEvent:
        return event

    async def on_error(
        self,
        error: Exception,
        context: RunContext,
    ) -> ExecutionEvent | None:
        return None


class EventEmitterHook:
    """Emits AGENT_TURN_STARTED/COMPLETED and AGENT_HOOK_EXECUTED events.

    Emits AGENT_TURN_STARTED in before_turn and AGENT_HOOK_EXECUTED
    in after_event for observability.
    """

    def __init__(self, *, event_sink: EventSink, agent_id: str) -> None:
        self._event_sink = event_sink
        self._agent_id = agent_id

    async def before_turn(
        self,
        messages: list[dict[str, Any]],
        context: RunContext,
    ) -> list[dict[str, Any]]:
        event = ExecutionEvent(
            type=EventType.AGENT_TURN_STARTED.value,
            timestamp=datetime.now(timezone.utc),
            run_id=context.run_id,
            correlation_id=context.correlation_id,
            scope="agent_runtime",
            payload={
                "agent_id": self._agent_id,
                "message_count": len(messages),
            },
        )
        await self._event_sink.publish(event)
        return messages

    async def after_event(
        self,
        event: ExecutionEvent,
        context: RunContext,
    ) -> ExecutionEvent:
        hook_event = ExecutionEvent(
            type=EventType.AGENT_HOOK_EXECUTED.value,
            timestamp=datetime.now(timezone.utc),
            run_id=context.run_id,
            correlation_id=context.correlation_id,
            scope="agent_runtime",
            payload={
                "agent_id": self._agent_id,
                "hook": "EventEmitterHook",
                "phase": "after_event",
                "original_event_type": event.type,
            },
        )
        await self._event_sink.publish(hook_event)
        return event

    async def on_error(
        self,
        error: Exception,
        context: RunContext,
    ) -> ExecutionEvent | None:
        return None


class PermissionsEnforcerHook:
    """Blocks disallowed tool calls based on PermissionPolicy.

    Inspects BACKEND_TOOL_CALL_REQUESTED events in after_event.
    If the tool_name is not permitted, raises PermissionDeniedError.
    Non-tool-call events pass through unmodified.
    """

    def __init__(self, *, policy: PermissionPolicy) -> None:
        self._policy = policy

    async def before_turn(
        self,
        messages: list[dict[str, Any]],
        context: RunContext,
    ) -> list[dict[str, Any]]:
        return messages

    async def after_event(
        self,
        event: ExecutionEvent,
        context: RunContext,
    ) -> ExecutionEvent:
        if event.type == EventType.BACKEND_TOOL_CALL_REQUESTED.value:
            tool_name = event.get_payload("tool_name")
            if tool_name is not None:
                check_permission(self._policy, tool_name)
        return event

    async def on_error(
        self,
        error: Exception,
        context: RunContext,
    ) -> ExecutionEvent | None:
        return None
