"""Tests for OpenAISDKDriver with mocked openai client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from miniautogen.backends.errors import CancelNotSupportedError
from miniautogen.backends.models import (
    AgentEvent,
    BackendCapabilities,
    CancelTurnRequest,
    SendTurnRequest,
    StartSessionRequest,
)
from miniautogen.backends.openai_sdk.driver import OpenAISDKDriver


def _mock_completion_response(content: str = "Hello!", model: str = "gpt-4o") -> MagicMock:
    """Create a mock that looks like openai ChatCompletion response."""
    choice = MagicMock()
    choice.message.content = content
    choice.message.role = "assistant"

    usage = MagicMock()
    usage.prompt_tokens = 10
    usage.completion_tokens = 5
    usage.total_tokens = 15

    response = MagicMock()
    response.choices = [choice]
    response.model = model
    response.usage = usage
    return response


@pytest.fixture
def mock_openai_client() -> AsyncMock:
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(
        return_value=_mock_completion_response(),
    )
    return client


@pytest.fixture
def driver(mock_openai_client: AsyncMock) -> OpenAISDKDriver:
    return OpenAISDKDriver(
        client=mock_openai_client,
        model="gpt-4o",
    )


class TestOpenAISDKDriverStartSession:
    @pytest.mark.asyncio
    async def test_returns_session_id(self, driver: OpenAISDKDriver) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="openai"),
        )
        assert resp.session_id.startswith("sess_")

    @pytest.mark.asyncio
    async def test_capabilities(self, driver: OpenAISDKDriver) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="openai"),
        )
        assert resp.capabilities.streaming is True
        assert resp.capabilities.tools is True
        assert resp.capabilities.sessions is False


class TestOpenAISDKDriverSendTurn:
    @pytest.mark.asyncio
    async def test_yields_event_sequence(self, driver: OpenAISDKDriver) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="openai"),
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
        assert events[1].payload["text"] == "Hello!"
        assert events[2].type == "turn_completed"

    @pytest.mark.asyncio
    async def test_passes_model_to_sdk(
        self, driver: OpenAISDKDriver, mock_openai_client: AsyncMock,
    ) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="openai"),
        )
        async for _ in driver.send_turn(
            SendTurnRequest(
                session_id=resp.session_id,
                messages=[{"role": "user", "content": "hi"}],
            ),
        ):
            pass
        call_kwargs = mock_openai_client.chat.completions.create.call_args
        assert call_kwargs.kwargs.get("model") == "gpt-4o"

    @pytest.mark.asyncio
    async def test_passes_temperature(
        self, mock_openai_client: AsyncMock,
    ) -> None:
        driver = OpenAISDKDriver(
            client=mock_openai_client,
            model="gpt-4o",
            temperature=0.5,
        )
        resp = await driver.start_session(
            StartSessionRequest(backend_id="openai"),
        )
        async for _ in driver.send_turn(
            SendTurnRequest(
                session_id=resp.session_id,
                messages=[{"role": "user", "content": "hi"}],
            ),
        ):
            pass
        call_kwargs = mock_openai_client.chat.completions.create.call_args
        assert call_kwargs.kwargs.get("temperature") == 0.5


class TestOpenAISDKDriverOtherMethods:
    @pytest.mark.asyncio
    async def test_cancel_raises(self, driver: OpenAISDKDriver) -> None:
        with pytest.raises(CancelNotSupportedError):
            await driver.cancel_turn(CancelTurnRequest(session_id="s1"))

    @pytest.mark.asyncio
    async def test_list_artifacts_empty(self, driver: OpenAISDKDriver) -> None:
        result = await driver.list_artifacts("s1")
        assert result == []

    @pytest.mark.asyncio
    async def test_capabilities(self, driver: OpenAISDKDriver) -> None:
        caps = await driver.capabilities()
        assert isinstance(caps, BackendCapabilities)
        assert caps.streaming is True
        assert caps.tools is True
