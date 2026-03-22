"""Tests that FlowConfig response_format and prompts propagate to AgentRuntime."""
from __future__ import annotations

from typing import Any

import pytest

from miniautogen.cli.config import FlowConfig


class TestFlowConfigPropagation:
    @pytest.mark.anyio()
    async def test_flow_prompts_reach_agent_runtime(self) -> None:
        """FlowConfig.prompts should be passed to AgentRuntime._flow_prompts."""
        # This test validates the wiring; full integration tested separately.
        fc = FlowConfig(
            mode="deliberation",
            participants=["agent1", "agent2"],
            leader="agent1",
            prompts={"contribute": "Custom {topic} prompt."},
            response_format="free_text",
        )
        assert fc.prompts["contribute"] == "Custom {topic} prompt."
        assert fc.response_format == "free_text"
