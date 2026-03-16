"""Abstract base class for all backend drivers.

Every driver (ACP, HTTP bridge, PTY) must implement this interface.
The contract test suite in tests/backends/test_driver_contract.py
validates compliance.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator

from miniautogen.backends.models import (
    AgentEvent,
    ArtifactRef,
    BackendCapabilities,
    CancelTurnRequest,
    SendTurnRequest,
    StartSessionRequest,
    StartSessionResponse,
)


class AgentDriver(ABC):
    """Unified interface for external agent backends."""

    @abstractmethod
    async def start_session(
        self,
        request: StartSessionRequest,
    ) -> StartSessionResponse:
        """Start a new session with the backend."""
        ...

    @abstractmethod
    def send_turn(
        self,
        request: SendTurnRequest,
    ) -> AsyncIterator[AgentEvent]:
        """Send a turn and stream back events.

        Declared as a regular method returning AsyncIterator (see D1).
        Implementations use ``async def`` + ``yield`` (async generators).
        Callers iterate directly: ``async for event in driver.send_turn(req):``
        """
        ...

    @abstractmethod
    async def cancel_turn(
        self,
        request: CancelTurnRequest,
    ) -> None:
        """Cancel an in-progress turn.

        Raises CancelNotSupportedError if the driver does not support it.
        """
        ...

    @abstractmethod
    async def list_artifacts(
        self,
        session_id: str,
    ) -> list[ArtifactRef]:
        """List artifacts produced during a session."""
        ...

    @abstractmethod
    async def close_session(
        self,
        session_id: str,
    ) -> None:
        """Close and clean up a session."""
        ...

    @abstractmethod
    async def capabilities(self) -> BackendCapabilities:
        """Report the capabilities this driver supports."""
        ...
