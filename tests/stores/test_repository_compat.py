import pytest

from miniautogen.core.contracts import Message
from miniautogen.storage.in_memory_repository import InMemoryChatRepository
from miniautogen.stores import InMemoryMessageStore


@pytest.mark.asyncio
async def test_legacy_repository_remains_compatible_with_store_contract() -> None:
    repository = InMemoryChatRepository()
    message = Message(sender_id="user", content="hello")

    await repository.add_message(message)

    messages = await repository.get_messages()
    assert messages == [message]


@pytest.mark.asyncio
async def test_store_and_legacy_repository_share_the_same_message_shape() -> None:
    repository = InMemoryChatRepository()
    store = InMemoryMessageStore()
    message = Message(sender_id="assistant", content="hello")

    await repository.add_message(message)
    await store.add_message(message.model_copy())

    assert await repository.get_messages() == [message]
    assert await store.get_messages() == [message.model_copy(update={"id": 1})]
