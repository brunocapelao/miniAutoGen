"""Tests for miniautogen.agent.agent — covering uncovered lines 46-59, 72, 76-79."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from miniautogen.agent.agent import Agent
from miniautogen.pipeline.pipeline import ChatPipelineState, Pipeline


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestAgentConstruction:
    def test_basic_construction(self) -> None:
        agent = Agent(agent_id="a1", name="Alice", role="analyst")
        assert agent.agent_id == "a1"
        assert agent.name == "Alice"
        assert agent.role == "analyst"
        assert agent.pipeline is None
        assert agent.status == "available"

    def test_construction_with_pipeline(self) -> None:
        pipeline = Pipeline()
        agent = Agent(agent_id="a2", name="Bob", role="coder", pipeline=pipeline)
        assert agent.pipeline is pipeline

    def test_get_status(self) -> None:
        """Covers line 72."""
        agent = Agent(agent_id="a1", name="Alice", role="analyst")
        assert agent.get_status() == "available"


# ---------------------------------------------------------------------------
# from_json  (lines 76-79)
# ---------------------------------------------------------------------------


class TestAgentFromJson:
    def test_from_json_success(self) -> None:
        """Covers lines 75-79 — happy path."""
        data = {"agent_id": "x1", "name": "Xena", "role": "warrior"}
        agent = Agent.from_json(data)
        assert agent.agent_id == "x1"
        assert agent.name == "Xena"
        assert agent.role == "warrior"
        assert agent.pipeline is None

    def test_from_json_extra_keys_ignored(self) -> None:
        data = {"agent_id": "x2", "name": "Y", "role": "r", "extra": 42}
        agent = Agent.from_json(data)
        assert agent.agent_id == "x2"

    def test_from_json_missing_agent_id(self) -> None:
        """Covers lines 77-78 — validation branch."""
        with pytest.raises(ValueError, match="agent_id"):
            Agent.from_json({"name": "N", "role": "R"})

    def test_from_json_missing_name(self) -> None:
        with pytest.raises(ValueError, match="name"):
            Agent.from_json({"agent_id": "a", "role": "R"})

    def test_from_json_missing_role(self) -> None:
        with pytest.raises(ValueError, match="role"):
            Agent.from_json({"agent_id": "a", "name": "N"})

    def test_from_json_empty_dict(self) -> None:
        with pytest.raises(ValueError):
            Agent.from_json({})


# ---------------------------------------------------------------------------
# generate_reply  (lines 46-59, 66-68)
# ---------------------------------------------------------------------------


class TestAgentGenerateReply:
    @pytest.mark.asyncio
    async def test_without_pipeline_returns_default(self) -> None:
        """Covers lines 66-68 — no pipeline branch."""
        agent = Agent(agent_id="a1", name="Alice", role="analyst")
        state = ChatPipelineState(messages=[])
        reply = await agent.generate_reply(state)
        assert "Alice" in reply
        assert "don't have a pipeline" in reply

    @pytest.mark.asyncio
    async def test_with_pipeline_reply_in_state(self) -> None:
        """Covers lines 46-59 — pipeline returns state with 'reply' key."""
        result_state = ChatPipelineState(reply="Generated answer")
        pipeline = MagicMock(spec=Pipeline)
        pipeline.run = AsyncMock(return_value=result_state)

        agent = Agent(agent_id="a1", name="Alice", role="analyst", pipeline=pipeline)
        state = ChatPipelineState(messages=[{"role": "user", "content": "hi"}])
        reply = await agent.generate_reply(state)

        pipeline.run.assert_awaited_once_with(state)
        assert reply == "Generated answer"

    @pytest.mark.asyncio
    async def test_with_pipeline_missing_reply_key(self) -> None:
        """Covers lines 59-64 — pipeline runs but 'reply' not in state (fallback)."""
        result_state = ChatPipelineState(other_data="something")
        pipeline = MagicMock(spec=Pipeline)
        pipeline.run = AsyncMock(return_value=result_state)

        agent = Agent(agent_id="a1", name="Bob", role="coder", pipeline=pipeline)
        state = ChatPipelineState(messages=[])
        reply = await agent.generate_reply(state)

        pipeline.run.assert_awaited_once_with(state)
        assert "Bob" in reply
        assert "no 'reply' in state" in reply.lower() or "reply" in reply
