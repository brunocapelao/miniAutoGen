# tests/backends/test_event_types.py
"""Tests for backend-specific event types."""

from miniautogen.core.events.types import BACKEND_EVENT_TYPES, EventType


class TestBackendEventTypes:
    def test_backend_events_exist_in_enum(self) -> None:
        expected = {
            "backend_session_started",
            "backend_turn_started",
            "backend_message_delta",
            "backend_message_completed",
            "backend_tool_call_requested",
            "backend_tool_call_executed",
            "backend_artifact_emitted",
            "backend_warning",
            "backend_error",
            "backend_turn_completed",
            "backend_session_closed",
        }
        for name in expected:
            assert hasattr(EventType, name.upper()), f"Missing: {name}"

    def test_backend_event_types_set(self) -> None:
        assert "backend_session_started" in BACKEND_EVENT_TYPES
        assert "backend_turn_completed" in BACKEND_EVENT_TYPES
        assert len(BACKEND_EVENT_TYPES) == 11

    def test_no_collision_with_existing_events(self) -> None:
        # Backend events are prefixed with 'backend_' to avoid collisions
        non_backend = {
            e.value for e in EventType
            if not e.value.startswith("backend_")
        }
        assert non_backend & BACKEND_EVENT_TYPES == set()
