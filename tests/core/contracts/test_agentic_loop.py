import pytest
from pydantic import ValidationError

from miniautogen.core.contracts.agentic_loop import (
    AgenticLoopState,
    ConversationPolicy,
    RouterDecision,
)


def test_router_decision_requires_next_agent_or_terminate() -> None:
    decision = RouterDecision(
        current_state_summary="Resumo",
        missing_information="Falta revisão",
        next_agent="QA_Agent",
        terminate=False,
        stagnation_risk=0.1,
    )
    assert decision.next_agent == "QA_Agent"
    assert decision.terminate is False


def test_conversation_policy_has_basic_breakers() -> None:
    policy = ConversationPolicy(max_turns=8, budget_cap=2.5, timeout_seconds=120.0)
    assert policy.max_turns == 8
    assert policy.budget_cap == 2.5


def test_agentic_loop_state_tracks_turns_and_active_agent() -> None:
    state = AgenticLoopState(active_agent="Planner", turn_count=2)
    assert state.active_agent == "Planner"
    assert state.turn_count == 2


def test_router_decision_rejects_missing_next_agent_when_not_terminating() -> None:
    with pytest.raises(ValidationError):
        RouterDecision(
            current_state_summary="Resumo",
            missing_information="Falta algo",
            next_agent=None,
            terminate=False,
            stagnation_risk=0.2,
        )


def test_router_decision_accepts_terminate_without_next_agent() -> None:
    decision = RouterDecision(
        current_state_summary="Resumo final",
        missing_information="Nada",
        next_agent=None,
        terminate=True,
        stagnation_risk=0.0,
    )
    assert decision.terminate is True
