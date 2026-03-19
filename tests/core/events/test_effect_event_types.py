"""Tests for Phase 2 effect event types and convenience set normalization."""

from __future__ import annotations


class TestEffectEventTypes:
    def test_effect_registered_exists(self) -> None:
        from miniautogen.core.events.types import EventType

        assert EventType.EFFECT_REGISTERED == "effect_registered"

    def test_effect_executed_exists(self) -> None:
        from miniautogen.core.events.types import EventType

        assert EventType.EFFECT_EXECUTED == "effect_executed"

    def test_effect_skipped_exists(self) -> None:
        from miniautogen.core.events.types import EventType

        assert EventType.EFFECT_SKIPPED == "effect_skipped"

    def test_effect_failed_exists(self) -> None:
        from miniautogen.core.events.types import EventType

        assert EventType.EFFECT_FAILED == "effect_failed"

    def test_effect_denied_exists(self) -> None:
        from miniautogen.core.events.types import EventType

        assert EventType.EFFECT_DENIED == "effect_denied"

    def test_effect_stale_reclaimed_exists(self) -> None:
        from miniautogen.core.events.types import EventType

        assert EventType.EFFECT_STALE_RECLAIMED == "effect_stale_reclaimed"

    def test_effect_unprotected_exists(self) -> None:
        from miniautogen.core.events.types import EventType

        assert EventType.EFFECT_UNPROTECTED == "effect_unprotected"

    def test_effect_event_types_convenience_set(self) -> None:
        from miniautogen.core.events.types import EFFECT_EVENT_TYPES, EventType

        expected = {
            EventType.EFFECT_REGISTERED,
            EventType.EFFECT_EXECUTED,
            EventType.EFFECT_SKIPPED,
            EventType.EFFECT_FAILED,
            EventType.EFFECT_DENIED,
            EventType.EFFECT_STALE_RECLAIMED,
            EventType.EFFECT_UNPROTECTED,
        }
        assert EFFECT_EVENT_TYPES == expected

    def test_effect_event_types_contains_enum_members_not_strings(self) -> None:
        from miniautogen.core.events.types import EFFECT_EVENT_TYPES, EventType

        for member in EFFECT_EVENT_TYPES:
            assert isinstance(member, EventType), (
                f"Expected EventType member, got {type(member)}: {member}"
            )


class TestConvenienceSetNormalization:
    """Verify that AGENTIC_LOOP_EVENT_TYPES and BACKEND_EVENT_TYPES
    use enum members (not .value strings), consistent with
    APPROVAL_EVENT_TYPES and DELIBERATION_EVENT_TYPES."""

    def test_agentic_loop_event_types_uses_enum_members(self) -> None:
        from miniautogen.core.events.types import AGENTIC_LOOP_EVENT_TYPES, EventType

        for member in AGENTIC_LOOP_EVENT_TYPES:
            assert isinstance(member, EventType), (
                f"Expected EventType member, got {type(member)}: {member}"
            )

    def test_backend_event_types_uses_enum_members(self) -> None:
        from miniautogen.core.events.types import BACKEND_EVENT_TYPES, EventType

        for member in BACKEND_EVENT_TYPES:
            assert isinstance(member, EventType), (
                f"Expected EventType member, got {type(member)}: {member}"
            )

    def test_agentic_loop_event_types_has_correct_members(self) -> None:
        from miniautogen.core.events.types import AGENTIC_LOOP_EVENT_TYPES, EventType

        expected = {
            EventType.AGENTIC_LOOP_STARTED,
            EventType.ROUTER_DECISION,
            EventType.AGENT_REPLIED,
            EventType.AGENTIC_LOOP_STOPPED,
            EventType.STAGNATION_DETECTED,
        }
        assert AGENTIC_LOOP_EVENT_TYPES == expected

    def test_backend_event_types_has_correct_members(self) -> None:
        from miniautogen.core.events.types import BACKEND_EVENT_TYPES, EventType

        expected = {
            EventType.BACKEND_SESSION_STARTED,
            EventType.BACKEND_TURN_STARTED,
            EventType.BACKEND_MESSAGE_DELTA,
            EventType.BACKEND_MESSAGE_COMPLETED,
            EventType.BACKEND_TOOL_CALL_REQUESTED,
            EventType.BACKEND_TOOL_CALL_EXECUTED,
            EventType.BACKEND_ARTIFACT_EMITTED,
            EventType.BACKEND_WARNING,
            EventType.BACKEND_ERROR,
            EventType.BACKEND_TURN_COMPLETED,
            EventType.BACKEND_SESSION_CLOSED,
        }
        assert BACKEND_EVENT_TYPES == expected
