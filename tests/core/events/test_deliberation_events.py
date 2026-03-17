from miniautogen.core.events.types import (
    DELIBERATION_EVENT_TYPES,
    EventType,
)


def test_deliberation_events_are_enum_members() -> None:
    for evt in DELIBERATION_EVENT_TYPES:
        assert isinstance(evt, EventType)


def test_deliberation_event_type_values() -> None:
    assert EventType.DELIBERATION_STARTED.value == "deliberation_started"
    assert EventType.DELIBERATION_FINISHED.value == "deliberation_finished"
    assert EventType.DELIBERATION_FAILED.value == "deliberation_failed"
