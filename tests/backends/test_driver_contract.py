# tests/backends/test_driver_contract.py
"""Contract test suite for AgentDriver implementations.

Every driver (Fake, ACP, HTTP, PTY) must pass these tests.
To add a new driver: parametrize the ``driver`` fixture.
"""

from __future__ import annotations

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
)

from tests.backends.conftest import FakeDriver


@pytest.fixture
def driver() -> AgentDriver:
    """Default driver under test. Parametrize to add more."""
    return FakeDriver(
        events=[
            AgentEvent(type="message_delta", session_id="", payload={"delta": "hi"}),
        ],
        artifacts=[
            ArtifactRef(artifact_id="art_1", kind="file", name="output.txt"),
        ],
    )


class TestDriverContract:
    """Tests every AgentDriver implementation must pass."""

    @pytest.mark.asyncio
    async def test_start_session_returns_valid_response(
        self, driver: AgentDriver,
    ) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="test"),
        )
        assert resp.session_id
        assert isinstance(resp.capabilities, BackendCapabilities)

    @pytest.mark.asyncio
    async def test_send_turn_yields_events(
        self, driver: AgentDriver,
    ) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="test"),
        )
        events: list[AgentEvent] = []
        async for ev in driver.send_turn(
            SendTurnRequest(
                session_id=resp.session_id,
                messages=[{"role": "user", "content": "hello"}],
            ),
        ):
            events.append(ev)

        assert len(events) >= 1
        assert all(isinstance(e, AgentEvent) for e in events)
        assert all(e.session_id == resp.session_id for e in events)

    @pytest.mark.asyncio
    async def test_send_turn_ends_with_turn_completed(
        self, driver: AgentDriver,
    ) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="test"),
        )
        events: list[AgentEvent] = []
        async for ev in driver.send_turn(
            SendTurnRequest(
                session_id=resp.session_id,
                messages=[{"role": "user", "content": "hello"}],
            ),
        ):
            events.append(ev)

        assert events[-1].type == "turn_completed"

    @pytest.mark.asyncio
    async def test_list_artifacts_returns_list(
        self, driver: AgentDriver,
    ) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="test"),
        )
        artifacts = await driver.list_artifacts(resp.session_id)
        assert isinstance(artifacts, list)
        assert all(isinstance(a, ArtifactRef) for a in artifacts)

    @pytest.mark.asyncio
    async def test_close_session_completes(
        self, driver: AgentDriver,
    ) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="test"),
        )
        await driver.close_session(resp.session_id)

    @pytest.mark.asyncio
    async def test_capabilities_returns_valid_object(
        self, driver: AgentDriver,
    ) -> None:
        caps = await driver.capabilities()
        assert isinstance(caps, BackendCapabilities)

    @pytest.mark.asyncio
    async def test_cancel_turn_when_supported(
        self, driver: AgentDriver,
    ) -> None:
        caps = await driver.capabilities()
        resp = await driver.start_session(
            StartSessionRequest(backend_id="test"),
        )
        if caps.cancel:
            await driver.cancel_turn(
                CancelTurnRequest(session_id=resp.session_id),
            )
        else:
            with pytest.raises(CancelNotSupportedError):
                await driver.cancel_turn(
                    CancelTurnRequest(session_id=resp.session_id),
                )

    @pytest.mark.asyncio
    async def test_events_have_timestamps(
        self, driver: AgentDriver,
    ) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="test"),
        )
        async for ev in driver.send_turn(
            SendTurnRequest(
                session_id=resp.session_id,
                messages=[{"role": "user", "content": "ts check"}],
            ),
        ):
            assert ev.timestamp is not None
