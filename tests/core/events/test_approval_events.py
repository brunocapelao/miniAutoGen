from miniautogen.core.events.types import (
    APPROVAL_EVENT_TYPES,
    EventType,
)


def test_approval_events_are_enum_members() -> None:
    for evt in APPROVAL_EVENT_TYPES:
        assert isinstance(evt, EventType)


def test_approval_event_count() -> None:
    assert len(APPROVAL_EVENT_TYPES) == 4
