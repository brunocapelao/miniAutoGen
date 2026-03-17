# tests/backends/agentapi/test_driver_contract.py
"""Contract test suite for AgentAPIDriver.

Runs the same contract tests that FakeDriver passes, proving
AgentAPIDriver satisfies the AgentDriver contract.
"""

from __future__ import annotations

import httpx
import pytest

from miniautogen.backends.agentapi.client import AgentAPIClient
from miniautogen.backends.agentapi.driver import AgentAPIDriver
from miniautogen.backends.driver import AgentDriver
from miniautogen.backends.errors import CancelNotSupportedError
from miniautogen.backends.models import (
    AgentEvent,
    BackendCapabilities,
    CancelTurnRequest,
    SendTurnRequest,
    StartSessionRequest,
)


def _mock_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/health":
        return httpx.Response(200, json={"status": "ok"})
    return httpx.Response(200, json={
        "choices": [{"message": {"role": "assistant", "content": "contract test"}}],
        "model": "test",
    })


@pytest.fixture
def driver() -> AgentDriver:
    client = AgentAPIClient(
        base_url="http://fake",
        transport=httpx.MockTransport(_mock_handler),
        max_retry_attempts=1,
    )
    return AgentAPIDriver(client=client)


class TestAgentAPIDriverContract:
    """Same contract tests from test_driver_contract.py."""

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
    async def test_cancel_raises_not_supported(
        self, driver: AgentDriver,
    ) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="test"),
        )
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
                messages=[{"role": "user", "content": "ts"}],
            ),
        ):
            assert ev.timestamp is not None
