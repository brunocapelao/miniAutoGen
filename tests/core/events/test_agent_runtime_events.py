from miniautogen.core.events.types import EventType, AGENT_RUNTIME_EVENT_TYPES


def test_new_agent_runtime_events_exist():
    assert EventType.AGENT_INITIALIZED.value == "agent_initialized"
    assert EventType.AGENT_CLOSED.value == "agent_closed"
    assert EventType.AGENT_MEMORY_LOADED.value == "agent_memory_loaded"
    assert EventType.AGENT_MEMORY_SAVED.value == "agent_memory_saved"
    assert EventType.AGENT_DELEGATED.value == "agent_delegated"
    assert EventType.AGENT_DELEGATION_DEPTH_EXCEEDED.value == "agent_delegation_depth_exceeded"


def test_agent_runtime_event_types_set_includes_new():
    new_events = {
        EventType.AGENT_INITIALIZED,
        EventType.AGENT_CLOSED,
        EventType.AGENT_MEMORY_LOADED,
        EventType.AGENT_MEMORY_SAVED,
        EventType.AGENT_DELEGATED,
        EventType.AGENT_DELEGATION_DEPTH_EXCEEDED,
    }
    assert new_events.issubset(AGENT_RUNTIME_EVENT_TYPES)


def test_total_agent_runtime_events():
    # 4 existing + 6 new = 10
    assert len(AGENT_RUNTIME_EVENT_TYPES) == 10
