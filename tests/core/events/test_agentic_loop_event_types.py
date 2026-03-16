"""Tests for AgenticLoop event types in the EventType enum."""

from miniautogen.core.events.types import EventType


def test_event_type_agentic_loop_started_exists() -> None:
    assert EventType.AGENTIC_LOOP_STARTED.value == "agentic_loop_started"


def test_event_type_router_decision_exists() -> None:
    assert EventType.ROUTER_DECISION.value == "router_decision"


def test_event_type_agent_replied_exists() -> None:
    assert EventType.AGENT_REPLIED.value == "agent_replied"


def test_event_type_agentic_loop_stopped_exists() -> None:
    assert EventType.AGENTIC_LOOP_STOPPED.value == "agentic_loop_stopped"


def test_event_type_stagnation_detected_exists() -> None:
    assert EventType.STAGNATION_DETECTED.value == "stagnation_detected"


def test_agentic_loop_event_types_are_strings() -> None:
    agentic_events = [
        EventType.AGENTIC_LOOP_STARTED,
        EventType.ROUTER_DECISION,
        EventType.AGENT_REPLIED,
        EventType.AGENTIC_LOOP_STOPPED,
        EventType.STAGNATION_DETECTED,
    ]
    for event in agentic_events:
        assert isinstance(event.value, str)
        assert isinstance(event, str)
