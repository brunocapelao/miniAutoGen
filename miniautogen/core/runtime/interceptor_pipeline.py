"""InterceptorPipeline -- composes RuntimeInterceptors for step execution.

Implements the 4-hook interception pattern from Fluxo 9:
- before_step: Waterfall (each interceptor transforms input)
- should_execute: Bail (any False = skip)
- after_step: Series (each interceptor transforms result)
- on_error: First non-None recovery wins

Emits INTERCEPTOR_BEFORE_STEP, INTERCEPTOR_AFTER_STEP, and
INTERCEPTOR_BAIL events through the EventSink.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.events.event_sink import EventSink, NullEventSink
from miniautogen.core.events.types import EventType


class InterceptorPipeline:
    """Composes a list of RuntimeInterceptors and runs them in order.

    Each method corresponds to a phase of the interception lifecycle.
    The pipeline emits canonical events for observability.
    """

    def __init__(
        self,
        *,
        interceptors: list[Any],
        event_sink: EventSink | None = None,
    ) -> None:
        self._interceptors = list(interceptors)
        self._event_sink = event_sink or NullEventSink()

    async def run_before_step(
        self,
        input: Any,
        context: RunContext,
    ) -> Any:
        """Run before_step on all interceptors in waterfall order."""
        current = input
        for interceptor in self._interceptors:
            current = await interceptor.before_step(current, context)

        if self._interceptors:
            await self._emit(
                EventType.INTERCEPTOR_BEFORE_STEP,
                context,
                {
                    "interceptor_count": len(self._interceptors),
                },
            )
        return current

    async def run_should_execute(
        self,
        context: RunContext,
    ) -> bool:
        """Run should_execute on all interceptors. Any False = bail."""
        for interceptor in self._interceptors:
            if not await interceptor.should_execute(context):
                await self._emit(
                    EventType.INTERCEPTOR_BAIL,
                    context,
                    {
                        "interceptor": type(interceptor).__name__,
                    },
                )
                return False
        return True

    async def run_after_step(
        self,
        result: Any,
        context: RunContext,
    ) -> Any:
        """Run after_step on all interceptors in series order."""
        current = result
        for interceptor in self._interceptors:
            current = await interceptor.after_step(current, context)

        if self._interceptors:
            await self._emit(
                EventType.INTERCEPTOR_AFTER_STEP,
                context,
                {
                    "interceptor_count": len(self._interceptors),
                },
            )
        return current

    async def run_on_error(
        self,
        error: Exception,
        context: RunContext,
    ) -> Any:
        """Run on_error on interceptors. First non-None recovery wins."""
        for interceptor in self._interceptors:
            recovery = await interceptor.on_error(error, context)
            if recovery is not None:
                return recovery
        return None

    async def _emit(
        self,
        event_type: EventType,
        context: RunContext,
        payload: dict[str, Any],
    ) -> None:
        event = ExecutionEvent(
            type=event_type.value,
            timestamp=datetime.now(timezone.utc),
            run_id=context.run_id,
            correlation_id=context.correlation_id,
            scope="interceptor_pipeline",
            payload=payload,
        )
        await self._event_sink.publish(event)
