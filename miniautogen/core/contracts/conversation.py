from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from miniautogen.core.contracts.message import Message


class Conversation(BaseModel):
    """Typed conversation history — minimal but useful.

    Immutable-style: add_message returns a new Conversation.
    """

    id: str = ""
    messages: list[Message] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def add_message(self, message: Message) -> Conversation:
        """Return a new Conversation with the message appended."""
        return self.model_copy(update={"messages": [*self.messages, message]})

    def last_n(self, n: int) -> list[Message]:
        """Return the last n messages."""
        return self.messages[-n:] if n > 0 else []

    def by_sender(self, sender_id: str) -> list[Message]:
        """Return all messages from a specific sender."""
        return [m for m in self.messages if m.sender_id == sender_id]
