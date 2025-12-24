from abc import ABC, abstractmethod
from typing import List, Optional
from miniautogen.schemas import Message

class ChatRepository(ABC):
    """
    Abstract interface for chat persistence.
    """

    @abstractmethod
    async def add_message(self, message: Message) -> None:
        """
        Adds a message to the repository.
        """
        pass

    @abstractmethod
    async def get_messages(self, limit: int = 100, offset: int = 0) -> List[Message]:
        """
        Retrieves messages from the repository with pagination.
        """
        pass

    @abstractmethod
    async def remove_message(self, message_id: int) -> None:
        """
        Removes a message by ID.
        """
        pass
