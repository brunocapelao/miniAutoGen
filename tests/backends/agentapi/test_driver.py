"""Tests for AgentAPIDriver with mocked client."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from miniautogen.backends.agentapi.client import AgentAPIClient
from miniautogen.backends.agentapi.driver import AgentAPIDriver
from miniautogen.backends.errors import (
    BackendUnavailableError,
    CancelNotSupportedError,
    TurnExecutionError,
)
from miniautogen.backends.models import (
    AgentEvent,
    BackendCapabilities,
    SendTurnRequest,
    StartSessionRequest,
)


@pytest.fixture
def mock_client() -> AsyncMock:
    client = AsyncMock(spec=AgentAPIClient)
    client.health_check = AsyncMock(return_value=True)
    client.chat_completion = AsyncMock(return_value={
        "choices": [{"message": {"role": "assistant", "content": "Hello"}}],
        "model": "test-model",
    })
    client.close = AsyncMock()
    return client


@pytest.fixture
def driver(mock_client: AsyncMock) -> AgentAPIDriver:
    return AgentAPIDriver(client=mock_client)


class TestAgentAPIDriverStartSession:
    @pytest.mark.asyncio
    async def test_returns_session_id(self, driver: AgentAPIDriver) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="test"),
        )
        assert resp.session_id.startswith("sess_")

    @pytest.mark.asyncio
    async def test_capabilities_no_streaming(
        self, driver: AgentAPIDriver,
    ) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="test"),
        )
        assert resp.capabilities.streaming is False
        assert resp.capabilities.sessions is True
        assert resp.capabilities.cancel is False

    @pytest.mark.asyncio
    async def test_health_check_called(
        self, driver: AgentAPIDriver, mock_client: AsyncMock,
    ) -> None:
        await driver.start_session(StartSessionRequest(backend_id="test"))
        mock_client.health_check.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_health_check_failure_raises(
        self, mock_client: AsyncMock,
    ) -> None:
        mock_client.health_check = AsyncMock(
            side_effect=BackendUnavailableError("down"),
        )
        driver = AgentAPIDriver(client=mock_client)
        with pytest.raises(BackendUnavailableError):
            await driver.start_session(
                StartSessionRequest(backend_id="test"),
            )


class TestAgentAPIDriverSendTurn:
    @pytest.mark.asyncio
    async def test_yields_event_sequence(
        self, driver: AgentAPIDriver,
    ) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="test"),
        )
        events: list[AgentEvent] = []
        async for ev in driver.send_turn(
            SendTurnRequest(
                session_id=resp.session_id,
                messages=[{"role": "user", "content": "hi"}],
            ),
        ):
            events.append(ev)

        assert len(events) == 3
        assert events[0].type == "turn_started"
        assert events[1].type == "message_completed"
        assert events[1].payload["text"] == "Hello"
        assert events[2].type == "turn_completed"

    @pytest.mark.asyncio
    async def test_events_have_session_and_turn_ids(
        self, driver: AgentAPIDriver,
    ) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="test"),
        )
        async for ev in driver.send_turn(
            SendTurnRequest(
                session_id=resp.session_id,
                messages=[{"role": "user", "content": "hi"}],
            ),
        ):
            assert ev.session_id == resp.session_id
            assert ev.turn_id is not None

    @pytest.mark.asyncio
    async def test_client_error_propagates(
        self, mock_client: AsyncMock,
    ) -> None:
        mock_client.chat_completion = AsyncMock(
            side_effect=TurnExecutionError("HTTP 500"),
        )
        driver = AgentAPIDriver(client=mock_client)
        resp = await driver.start_session(
            StartSessionRequest(backend_id="test"),
        )
        with pytest.raises(TurnExecutionError):
            async for _ in driver.send_turn(
                SendTurnRequest(
                    session_id=resp.session_id,
                    messages=[{"role": "user", "content": "hi"}],
                ),
            ):
                pass

    @pytest.mark.asyncio
    async def test_model_passed_to_client(
        self, driver: AgentAPIDriver, mock_client: AsyncMock,
    ) -> None:
        driver = AgentAPIDriver(client=mock_client, model="gemini-2.5-pro")
        resp = await driver.start_session(
            StartSessionRequest(backend_id="test"),
        )
        async for _ in driver.send_turn(
            SendTurnRequest(
                session_id=resp.session_id,
                messages=[{"role": "user", "content": "hi"}],
            ),
        ):
            pass
        _, kwargs = mock_client.chat_completion.call_args
        assert kwargs.get("model") == "gemini-2.5-pro"


class TestAgentAPIDriverOtherMethods:
    @pytest.mark.asyncio
    async def test_cancel_raises(self, driver: AgentAPIDriver) -> None:
        from miniautogen.backends.models import CancelTurnRequest

        with pytest.raises(CancelNotSupportedError):
            await driver.cancel_turn(CancelTurnRequest(session_id="s1"))

    @pytest.mark.asyncio
    async def test_list_artifacts_empty(self, driver: AgentAPIDriver) -> None:
        result = await driver.list_artifacts("s1")
        assert result == []

    @pytest.mark.asyncio
    async def test_close_session_noop(self, driver: AgentAPIDriver) -> None:
        await driver.close_session("s1")

    @pytest.mark.asyncio
    async def test_capabilities(self, driver: AgentAPIDriver) -> None:
        caps = await driver.capabilities()
        assert isinstance(caps, BackendCapabilities)
        assert caps.streaming is False
