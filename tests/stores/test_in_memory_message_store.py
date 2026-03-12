import pytest

from miniautogen.core.contracts import Message
from miniautogen.stores import InMemoryMessageStore


@pytest.mark.asyncio
async def test_in_memory_message_store_roundtrip() -> None:
    store = InMemoryMessageStore()
    message = Message(sender_id="user", content="hello")

    await store.add_message(message)

    messages = await store.get_messages()

    assert messages == [message]
    assert message.id == 1


@pytest.mark.asyncio
async def test_in_memory_message_store_removes_message_by_index() -> None:
    store = InMemoryMessageStore()
    first = Message(sender_id="user", content="first")
    second = Message(sender_id="assistant", content="second")
    await store.add_message(first)
    await store.add_message(second)

    await store.remove_message(first.id or 0)

    messages = await store.get_messages()
    assert messages == [second]
