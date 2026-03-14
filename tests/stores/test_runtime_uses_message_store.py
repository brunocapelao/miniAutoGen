import pytest

from miniautogen.chat.chat import Chat
from miniautogen.stores import InMemoryMessageStore


@pytest.mark.asyncio
async def test_chat_defaults_to_new_message_store() -> None:
    chat = Chat()

    assert isinstance(chat.repository, InMemoryMessageStore)
