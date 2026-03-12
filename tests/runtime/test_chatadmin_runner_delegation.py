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
async def test_chatadmin_initializes_runner_and_delegates_execution():
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

    assert hasattr(admin, "_runner")
    assert admin.round == 1
