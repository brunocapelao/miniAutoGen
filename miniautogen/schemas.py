from typing import Any

from pydantic import BaseModel, Field

from miniautogen.core.contracts.message import Message


class AgentConfig(BaseModel):
    """Configuration for an agent."""

    agent_id: str
    name: str
    role: str
    description: str | None = None

class ChatState(BaseModel):
    """Represents the state of a chat session."""

    context: dict[str, Any] = Field(default_factory=dict)
    active_agent_id: str | None = None
    messages: list[Message] = Field(default_factory=list)
