import pytest

from miniautogen.agent.agent import Agent
from miniautogen.chat.chat import Chat
from miniautogen.chat.chatadmin import ChatAdmin
from miniautogen.pipeline.components.components import (
    AgentReplyComponent,
    NextAgentSelectorComponent,
    TerminateChatComponent,
)
from miniautogen.pipeline.pipeline import Pipeline
from miniautogen.storage.in_memory_repository import InMemoryChatRepository


@pytest.mark.asyncio
async def test_chatadmin_increments_round_count_for_each_executed_round():
    chat = Chat(repository=InMemoryChatRepository())
    chat.add_agent(Agent("user", "User", "human"))
    await chat.add_message("user", "hello")

    admin = ChatAdmin(
        "admin",
        "Admin",
        "orchestrator",
        Pipeline([
            NextAgentSelectorComponent(),
            AgentReplyComponent(),
            TerminateChatComponent(),
        ]),
        chat,
        "goal",
        1,
    )

    await admin.run()

    assert admin.round == 1
    assert admin.running is False


@pytest.mark.asyncio
async def test_chatadmin_stops_when_max_rounds_is_reached():
    chat = Chat(repository=InMemoryChatRepository())
    chat.add_agent(Agent("user", "User", "human"))
    await chat.add_message("user", "hello")

    admin = ChatAdmin("admin", "Admin", "role", Pipeline([]), chat, "goal", 0)

    await admin.run()

    assert admin.running is False
