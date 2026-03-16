from __future__ import annotations

from miniautogen.core.contracts.agentic_loop import (
    AgenticLoopState,
    ConversationPolicy,
    RouterDecision,
)


def detect_stagnation(history: list[RouterDecision], window: int) -> bool:
    if len(history) < window:
        return False
    recent = history[-window:]
    first = recent[0]
    return all(
        item.next_agent == first.next_agent
        and item.missing_information == first.missing_information
        for item in recent
    )


def should_stop_loop(
    state: AgenticLoopState, policy: ConversationPolicy
) -> tuple[bool, str | None]:
    if state.turn_count >= policy.max_turns:
        return True, "max_turns"
    return False, None
