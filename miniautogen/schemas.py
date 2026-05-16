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


class MailboxConfig(BaseModel):
    enabled: bool = False
    buffer_size: int = 256
    idle_threshold_seconds: float = 5.0


class PlanApprovalConfig(BaseModel):
    timeout_seconds: float = 300.0
    required_for: list[str] = Field(default_factory=list)
