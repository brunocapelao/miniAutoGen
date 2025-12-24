import pytest
from miniautogen.schemas import Message
from miniautogen.storage.in_memory_repository import InMemoryChatRepository
from miniautogen.chat.chat import Chat
from miniautogen.agent.agent import Agent

@pytest.mark.asyncio
async def test_repository_add_get():
    repo = InMemoryChatRepository()
    msg = Message(sender_id="user", content="hello")
    await repo.add_message(msg)

    msgs = await repo.get_messages()
    assert len(msgs) == 1
    assert msgs[0].content == "hello"
    assert msgs[0].id is not None

@pytest.mark.asyncio
async def test_chat_orchestration():
    chat = Chat(repository=InMemoryChatRepository())
    agent = Agent("test_agent", "Tester", "Testing Role")
    chat.add_agent(agent)

    await chat.add_message("user", "hi")
    msgs = await chat.get_messages()
    assert len(msgs) == 1
    assert msgs[0].sender_id == "user"
