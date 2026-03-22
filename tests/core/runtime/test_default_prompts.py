"""Tests for default prompt builders extracted from AgentRuntime."""
from __future__ import annotations

import pytest

from miniautogen.core.contracts.deliberation import (
    Contribution,
    DeliberationState,
    Review,
)


class TestDefaultContributePrompt:
    def test_contains_topic(self) -> None:
        from miniautogen.core.runtime.default_prompts import build_default_contribute_prompt

        prompt = build_default_contribute_prompt(topic="AI safety")
        assert "AI safety" in prompt
        assert "JSON" in prompt  # default expects JSON

    def test_returns_string(self) -> None:
        from miniautogen.core.runtime.default_prompts import build_default_contribute_prompt

        result = build_default_contribute_prompt(topic="test")
        assert isinstance(result, str)


class TestDefaultReviewPrompt:
    def test_contains_target_and_content(self) -> None:
        from miniautogen.core.runtime.default_prompts import build_default_review_prompt

        contrib = Contribution(
            participant_id="agent-a", title="Title", content={"key": "val"}
        )
        prompt = build_default_review_prompt(target_id="agent-a", contribution=contrib)
        assert "agent-a" in prompt
        assert "Title" in prompt

    def test_returns_string(self) -> None:
        from miniautogen.core.runtime.default_prompts import build_default_review_prompt

        contrib = Contribution(
            participant_id="other", title="T", content={}
        )
        result = build_default_review_prompt(target_id="other", contribution=contrib)
        assert isinstance(result, str)


class TestDefaultConsolidatePrompt:
    def test_contains_topic_and_summaries(self) -> None:
        from miniautogen.core.runtime.default_prompts import build_default_consolidate_prompt

        contribs = [
            Contribution(participant_id="a", title="T1", content={}),
        ]
        reviews = [
            Review(
                reviewer_id="b", target_id="a", target_title="T1",
                strengths=["good"], concerns=[], questions=[],
            ),
        ]
        prompt = build_default_consolidate_prompt(
            topic="AI", contributions=contribs, reviews=reviews
        )
        assert "AI" in prompt
        assert "a" in prompt
        assert "b" in prompt


class TestDefaultFinalDocumentPrompt:
    def test_contains_state_info(self) -> None:
        from miniautogen.core.runtime.default_prompts import build_default_final_document_prompt

        state = DeliberationState(
            review_cycle=1,
            leader_decision="Approved",
            is_sufficient=True,
        )
        contribs = [
            Contribution(participant_id="a", title="T1", content={"x": 1}),
        ]
        prompt = build_default_final_document_prompt(state=state, contributions=contribs)
        assert "Approved" in prompt
        assert "a" in prompt


class TestDefaultRoutePrompt:
    def test_returns_string(self) -> None:
        from miniautogen.core.runtime.default_prompts import build_default_route_prompt

        prompt = build_default_route_prompt()
        assert isinstance(prompt, str)
        assert "JSON" in prompt
