"""Shared fixtures for backend driver tests."""

from __future__ import annotations

from typing import AsyncIterator

import pytest

from miniautogen.backends.driver import AgentDriver
from miniautogen.backends.errors import CancelNotSupportedError
from miniautogen.backends.models import (
    AgentEvent,
    ArtifactRef,
    BackendCapabilities,
    CancelTurnRequest,
    SendTurnRequest,
    StartSessionRequest,
    StartSessionResponse,
)


class FakeDriver(AgentDriver):
    """In-memory driver for testing the contract.

    Note: send_turn uses ``async def`` + ``yield`` (async generator),
    which satisfies the ABC's ``def -> AsyncIterator`` contract (D1).
    """

    def __init__(
        self,
        caps: BackendCapabilities | None = None,
        events: list[AgentEvent] | None = None,
        artifacts: list[ArtifactRef] | None = None,
    ) -> None:
        self._caps = caps or BackendCapabilities(
            sessions=True, streaming=True, cancel=True, artifacts=True,
        )
        self._events = events or []
        self._artifacts = artifacts or []
        self._sessions: dict[str, bool] = {}
        self._next_id = 0
        self.cancelled: list[str] = []

    async def start_session(
        self, request: StartSessionRequest,
    ) -> StartSessionResponse:
        self._next_id += 1
        sid = f"fake_sess_{self._next_id}"
        self._sessions[sid] = True
        return StartSessionResponse(
            session_id=sid,
            capabilities=self._caps,
        )

    async def send_turn(
        self, request: SendTurnRequest,
    ) -> AsyncIterator[AgentEvent]:
        turn_id = f"turn_{self._next_id}"
        self._next_id += 1
        for ev in self._events:
            yield AgentEvent(
                type=ev.type,
                session_id=request.session_id,
                turn_id=turn_id,
                payload=ev.payload,
            )
        yield AgentEvent(
            type="turn_completed",
            session_id=request.session_id,
            turn_id=turn_id,
        )

    async def cancel_turn(
        self, request: CancelTurnRequest,
    ) -> None:
        if not self._caps.cancel:
            raise CancelNotSupportedError("FakeDriver: cancel disabled")
        self.cancelled.append(request.session_id)

    async def list_artifacts(self, session_id: str) -> list[ArtifactRef]:
        return list(self._artifacts)

    async def close_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    async def capabilities(self) -> BackendCapabilities:
        return self._caps


@pytest.fixture
def fake_driver() -> FakeDriver:
    return FakeDriver()


@pytest.fixture
def fake_driver_with_events() -> FakeDriver:
    return FakeDriver(
        events=[
            AgentEvent(type="message_delta", session_id="", payload={"delta": "Hello"}),
            AgentEvent(type="message_completed", session_id="", payload={"text": "Hello world"}),
        ],
    )
