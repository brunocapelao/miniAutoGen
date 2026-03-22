"""Tests for InteractionStrategy protocol."""
from __future__ import annotations

from typing import Any

import pytest

from miniautogen.core.contracts.interaction import InteractionStrategy


class FakeStrategy:
    """A concrete strategy that satisfies the protocol."""

    async def build_prompt(self, action: str, context: dict[str, Any]) -> str:
        return f"Prompt for {action}"

    async def parse_response(self, action: str, raw: str) -> Any:
        return {"parsed": raw}


class IncompleteStrategy:
    """Missing parse_response — should NOT satisfy protocol."""

    async def build_prompt(self, action: str, context: dict[str, Any]) -> str:
        return "prompt"


class TestInteractionStrategyProtocol:
    def test_fake_strategy_satisfies_protocol(self) -> None:
        strategy = FakeStrategy()
        assert isinstance(strategy, InteractionStrategy)

    def test_incomplete_strategy_does_not_satisfy(self) -> None:
        strategy = IncompleteStrategy()
        assert not isinstance(strategy, InteractionStrategy)

    @pytest.mark.anyio()
    async def test_build_prompt_returns_string(self) -> None:
        strategy = FakeStrategy()
        result = await strategy.build_prompt("contribute", {"topic": "AI"})
        assert isinstance(result, str)
        assert "contribute" in result

    @pytest.mark.anyio()
    async def test_parse_response_returns_any(self) -> None:
        strategy = FakeStrategy()
        result = await strategy.parse_response("contribute", '{"key": "val"}')
        assert result == {"parsed": '{"key": "val"}'}
