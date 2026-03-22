"""Tests for FlowConfig response_format and prompts fields."""
from __future__ import annotations

import pytest

from miniautogen.cli.config import FlowConfig


class TestFlowConfigResponseFormat:
    def test_default_response_format_is_json(self) -> None:
        fc = FlowConfig(mode="workflow", participants=["agent1"])
        assert fc.response_format == "json"

    def test_free_text_response_format(self) -> None:
        fc = FlowConfig(
            mode="workflow",
            participants=["agent1"],
            response_format="free_text",
        )
        assert fc.response_format == "free_text"

    def test_structured_response_format(self) -> None:
        fc = FlowConfig(
            mode="workflow",
            participants=["agent1"],
            response_format="structured",
            response_schema="miniautogen.core.contracts.deliberation.Contribution",
        )
        assert fc.response_format == "structured"

    def test_invalid_response_format_raises(self) -> None:
        with pytest.raises(ValueError):
            FlowConfig(
                mode="workflow",
                participants=["agent1"],
                response_format="invalid_format",
            )

    def test_prompts_default_empty(self) -> None:
        fc = FlowConfig(mode="workflow", participants=["agent1"])
        assert fc.prompts == {}

    def test_prompts_with_contribute(self) -> None:
        fc = FlowConfig(
            mode="deliberation",
            participants=["a", "b"],
            leader="a",
            prompts={"contribute": "Review {topic} as {role}."},
        )
        assert fc.prompts["contribute"] == "Review {topic} as {role}."

    def test_response_schema_default_none(self) -> None:
        fc = FlowConfig(mode="workflow", participants=["agent1"])
        assert fc.response_schema is None

    def test_response_schema_with_structured(self) -> None:
        fc = FlowConfig(
            mode="workflow",
            participants=["agent1"],
            response_format="structured",
            response_schema="miniautogen.core.contracts.deliberation.Contribution",
        )
        assert fc.response_schema is not None

    def test_structured_without_schema_raises(self) -> None:
        with pytest.raises(ValueError, match="response_schema"):
            FlowConfig(
                mode="workflow",
                participants=["agent1"],
                response_format="structured",
                # response_schema intentionally omitted
            )
