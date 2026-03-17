"""Domain models for the backend driver layer.

These models define the contract between MiniAutoGen's core and any
external agent backend (ACP, HTTP bridge, PTY).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, get_args

from pydantic import BaseModel, Field

CapabilityName = Literal[
    "sessions",
    "streaming",
    "cancel",
    "resume",
    "tools",
    "artifacts",
    "multimodal",
]


class BackendCapabilities(BaseModel):
    """Declares what a backend supports.

    Drivers report these at session start. The core uses them to decide
    which features are available (e.g., skip cancel if not supported).
    """

    sessions: bool = False
    streaming: bool = False
    cancel: bool = False
    resume: bool = False
    tools: bool = False
    artifacts: bool = False
    multimodal: bool = False

    def supported(self) -> set[str]:
        """Return the set of capability names that are enabled."""
        return {
            name
            for name in get_args(CapabilityName)
            if getattr(self, name)
        }


class StartSessionRequest(BaseModel):
    """Request to start a new session with a backend."""

    backend_id: str
    system_prompt: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class StartSessionResponse(BaseModel):
    """Response from starting a session."""

    session_id: str
    external_session_ref: str | None = None
    capabilities: BackendCapabilities


class SendTurnRequest(BaseModel):
    """Request to send a turn (one interaction) to a backend."""

    session_id: str
    messages: list[dict[str, Any]]
    metadata: dict[str, Any] = Field(default_factory=dict)


class CancelTurnRequest(BaseModel):
    """Request to cancel an in-progress turn."""

    session_id: str
    reason: str | None = None


class ArtifactRef(BaseModel):
    """Reference to an artifact produced by a backend."""

    artifact_id: str
    kind: str
    name: str | None = None
    uri: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentEvent(BaseModel):
    """Canonical event emitted by a backend during execution.

    All driver implementations must convert their native events into
    this model before yielding them to the core.
    """

    # TODO(review): validate type against canonical set, warn on unknown
    type: str
    session_id: str
    turn_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
