from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime

class Message(BaseModel):
    """
    Represents a message in the system.
    """
    id: Optional[int] = Field(None, description="The unique identifier of the message.")
    sender_id: str = Field(..., description="The ID of the message sender.")
    content: str = Field(..., description="The content of the message.")
    timestamp: datetime = Field(default_factory=datetime.now, description="The timestamp of the message.")
    additional_info: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata for the message.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sender_id": "agent_1",
                "content": "Hello, world!",
                "timestamp": "2023-01-01T12:00:00",
                "additional_info": {"model": "gpt-4"}
            }
        }
    )

class AgentConfig(BaseModel):
    """
    Configuration for an agent.
    """
    agent_id: str
    name: str
    role: str
    description: Optional[str] = None

class ChatState(BaseModel):
    """
    Represents the state of a chat session.
    """
    context: Dict[str, Any] = Field(default_factory=dict)
    active_agent_id: Optional[str] = None
    messages: List[Message] = Field(default_factory=list)
