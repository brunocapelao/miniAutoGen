# tests/backends/test_sessions.py
"""Tests for backend session management."""

from __future__ import annotations

import pytest

from miniautogen.backends.models import BackendCapabilities
from miniautogen.backends.sessions import (
    InvalidTransitionError,
    SessionManager,
    SessionState,
)


class TestSessionState:
    def test_initial_state_is_created(self) -> None:
        assert SessionState.CREATED.value == "created"

    def test_all_states_defined(self) -> None:
        names = {s.value for s in SessionState}
        assert names == {
            "created", "active", "busy",
            "interrupted", "completed", "failed", "closed",
        }


class TestSessionManager:
    def test_create_session(self) -> None:
        mgr = SessionManager()
        info = mgr.create(
            session_id="s1",
            backend_id="claude_code",
            capabilities=BackendCapabilities(sessions=True),
        )
        assert info.session_id == "s1"
        assert info.state == SessionState.CREATED

    def test_transition_created_to_active(self) -> None:
        mgr = SessionManager()
        mgr.create(session_id="s1", backend_id="b1", capabilities=BackendCapabilities())
        mgr.transition("s1", SessionState.ACTIVE)
        assert mgr.get("s1").state == SessionState.ACTIVE

    def test_transition_active_to_busy(self) -> None:
        mgr = SessionManager()
        mgr.create(session_id="s1", backend_id="b1", capabilities=BackendCapabilities())
        mgr.transition("s1", SessionState.ACTIVE)
        mgr.transition("s1", SessionState.BUSY)
        assert mgr.get("s1").state == SessionState.BUSY

    def test_transition_busy_to_active(self) -> None:
        mgr = SessionManager()
        mgr.create(session_id="s1", backend_id="b1", capabilities=BackendCapabilities())
        mgr.transition("s1", SessionState.ACTIVE)
        mgr.transition("s1", SessionState.BUSY)
        mgr.transition("s1", SessionState.ACTIVE)
        assert mgr.get("s1").state == SessionState.ACTIVE

    def test_invalid_transition_raises(self) -> None:
        mgr = SessionManager()
        mgr.create(session_id="s1", backend_id="b1", capabilities=BackendCapabilities())
        with pytest.raises(InvalidTransitionError):
            mgr.transition("s1", SessionState.BUSY)

    def test_close_from_any_non_closed_state(self) -> None:
        mgr = SessionManager()
        mgr.create(session_id="s1", backend_id="b1", capabilities=BackendCapabilities())
        mgr.transition("s1", SessionState.CLOSED)
        assert mgr.get("s1").state == SessionState.CLOSED

    def test_get_unknown_session_returns_none(self) -> None:
        mgr = SessionManager()
        assert mgr.get("nonexistent") is None

    def test_list_active_sessions(self) -> None:
        mgr = SessionManager()
        caps = BackendCapabilities()
        mgr.create(session_id="s1", backend_id="b1", capabilities=caps)
        mgr.create(session_id="s2", backend_id="b1", capabilities=caps)
        mgr.transition("s1", SessionState.ACTIVE)
        mgr.transition("s2", SessionState.ACTIVE)
        mgr.transition("s2", SessionState.CLOSED)
        active = mgr.list_by_state(SessionState.ACTIVE)
        assert len(active) == 1
        assert active[0].session_id == "s1"

    def test_transition_to_failed_from_busy(self) -> None:
        mgr = SessionManager()
        mgr.create(session_id="s1", backend_id="b1", capabilities=BackendCapabilities())
        mgr.transition("s1", SessionState.ACTIVE)
        mgr.transition("s1", SessionState.BUSY)
        mgr.transition("s1", SessionState.FAILED)
        assert mgr.get("s1").state == SessionState.FAILED

    def test_transition_from_closed_raises(self) -> None:
        mgr = SessionManager()
        mgr.create(session_id="s1", backend_id="b1", capabilities=BackendCapabilities())
        mgr.transition("s1", SessionState.CLOSED)
        with pytest.raises(InvalidTransitionError):
            mgr.transition("s1", SessionState.ACTIVE)

    def test_transition_unknown_session_raises(self) -> None:
        mgr = SessionManager()
        with pytest.raises(KeyError, match="Unknown session"):
            mgr.transition("nonexistent", SessionState.ACTIVE)

    def test_duplicate_session_id_raises(self) -> None:
        mgr = SessionManager()
        caps = BackendCapabilities()
        mgr.create(session_id="s1", backend_id="b1", capabilities=caps)
        with pytest.raises(ValueError, match="already exists"):
            mgr.create(session_id="s1", backend_id="b1", capabilities=caps)
