from miniautogen.core.events.types import AGENTIC_LOOP_EVENT_TYPES


def test_agentic_loop_event_types_include_router_and_stop_events() -> None:
    assert "agentic_loop_started" in AGENTIC_LOOP_EVENT_TYPES
    assert "router_decision_emitted" in AGENTIC_LOOP_EVENT_TYPES
    assert "agent_reply_recorded" in AGENTIC_LOOP_EVENT_TYPES
    assert "agentic_loop_stopped" in AGENTIC_LOOP_EVENT_TYPES
