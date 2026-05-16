"""Tests for resolve_timeout precedence matrix — Spec 013."""

import pytest

from miniautogen.core.contracts.timeout_resolution import (
    ResolvedTimeout,
    resolve_timeout,
)


class TestResolveTimeout:
    """Cover the full precedence matrix: agent > round > flow > engine."""

    def test_agent_precedence(self) -> None:
        """Agent-level timeout wins when set."""
        result = resolve_timeout(
            agent_id="engenheiro",
            round_name="contribute",
            agent_timeouts={"engenheiro": 60.0},
            round_timeouts={"contribute": 90.0},
            flow_timeout=120.0,
            engine_timeout=300.0,
        )
        assert result.seconds == 60.0
        assert result.source == "agent"

    def test_round_precedence_when_agent_missing(self) -> None:
        """Round-level timeout wins when agent timeout is absent."""
        result = resolve_timeout(
            agent_id="engenheiro",
            round_name="contribute",
            agent_timeouts={},
            round_timeouts={"contribute": 90.0},
            flow_timeout=120.0,
            engine_timeout=300.0,
        )
        assert result.seconds == 90.0
        assert result.source == "round"

    def test_flow_precedence_when_below_missing(self) -> None:
        """Flow-level timeout wins when agent and round are absent."""
        result = resolve_timeout(
            agent_id="engenheiro",
            round_name="contribute",
            agent_timeouts={},
            round_timeouts={},
            flow_timeout=120.0,
            engine_timeout=300.0,
        )
        assert result.seconds == 120.0
        assert result.source == "flow"

    def test_engine_fallback(self) -> None:
        """Engine timeout is the final fallback."""
        result = resolve_timeout(
            agent_id="engenheiro",
            round_name="contribute",
            agent_timeouts={},
            round_timeouts={},
            flow_timeout=None,
            engine_timeout=300.0,
        )
        assert result.seconds == 300.0
        assert result.source == "engine"

    def test_agent_still_wins_when_round_also_set(self) -> None:
        """Agent beats round when both are set (precedence)."""
        result = resolve_timeout(
            agent_id="engenheiro",
            round_name="contribute",
            agent_timeouts={"engenheiro": 60.0},
            round_timeouts={"contribute": 90.0},
            flow_timeout=120.0,
            engine_timeout=300.0,
        )
        assert result.seconds == 60.0
        assert result.source == "agent"
