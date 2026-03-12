import pytest

from miniautogen.chat.chat import Chat
from miniautogen.storage.in_memory_repository import InMemoryChatRepository


@pytest.mark.asyncio
async def test_chat_add_message_returns_message_and_persists_it():
    chat = Chat(repository=InMemoryChatRepository())

    message = await chat.add_message("user", "hello")
    messages = await chat.get_messages()

    assert message.sender_id == "user"
    assert message.content == "hello"
    assert len(messages) == 1
    assert messages[0].content == "hello"
