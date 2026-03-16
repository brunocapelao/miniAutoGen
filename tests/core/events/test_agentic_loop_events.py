from miniautogen.core.events.types import AGENTIC_LOOP_EVENT_TYPES, EventType


def test_agentic_loop_event_types_include_router_and_stop_events() -> None:
    assert EventType.AGENTIC_LOOP_STARTED.value in AGENTIC_LOOP_EVENT_TYPES
    assert EventType.ROUTER_DECISION.value in AGENTIC_LOOP_EVENT_TYPES
    assert EventType.AGENT_REPLIED.value in AGENTIC_LOOP_EVENT_TYPES
    assert EventType.AGENTIC_LOOP_STOPPED.value in AGENTIC_LOOP_EVENT_TYPES
    assert EventType.STAGNATION_DETECTED.value in AGENTIC_LOOP_EVENT_TYPES
