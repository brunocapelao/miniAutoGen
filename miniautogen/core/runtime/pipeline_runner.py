from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import anyio

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events import EventSink, EventType, NullEventSink
from miniautogen.policies.execution import ExecutionPolicy
from miniautogen.stores.checkpoint_store import CheckpointStore
from miniautogen.stores.run_store import RunStore


class PipelineRunner:
    """Runs an existing pipeline while keeping runtime mechanics centralized."""

    def __init__(
        self,
        event_sink: EventSink | None = None,
        run_store: RunStore | None = None,
        checkpoint_store: CheckpointStore | None = None,
        execution_policy: ExecutionPolicy | None = None,
    ):
        self.event_sink = event_sink or NullEventSink()
        self.run_store = run_store
        self.checkpoint_store = checkpoint_store
        self.execution_policy = execution_policy
        self.last_run_id: str | None = None

    async def run_pipeline(
        self,
        pipeline: Any,
        state: Any,
        *,
        timeout_seconds: float | None = None,
    ) -> Any:
        run_id = getattr(state, "run_id", None) or getattr(state, "id", None) or str(uuid4())
        correlation_id = str(uuid4())
        self.last_run_id = str(run_id)
        effective_timeout = timeout_seconds
        if effective_timeout is None and self.execution_policy is not None:
            effective_timeout = self.execution_policy.timeout_seconds

        if self.run_store is not None:
            await self.run_store.save_run(
                self.last_run_id,
                {
                    "status": "started",
                    "correlation_id": correlation_id,
                },
            )

        await self.event_sink.publish(
            ExecutionEvent(
                type=EventType.RUN_STARTED.value,
                timestamp=datetime.now(UTC),
                run_id=self.last_run_id,
                correlation_id=correlation_id,
                scope="pipeline_runner",
            )
        )

        try:
            if effective_timeout is None:
                result = await pipeline.run(state)
            else:
                with anyio.fail_after(effective_timeout):
                    result = await pipeline.run(state)
        except TimeoutError:
            if self.run_store is not None:
                await self.run_store.save_run(
                    self.last_run_id,
                    {
                        "status": "timed_out",
                        "correlation_id": correlation_id,
                    },
                )
            await self.event_sink.publish(
                ExecutionEvent(
                    type=EventType.RUN_TIMED_OUT.value,
                    timestamp=datetime.now(UTC),
                    run_id=self.last_run_id,
                    correlation_id=correlation_id,
                    scope="pipeline_runner",
                )
            )
            raise
        except Exception as exc:
            if self.run_store is not None:
                await self.run_store.save_run(
                    self.last_run_id,
                    {
                        "status": "failed",
                        "correlation_id": correlation_id,
                        "error_type": type(exc).__name__,
                    },
                )
            await self.event_sink.publish(
                ExecutionEvent(
                    type=EventType.RUN_FAILED.value,
                    timestamp=datetime.now(UTC),
                    run_id=self.last_run_id,
                    correlation_id=correlation_id,
                    scope="pipeline_runner",
                    payload={"error_type": type(exc).__name__},
                )
            )
            raise

        if self.run_store is not None:
            await self.run_store.save_run(
                self.last_run_id,
                {
                    "status": "finished",
                    "correlation_id": correlation_id,
                },
            )
        if self.checkpoint_store is not None:
            await self.checkpoint_store.save_checkpoint(self.last_run_id, result)
        await self.event_sink.publish(
            ExecutionEvent(
                type=EventType.RUN_FINISHED.value,
                timestamp=datetime.now(UTC),
                run_id=self.last_run_id,
                correlation_id=correlation_id,
                scope="pipeline_runner",
            )
        )
        return result
