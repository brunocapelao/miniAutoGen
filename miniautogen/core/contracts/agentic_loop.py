from __future__ import annotations

from pydantic import BaseModel, model_validator


class RouterDecision(BaseModel):
    current_state_summary: str
    missing_information: str
    next_agent: str | None = None
    terminate: bool = False
    stagnation_risk: float = 0.0

    @model_validator(mode="after")
    def validate_routing(self) -> "RouterDecision":
        if not self.terminate and not self.next_agent:
            raise ValueError("next_agent is required when not terminating")
        if not 0.0 <= self.stagnation_risk <= 1.0:
            raise ValueError("stagnation_risk must be between 0.0 and 1.0")
        return self


class ConversationPolicy(BaseModel):
    max_turns: int = 8
    budget_cap: float | None = None
    timeout_seconds: float = 120.0
    stagnation_window: int = 2


class AgenticLoopState(BaseModel):
    active_agent: str | None = None
    turn_count: int = 0
    accepted_output: str | None = None
