"""TimeoutPolicy — wraps agent turns in anyio.fail_after scopes.

Emits agent_turn_timed_out on expiration. Supports 'continue' (default)
and 'abort' on_timeout_action. Precedence: agent > round > flow > engine.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable

import anyio
import structlog

from miniautogen.core.contracts.timeout_resolution import (
    ResolvedTimeout,
    resolve_timeout,
)
from miniautogen.core.events.types import EventType

logger = structlog.get_logger()

EmitCallable = Callable[..., Any]


class TimeoutPolicy:
    """Lateral policy that wraps each agent turn in a fail_after scope.

    Subscribes to agent_turn_started; opens a CancelScope; on expiration,
    cancels the turn and emits agent_turn_timed_out.
    """

    def __init__(
        self,
        *,
        agent_timeouts: dict[str, float],
        round_timeouts: dict[str, float],
        flow_timeout: float | None,
        engine_timeout: float,
        on_timeout_action: str = "continue",
    ) -> None:
        self._agent_timeouts = agent_timeouts
        self._round_timeouts = round_timeouts
        self._flow_timeout = flow_timeout
        self._engine_timeout = engine_timeout
        self._on_timeout_action = on_timeout_action

    @asynccontextmanager
    async def scope_for_turn(
        self,
        *,
        agent_id: str,
        round_name: str | None,
        emit: EmitCallable,
    ) -> AsyncIterator[ResolvedTimeout]:
        resolved = resolve_timeout(
            agent_id=agent_id,
            round_name=round_name,
            agent_timeouts=self._agent_timeouts,
            round_timeouts=self._round_timeouts,
            flow_timeout=self._flow_timeout,
            engine_timeout=self._engine_timeout,
        )
        try:
            with anyio.fail_after(resolved.seconds):
                yield resolved
        except TimeoutError:
            await emit(
                EventType.AGENT_TURN_TIMED_OUT.value,
                agent_id=agent_id,
                round_name=round_name,
                applied_timeout=resolved.seconds,
                source=resolved.source,
            )
            if self._on_timeout_action == "abort":
                raise
            logger.warning(
                "timeout_policy.continue_after_timeout",
                agent_id=agent_id,
                round_name=round_name,
                applied=resolved.seconds,
            )
