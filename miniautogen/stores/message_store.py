from abc import ABC, abstractmethod

from miniautogen.schemas import Message


class MessageStore(ABC):
    """Canonical persistence contract for chat messages."""

    @abstractmethod
    async def add_message(self, message: Message) -> None:
        """Persist a message."""

    @abstractmethod
    async def get_messages(self, limit: int = 100, offset: int = 0) -> list[Message]:
        """Fetch persisted messages."""

    @abstractmethod
    async def remove_message(self, message_id: int) -> None:
        """Remove a persisted message by identifier."""
