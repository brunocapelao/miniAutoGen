"""Tests for supervision event types in the EventType enum."""

from miniautogen.core.events.types import (
    SUPERVISION_EVENT_TYPES,
    EventType,
)


class TestSupervisionEventTypes:
    """Verify all 6 supervision event types exist and are grouped."""

    def test_supervision_failure_received_exists(self) -> None:
        assert EventType.SUPERVISION_FAILURE_RECEIVED == "supervision_failure_received"

    def test_supervision_decision_made_exists(self) -> None:
        assert EventType.SUPERVISION_DECISION_MADE == "supervision_decision_made"

    def test_supervision_restart_started_exists(self) -> None:
        assert EventType.SUPERVISION_RESTART_STARTED == "supervision_restart_started"

    def test_supervision_circuit_opened_exists(self) -> None:
        assert EventType.SUPERVISION_CIRCUIT_OPENED == "supervision_circuit_opened"

    def test_supervision_escalated_exists(self) -> None:
        assert EventType.SUPERVISION_ESCALATED == "supervision_escalated"

    def test_supervision_retry_succeeded_exists(self) -> None:
        assert EventType.SUPERVISION_RETRY_SUCCEEDED == "supervision_retry_succeeded"

    def test_supervision_event_types_set_contains_all(self) -> None:
        expected = {
            EventType.SUPERVISION_FAILURE_RECEIVED,
            EventType.SUPERVISION_DECISION_MADE,
            EventType.SUPERVISION_RESTART_STARTED,
            EventType.SUPERVISION_CIRCUIT_OPENED,
            EventType.SUPERVISION_ESCALATED,
            EventType.SUPERVISION_RETRY_SUCCEEDED,
        }
        assert SUPERVISION_EVENT_TYPES == expected

    def test_supervision_event_types_are_enum_members(self) -> None:
        """Set uses enum members, not .value strings."""
        for member in SUPERVISION_EVENT_TYPES:
            assert isinstance(member, EventType)
