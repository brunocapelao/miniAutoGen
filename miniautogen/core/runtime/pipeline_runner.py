from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import anyio

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events import EventSink, EventType, NullEventSink


class PipelineRunner:
    """Runs an existing pipeline while keeping runtime mechanics centralized."""

    def __init__(self, event_sink: EventSink | None = None):
        self.event_sink = event_sink or NullEventSink()

    async def run_pipeline(
        self,
        pipeline: Any,
        state: Any,
        *,
        timeout_seconds: float | None = None,
    ) -> Any:
        run_id = getattr(state, "run_id", None) or getattr(state, "id", None) or str(uuid4())
        correlation_id = str(uuid4())

        await self.event_sink.publish(
            ExecutionEvent(
                type=EventType.RUN_STARTED.value,
                timestamp=datetime.now(UTC),
                run_id=str(run_id),
                correlation_id=correlation_id,
                scope="pipeline_runner",
            )
        )

        if timeout_seconds is None:
            result = await pipeline.run(state)
            await self.event_sink.publish(
                ExecutionEvent(
                    type=EventType.RUN_FINISHED.value,
                    timestamp=datetime.now(UTC),
                    run_id=str(run_id),
                    correlation_id=correlation_id,
                    scope="pipeline_runner",
                )
            )
            return result

        try:
            with anyio.fail_after(timeout_seconds):
                result = await pipeline.run(state)
        except TimeoutError:
            await self.event_sink.publish(
                ExecutionEvent(
                    type=EventType.RUN_TIMED_OUT.value,
                    timestamp=datetime.now(UTC),
                    run_id=str(run_id),
                    correlation_id=correlation_id,
                    scope="pipeline_runner",
                )
            )
            raise

        await self.event_sink.publish(
            ExecutionEvent(
                type=EventType.RUN_FINISHED.value,
                timestamp=datetime.now(UTC),
                run_id=str(run_id),
                correlation_id=correlation_id,
                scope="pipeline_runner",
            )
        )
        return result
