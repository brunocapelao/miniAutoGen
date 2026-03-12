import pytest

from miniautogen.chat.chat import Chat
from miniautogen.stores import InMemoryMessageStore


@pytest.mark.asyncio
async def test_chat_accepts_new_message_store_contract() -> None:
    chat = Chat(repository=InMemoryMessageStore())

    message = await chat.add_message(sender_id="agent_1", content="hello")
    messages = await chat.get_messages()

    assert messages == [message]
    assert chat.context.messages == [message]
