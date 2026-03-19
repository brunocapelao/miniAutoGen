"""Formal state machine for pipeline run lifecycle management.

Governs valid state transitions, emits events at each transition,
and tracks transition history for observability.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.event_sink import EventSink


class RunState(str, Enum):
    """States in the pipeline run lifecycle."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


# Terminal states — no further transitions allowed.
TERMINAL_STATES: set[RunState] = {
    RunState.FINISHED,
    RunState.FAILED,
    RunState.CANCELLED,
    RunState.TIMED_OUT,
}

# Valid transitions: from_state -> set of allowed to_states.
VALID_TRANSITIONS: dict[RunState, set[RunState]] = {
    RunState.PENDING: {RunState.RUNNING, RunState.CANCELLED},
    RunState.RUNNING: {
        RunState.FINISHED,
        RunState.FAILED,
        RunState.CANCELLED,
        RunState.TIMED_OUT,
        RunState.PAUSED,
    },
    RunState.PAUSED: {RunState.RUNNING, RunState.CANCELLED},
    # Terminal states have no outgoing transitions.
    RunState.FINISHED: set(),
    RunState.FAILED: set(),
    RunState.CANCELLED: set(),
    RunState.TIMED_OUT: set(),
}


class InvalidTransitionError(Exception):
    """Raised when attempting an invalid state transition."""

    def __init__(self, from_state: RunState, to_state: RunState) -> None:
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(
            f"Invalid transition: {from_state.value} \u2192 {to_state.value}"
        )


class RunStateMachine:
    """Formal state machine for pipeline run lifecycle.

    Ensures valid transitions, emits events, and provides query methods.
    Thread-safe (single writer assumed in async context).
    """

    def __init__(
        self,
        run_id: str,
        event_sink: EventSink | None = None,
    ) -> None:
        self._run_id = run_id
        self._state = RunState.PENDING
        self._event_sink = event_sink
        self._history: list[tuple[RunState, RunState, datetime]] = []

    @property
    def state(self) -> RunState:
        """Current state of the run."""
        return self._state

    @property
    def is_terminal(self) -> bool:
        """Whether the run has reached a terminal state."""
        return self._state in TERMINAL_STATES

    @property
    def history(self) -> list[tuple[RunState, RunState, datetime]]:
        """Return a copy of the transition history."""
        return list(self._history)

    async def transition(self, to_state: RunState) -> None:
        """Transition to a new state.

        Raises InvalidTransitionError if the transition is not allowed.
        """
        if to_state not in VALID_TRANSITIONS.get(self._state, set()):
            raise InvalidTransitionError(self._state, to_state)

        from_state = self._state
        self._state = to_state
        self._history.append((from_state, to_state, datetime.now(timezone.utc)))

        if self._event_sink is not None:
            event = ExecutionEvent(
                type="run_state_changed",
                timestamp=datetime.now(timezone.utc),
                run_id=self._run_id,
                payload={
                    "from_state": from_state.value,
                    "to_state": to_state.value,
                },
            )
            await self._event_sink.publish(event)

    # -- Convenience methods --------------------------------------------------

    async def start(self) -> None:
        """Transition from PENDING to RUNNING."""
        await self.transition(RunState.RUNNING)

    async def finish(self) -> None:
        """Transition to FINISHED."""
        await self.transition(RunState.FINISHED)

    async def fail(self) -> None:
        """Transition to FAILED."""
        await self.transition(RunState.FAILED)

    async def cancel(self) -> None:
        """Transition to CANCELLED."""
        await self.transition(RunState.CANCELLED)

    async def timeout(self) -> None:
        """Transition to TIMED_OUT."""
        await self.transition(RunState.TIMED_OUT)

    async def pause(self) -> None:
        """Transition from RUNNING to PAUSED."""
        await self.transition(RunState.PAUSED)

    async def resume(self) -> None:
        """Transition from PAUSED to RUNNING."""
        await self.transition(RunState.RUNNING)
