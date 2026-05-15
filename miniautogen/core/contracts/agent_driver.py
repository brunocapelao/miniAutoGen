from __future__ import annotations

from typing import AsyncIterator, Protocol, runtime_checkable

from miniautogen.backends.models import (
    AgentEvent,
    ArtifactRef,
    BackendCapabilities,
    CancelTurnRequest,
    SendTurnRequest,
    StartSessionRequest,
    StartSessionResponse,
)


@runtime_checkable
class AgentDriverProtocol(Protocol):
    """Structural protocol for backend drivers.

    Mirrors AgentDriver ABC exactly. Any object with these methods
    satisfies this protocol via duck typing.
    """

    async def start_session(
        self,
        request: StartSessionRequest,
    ) -> StartSessionResponse:
        ...

    def send_turn(
        self,
        request: SendTurnRequest,
    ) -> AsyncIterator[AgentEvent]:
        ...

    async def cancel_turn(
        self,
        request: CancelTurnRequest,
    ) -> None:
        ...

    async def list_artifacts(
        self,
        session_id: str,
    ) -> list[ArtifactRef]:
        ...

    async def close_session(
        self,
        session_id: str,
    ) -> None:
        ...

    async def capabilities(
        self,
    ) -> BackendCapabilities:
        ...
