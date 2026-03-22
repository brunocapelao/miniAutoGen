"""Tests for prompt cascade resolution."""
from __future__ import annotations

from typing import Any

import pytest

from miniautogen.core.contracts.interaction import InteractionStrategy


class FakeStrategy:
    async def build_prompt(self, action: str, context: dict[str, Any]) -> str:
        return f"strategy prompt for {action}"

    async def parse_response(self, action: str, raw: str) -> Any:
        return {"strategy_parsed": raw}


class TestResolvePrompt:
    @pytest.mark.anyio()
    async def test_strategy_wins_over_yaml_and_default(self) -> None:
        from miniautogen.core.runtime.prompt_resolver import resolve_prompt

        result = await resolve_prompt(
            action="contribute",
            context={"topic": "AI"},
            strategy=FakeStrategy(),
            flow_prompts={"contribute": "YAML: {topic}"},
            default_prompt="default prompt",
        )
        assert result == "strategy prompt for contribute"

    @pytest.mark.anyio()
    async def test_yaml_wins_over_default(self) -> None:
        from miniautogen.core.runtime.prompt_resolver import resolve_prompt

        result = await resolve_prompt(
            action="contribute",
            context={"topic": "AI"},
            strategy=None,
            flow_prompts={"contribute": "YAML: {topic}"},
            default_prompt="default prompt",
        )
        assert result == "YAML: AI"

    @pytest.mark.anyio()
    async def test_default_used_when_no_strategy_or_yaml(self) -> None:
        from miniautogen.core.runtime.prompt_resolver import resolve_prompt

        result = await resolve_prompt(
            action="contribute",
            context={"topic": "AI"},
            strategy=None,
            flow_prompts={},
            default_prompt="default prompt",
        )
        assert result == "default prompt"

    @pytest.mark.anyio()
    async def test_yaml_template_substitutes_variables(self) -> None:
        from miniautogen.core.runtime.prompt_resolver import resolve_prompt

        result = await resolve_prompt(
            action="review",
            context={"target": "agent-b", "content": "some text"},
            strategy=None,
            flow_prompts={"review": "Evaluate {target}'s work: {content}"},
            default_prompt="default",
        )
        assert result == "Evaluate agent-b's work: some text"

    @pytest.mark.anyio()
    async def test_yaml_template_ignores_missing_variables(self) -> None:
        from miniautogen.core.runtime.prompt_resolver import resolve_prompt

        result = await resolve_prompt(
            action="contribute",
            context={"topic": "AI"},
            strategy=None,
            flow_prompts={"contribute": "Do {topic} with {missing_var}"},
            default_prompt="default",
        )
        # Missing vars should remain as-is (safe fallback)
        assert result == "Do AI with {missing_var}"

    @pytest.mark.anyio()
    async def test_yaml_for_different_action_falls_to_default(self) -> None:
        from miniautogen.core.runtime.prompt_resolver import resolve_prompt

        result = await resolve_prompt(
            action="consolidate",
            context={},
            strategy=None,
            flow_prompts={"contribute": "only contribute template"},
            default_prompt="consolidate default",
        )
        assert result == "consolidate default"
