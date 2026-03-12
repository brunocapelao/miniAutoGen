from miniautogen.schemas import Message
from miniautogen.stores.message_store import MessageStore


class InMemoryMessageStore(MessageStore):
    """In-memory implementation of the canonical message store contract."""

    def __init__(self):
        self.messages: list[Message] = []
        self._counter = 1

    async def add_message(self, message: Message) -> None:
        if message.id is None:
            message.id = self._counter
            self._counter += 1
        self.messages.append(message)

    async def get_messages(self, limit: int = 100, offset: int = 0) -> list[Message]:
        return self.messages[offset : offset + limit]

    async def remove_message(self, message_id: int) -> None:
        self.messages = [message for message in self.messages if message.id != message_id]
