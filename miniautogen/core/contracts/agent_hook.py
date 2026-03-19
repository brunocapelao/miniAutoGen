"""AgentHook protocol for the Agent Runtime layer.

Defines composable hooks that intercept the agent turn lifecycle.
Hooks are invoked in registration order. All methods are async
(AnyIO canonical -- this is an invariant).

See docs/pt/architecture/07-agent-anatomy.md section 6.1.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.contracts.run_context import RunContext


@runtime_checkable
class AgentHook(Protocol):
    """Composable hook that intercepts the agent turn lifecycle.

    All methods are async (AnyIO invariant). Default implementations
    are pass-through to allow partial overrides.
    """

    async def before_turn(
        self,
        messages: list[dict[str, Any]],
        context: RunContext,
    ) -> list[dict[str, Any]]:
        """Transform messages before sending to the Engine.

        Called in waterfall order: each hook receives the output of
        the previous hook. Return messages unmodified for pass-through.
        """
        ...

    async def after_event(
        self,
        event: ExecutionEvent,
        context: RunContext,
    ) -> ExecutionEvent:
        """Transform events received from the Engine.

        Called in series order for each event. Return event unmodified
        for pass-through.
        """
        ...

    async def on_error(
        self,
        error: Exception,
        context: RunContext,
    ) -> ExecutionEvent | None:
        """Handle errors during agent execution.

        Return an ExecutionEvent as fallback, or None to propagate
        the error to the caller.
        """
        ...
