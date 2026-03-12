import pytest

from miniautogen.schemas import Message
from miniautogen.storage.in_memory_repository import InMemoryChatRepository


@pytest.mark.asyncio
async def test_in_memory_repository_keeps_append_order():
    repo = InMemoryChatRepository()

    await repo.add_message(Message(sender_id="user", content="first"))
    await repo.add_message(Message(sender_id="assistant", content="second"))

    items = await repo.get_messages()

    assert [item.content for item in items] == ["first", "second"]
