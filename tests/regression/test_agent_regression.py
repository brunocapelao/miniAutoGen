import pytest

from miniautogen.agent.agent import Agent
from miniautogen.pipeline.pipeline import ChatPipelineState


@pytest.mark.asyncio
async def test_agent_without_pipeline_returns_default_message():
    agent = Agent("a1", "Assistant", "helper")

    reply = await agent.generate_reply(ChatPipelineState())

    assert "don't have a pipeline" in reply.lower()
