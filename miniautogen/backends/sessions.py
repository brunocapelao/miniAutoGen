# miniautogen/backends/sessions.py
"""Session lifecycle management for backend drivers.

Tracks session state with a simple state machine. Sessions transition
through: created -> active -> busy -> active (loop) -> completed/failed -> closed.
Any state can transition to 'closed' directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from miniautogen.backends.models import BackendCapabilities


class SessionState(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    BUSY = "busy"
    INTERRUPTED = "interrupted"
    COMPLETED = "completed"
    FAILED = "failed"
    CLOSED = "closed"


# Valid transitions: from_state -> set of allowed to_states.
# 'closed' is always reachable from any state.
_TRANSITIONS: dict[SessionState, set[SessionState]] = {
    SessionState.CREATED: {SessionState.ACTIVE, SessionState.FAILED},
    SessionState.ACTIVE: {SessionState.BUSY, SessionState.COMPLETED, SessionState.FAILED},
    SessionState.BUSY: {SessionState.ACTIVE, SessionState.INTERRUPTED, SessionState.COMPLETED, SessionState.FAILED},
    SessionState.INTERRUPTED: {SessionState.ACTIVE, SessionState.FAILED},
    SessionState.COMPLETED: set(),
    SessionState.FAILED: set(),
    SessionState.CLOSED: set(),
}


class InvalidTransitionError(Exception):
    """Raised when a session state transition is not allowed."""


@dataclass
class SessionInfo:
    session_id: str
    backend_id: str
    state: SessionState
    capabilities: BackendCapabilities
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    external_session_ref: str | None = None


class SessionManager:
    """In-memory session tracker with state machine enforcement.

    This is the internal view of MiniAutoGen, not a mirror of the
    backend's truth. Not concurrency-safe in Phase 1 (see D5).
    """

    # TODO(review): add max session limit to prevent unbounded growth
    # TODO(review): return copy from get() to prevent state bypass

    def __init__(self) -> None:
        self._sessions: dict[str, SessionInfo] = {}

    def create(
        self,
        session_id: str,
        backend_id: str,
        capabilities: BackendCapabilities,
        external_session_ref: str | None = None,
    ) -> SessionInfo:
        if session_id in self._sessions:
            msg = f"Session '{session_id}' already exists"
            raise ValueError(msg)
        info = SessionInfo(
            session_id=session_id,
            backend_id=backend_id,
            state=SessionState.CREATED,
            capabilities=capabilities,
            external_session_ref=external_session_ref,
        )
        self._sessions[session_id] = info
        return info

    def transition(self, session_id: str, to_state: SessionState) -> None:
        info = self._sessions.get(session_id)
        if info is None:
            msg = f"Unknown session: {session_id}"
            raise KeyError(msg)

        # 'closed' is reachable from any non-closed state
        if to_state == SessionState.CLOSED and info.state != SessionState.CLOSED:
            info.state = to_state
            return

        allowed = _TRANSITIONS.get(info.state, set())
        if to_state not in allowed:
            msg = f"Cannot transition from {info.state.value} to {to_state.value}"
            raise InvalidTransitionError(msg)

        info.state = to_state

    def get(self, session_id: str) -> SessionInfo | None:
        return self._sessions.get(session_id)

    def list_by_state(self, state: SessionState) -> list[SessionInfo]:
        return [s for s in self._sessions.values() if s.state == state]
