from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import anyio

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events import EventSink, EventType, NullEventSink
from miniautogen.observability import get_logger
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
        self.logger = get_logger(__name__)

    async def _persist_failed_run(
        self,
        run_id: str,
        correlation_id: str,
        error_type: str,
    ) -> None:
        if self.run_store is not None:
            await self.run_store.save_run(
                run_id,
                {
                    "status": "failed",
                    "correlation_id": correlation_id,
                    "error_type": error_type,
                },
            )
        await self.event_sink.publish(
            ExecutionEvent(
                type=EventType.RUN_FAILED.value,
                timestamp=datetime.now(timezone.utc),
                run_id=run_id,
                correlation_id=correlation_id,
                scope="pipeline_runner",
                payload={"error_type": error_type},
            )
        )

    async def run_pipeline(
        self,
        pipeline: Any,
        state: Any,
        *,
        timeout_seconds: float | None = None,
    ) -> Any:
        run_id = getattr(state, "run_id", None) or getattr(state, "id", None) or str(uuid4())
        correlation_id = str(uuid4())
        current_run_id = str(run_id)
        self.last_run_id = current_run_id
        effective_timeout = timeout_seconds
        if effective_timeout is None and self.execution_policy is not None:
            effective_timeout = self.execution_policy.timeout_seconds
        logger = self.logger.bind(
            run_id=current_run_id,
            correlation_id=correlation_id,
            scope="pipeline_runner",
        )

        if self.run_store is not None:
            await self.run_store.save_run(
                current_run_id,
                {
                    "status": "started",
                    "correlation_id": correlation_id,
                },
            )

        await self.event_sink.publish(
            ExecutionEvent(
                type=EventType.RUN_STARTED.value,
                timestamp=datetime.now(timezone.utc),
                run_id=current_run_id,
                correlation_id=correlation_id,
                scope="pipeline_runner",
            )
        )
        logger.info("run_started")

        try:
            if effective_timeout is None:
                result = await pipeline.run(state)
            else:
                with anyio.fail_after(effective_timeout):
                    result = await pipeline.run(state)
        except TimeoutError:
            if self.run_store is not None:
                await self.run_store.save_run(
                    current_run_id,
                    {
                        "status": "timed_out",
                        "correlation_id": correlation_id,
                    },
                )
            await self.event_sink.publish(
                ExecutionEvent(
                    type=EventType.RUN_TIMED_OUT.value,
                    timestamp=datetime.now(timezone.utc),
                    run_id=current_run_id,
                    correlation_id=correlation_id,
                    scope="pipeline_runner",
                )
            )
            logger.warning("run_timed_out")
            raise
        except Exception as exc:
            await self._persist_failed_run(current_run_id, correlation_id, type(exc).__name__)
            logger.error("run_failed", error_type=type(exc).__name__)
            raise

        try:
            if self.run_store is not None:
                await self.run_store.save_run(
                    current_run_id,
                    {
                        "status": "finished",
                        "correlation_id": correlation_id,
                    },
                )
            if self.checkpoint_store is not None:
                await self.checkpoint_store.save_checkpoint(current_run_id, result)
        except Exception as exc:
            await self._persist_failed_run(current_run_id, correlation_id, type(exc).__name__)
            raise
        await self.event_sink.publish(
            ExecutionEvent(
                type=EventType.RUN_FINISHED.value,
                timestamp=datetime.now(timezone.utc),
                run_id=current_run_id,
                correlation_id=correlation_id,
                scope="pipeline_runner",
            )
        )
        logger.info("run_finished")
        self.last_run_id = current_run_id
        return result
