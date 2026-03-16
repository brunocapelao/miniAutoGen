from miniautogen.core.contracts.agentic_loop import (
    AgenticLoopState,
    ConversationPolicy,
    RouterDecision,
)
from miniautogen.core.runtime.agentic_loop import detect_stagnation, should_stop_loop


def test_detect_stagnation_when_same_agent_repeats_without_change() -> None:
    history = [
        RouterDecision(
            current_state_summary="A",
            missing_information="B",
            next_agent="QA",
            terminate=False,
            stagnation_risk=0.1,
        ),
        RouterDecision(
            current_state_summary="A",
            missing_information="B",
            next_agent="QA",
            terminate=False,
            stagnation_risk=0.1,
        ),
    ]
    assert detect_stagnation(history, window=2) is True


def test_should_stop_loop_when_max_turns_is_reached() -> None:
    policy = ConversationPolicy(max_turns=3, timeout_seconds=120.0)
    state = AgenticLoopState(active_agent="Planner", turn_count=3)
    stop, reason = should_stop_loop(state, policy)
    assert stop is True
    assert reason == "max_turns"
