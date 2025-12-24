from typing import List
from miniautogen.schemas import Message
from miniautogen.storage.repository import ChatRepository

class InMemoryChatRepository(ChatRepository):
    """
    In-memory implementation of ChatRepository.
    """
    def __init__(self):
        self.messages: List[Message] = []
        self._counter = 1

    async def add_message(self, message: Message) -> None:
        if message.id is None:
            message.id = self._counter
            self._counter += 1
        self.messages.append(message)

    async def get_messages(self, limit: int = 100, offset: int = 0) -> List[Message]:
        return self.messages[offset : offset + limit]

    async def remove_message(self, message_id: int) -> None:
        self.messages = [m for m in self.messages if m.id != message_id]
