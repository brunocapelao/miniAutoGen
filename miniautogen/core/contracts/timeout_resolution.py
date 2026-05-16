"""Timeout resolution with 4-level precedence: agent > round > flow > engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TimeoutSource = Literal["agent", "round", "flow", "engine"]


@dataclass(frozen=True)
class ResolvedTimeout:
    seconds: float
    source: TimeoutSource


def resolve_timeout(
    *,
    agent_id: str,
    round_name: str | None,
    agent_timeouts: dict[str, float],
    round_timeouts: dict[str, float],
    flow_timeout: float | None,
    engine_timeout: float,
) -> ResolvedTimeout:
    if agent_id in agent_timeouts:
        return ResolvedTimeout(agent_timeouts[agent_id], "agent")
    if round_name and round_name in round_timeouts:
        return ResolvedTimeout(round_timeouts[round_name], "round")
    if flow_timeout is not None:
        return ResolvedTimeout(flow_timeout, "flow")
    return ResolvedTimeout(engine_timeout, "engine")
