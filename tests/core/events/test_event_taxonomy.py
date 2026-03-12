from miniautogen.core.events.types import EventType


def test_event_taxonomy_contains_operational_events() -> None:
    assert EventType.COMPONENT_RETRIED.value == "component_retried"
    assert EventType.CHECKPOINT_SAVED.value == "checkpoint_saved"
    assert EventType.POLICY_APPLIED.value == "policy_applied"


def test_event_taxonomy_contains_terminal_run_events() -> None:
    assert EventType.RUN_CANCELLED.value == "run_cancelled"
    assert EventType.RUN_TIMED_OUT.value == "run_timed_out"
