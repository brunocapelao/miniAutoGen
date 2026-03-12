from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Message(BaseModel):
    """Represents a message exchanged by the framework."""

    id: int | None = Field(None, description="The unique identifier of the message.")
    sender_id: str = Field(..., description="The ID of the message sender.")
    content: str = Field(..., description="The message content.")
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="The timestamp of the message.",
    )
    additional_info: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata associated with the message.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sender_id": "agent_1",
                "content": "Hello, world!",
                "timestamp": "2023-01-01T12:00:00",
                "additional_info": {"model": "gpt-4"},
            }
        }
    )
