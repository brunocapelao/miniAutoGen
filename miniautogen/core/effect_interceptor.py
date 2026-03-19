"""Effect interceptor: idempotency middleware for side-effect deduplication.

Wraps tool execution to prevent duplicate side effects on retry/replay.
This is opt-in middleware -- PipelineRunner is NOT modified.

Idempotency key = SHA-256(run_id + step_id + tool_name + args_hash)
Args hashing uses json.dumps(sort_keys=True) for deterministic key ordering
(NOT orjson, which preserves insertion order).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Callable, TypeVar

from miniautogen.core.contracts.effect import (
    EffectDeniedError,
    EffectDescriptor,
    EffectDuplicateError,
    EffectRecord,
    EffectStatus,
)
from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.event_sink import EventSink, NullEventSink
from miniautogen.core.events.types import EventType
from miniautogen.policies.effect import EffectPolicy
from miniautogen.stores.effect_journal import EffectJournal

T = TypeVar("T")


def compute_args_hash(args: dict[str, Any]) -> str:
    """Compute SHA-256 hash of tool arguments for idempotency.

    Uses json.dumps(sort_keys=True) for deterministic key ordering.
    orjson preserves insertion order which is non-deterministic for
    idempotency key computation.
    """
    canonical = json.dumps(args, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def compute_idempotency_key(
    *,
    run_id: str,
    step_id: str,
    tool_name: str,
    args_hash: str,
) -> str:
    """Compute the idempotency key for an effect.

    Key = SHA-256(run_id + step_id + tool_name + args_hash).
    Attempt number is explicitly EXCLUDED -- including it would
    generate different keys per retry, defeating deduplication.
    """
    raw = f"{run_id}{step_id}{tool_name}{args_hash}"
    return hashlib.sha256(raw.encode()).hexdigest()


class EffectInterceptor:
    """Idempotency middleware that wraps tool execution.

    Lifecycle per effect:
    1. Check policy (max_effects, allowed_types)
       -> EffectDeniedError if rejected
    2. Compute idempotency_key
    3. Lookup journal
       -> If COMPLETED: return cached result, emit EFFECT_SKIPPED
       -> If PENDING + stale: emit EFFECT_STALE_RECLAIMED, re-execute
       -> If PENDING + fresh: raise EffectDuplicateError
    4. Register PENDING in journal, emit EFFECT_REGISTERED
    5. Execute tool
    6. On success: update COMPLETED, emit EFFECT_EXECUTED
    7. On failure: update FAILED, emit EFFECT_FAILED
    """

    def __init__(
        self,
        *,
        journal: EffectJournal,
        policy: EffectPolicy | None = None,
        event_sink: EventSink | None = None,
    ) -> None:
        self._journal = journal
        self._policy = policy or EffectPolicy()
        self._event_sink = event_sink or NullEventSink()
        self._step_effect_counts: dict[str, int] = {}

    async def _emit(
        self,
        event_type: EventType,
        run_id: str,
        payload: dict[str, Any],
    ) -> None:
        """Emit an event through the configured sink."""
        event = ExecutionEvent(
            type=event_type.value,
            run_id=run_id,
            payload=payload,
        )
        await self._event_sink.publish(event)

    def _check_policy(
        self,
        effect_type: str,
        step_id: str,
        run_id: str,
    ) -> None:
        """Validate the effect against the configured policy.

        Raises EffectDeniedError if the effect is not allowed.
        """
        # Check allowed effect types
        if (
            self._policy.allowed_effect_types is not None
            and effect_type not in self._policy.allowed_effect_types
        ):
            raise EffectDeniedError(
                f"Effect type '{effect_type}' not in allowed types: "
                f"{self._policy.allowed_effect_types}"
            )

        # Check per-step limit
        step_key = f"{run_id}:{step_id}"
        current_count = self._step_effect_counts.get(step_key, 0)
        if current_count >= self._policy.max_effects_per_step:
            raise EffectDeniedError(
                f"Max effects per step ({self._policy.max_effects_per_step}) "
                f"exceeded for step '{step_id}'"
            )

    def _is_stale(self, record: EffectRecord) -> bool:
        """Check if a PENDING record is stale (executor likely crashed)."""
        age = (datetime.now(timezone.utc) - record.created_at).total_seconds()
        return age > self._policy.stale_pending_timeout_seconds

    async def execute(
        self,
        *,
        run_id: str,
        step_id: str,
        tool_name: str,
        args: dict[str, Any],
        effect_type: str = "tool_call",
        tool_fn: Callable[..., Any],
        metadata: tuple[tuple[str, Any], ...] = (),
    ) -> Any:
        """Execute a tool call with idempotency protection.

        Args:
            run_id: Current run identifier.
            step_id: Current step identifier.
            tool_name: Name of the tool being called.
            args: Tool arguments (will be hashed for idempotency).
            effect_type: Type of effect (default: "tool_call").
            tool_fn: Async callable that performs the actual tool execution.
                Called as ``await tool_fn(**args)`` on first execution.
            metadata: Additional metadata for the effect descriptor.

        Returns:
            The result of the tool execution, or None if skipped (cached).

        Raises:
            EffectDeniedError: If policy rejects the effect.
            EffectDuplicateError: If a fresh PENDING record exists
                (concurrent execution detected).
        """
        # 1. Check policy
        self._check_policy(effect_type, step_id, run_id)

        # 2. Compute idempotency key
        args_hash = compute_args_hash(args)
        idempotency_key = compute_idempotency_key(
            run_id=run_id,
            step_id=step_id,
            tool_name=tool_name,
            args_hash=args_hash,
        )

        # 3. Lookup journal
        existing = await self._journal.get(idempotency_key)

        if existing is not None:
            if existing.status == EffectStatus.COMPLETED:
                # Already completed -- skip re-execution
                await self._emit(
                    EventType.EFFECT_SKIPPED,
                    run_id,
                    {
                        "idempotency_key": idempotency_key,
                        "tool_name": tool_name,
                        "reason": "already_completed",
                    },
                )
                return None

            if existing.status == EffectStatus.PENDING:
                if self._is_stale(existing):
                    # Stale PENDING -- executor likely crashed, reclaim.
                    # Mark the stale record as FAILED before re-registering
                    # to avoid UNIQUE constraint violations on durable journals.
                    await self._journal.update_status(
                        idempotency_key,
                        EffectStatus.FAILED,
                        error_info="stale PENDING reclaimed",
                    )
                    await self._emit(
                        EventType.EFFECT_STALE_RECLAIMED,
                        run_id,
                        {
                            "idempotency_key": idempotency_key,
                            "tool_name": tool_name,
                            "age_seconds": (
                                datetime.now(timezone.utc) - existing.created_at
                            ).total_seconds(),
                        },
                    )
                    # Fall through to re-execute with fresh PENDING record
                else:
                    # Fresh PENDING -- concurrent execution detected
                    raise EffectDuplicateError(
                        f"Effect '{idempotency_key}' is currently PENDING "
                        f"(concurrent execution detected)"
                    )

            # FAILED status: allow re-execution (fall through)

        # 4. Build descriptor and register PENDING
        descriptor = EffectDescriptor(
            effect_type=effect_type,
            tool_name=tool_name,
            args_hash=args_hash,
            run_id=run_id,
            step_id=step_id,
            metadata=metadata,
        )
        now = datetime.now(timezone.utc)
        record = EffectRecord(
            idempotency_key=idempotency_key,
            descriptor=descriptor,
            status=EffectStatus.PENDING,
            created_at=now,
        )
        await self._journal.register(record)

        # Track per-step count
        step_key = f"{run_id}:{step_id}"
        self._step_effect_counts[step_key] = (
            self._step_effect_counts.get(step_key, 0) + 1
        )

        await self._emit(
            EventType.EFFECT_REGISTERED,
            run_id,
            {
                "idempotency_key": idempotency_key,
                "tool_name": tool_name,
                "effect_type": effect_type,
                "step_id": step_id,
            },
        )

        # 5. Execute tool
        try:
            result = await tool_fn(**args)
        except Exception as exc:
            # 7. On failure: update FAILED, emit EFFECT_FAILED
            error_info = type(exc).__name__
            await self._journal.update_status(
                idempotency_key,
                EffectStatus.FAILED,
                error_info=error_info,
            )
            await self._emit(
                EventType.EFFECT_FAILED,
                run_id,
                {
                    "idempotency_key": idempotency_key,
                    "tool_name": tool_name,
                    "error_type": type(exc).__name__,
                },
            )
            raise

        # 6. On success: update COMPLETED, emit EFFECT_EXECUTED
        completed_at = datetime.now(timezone.utc)
        result_hash = hashlib.sha256(
            json.dumps(result, sort_keys=True, default=str).encode()
        ).hexdigest() if result is not None else None

        await self._journal.update_status(
            idempotency_key,
            EffectStatus.COMPLETED,
            completed_at=completed_at,
            result_hash=result_hash,
        )
        await self._emit(
            EventType.EFFECT_EXECUTED,
            run_id,
            {
                "idempotency_key": idempotency_key,
                "tool_name": tool_name,
                "result_hash": result_hash,
            },
        )

        return result
