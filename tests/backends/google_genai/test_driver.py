"""Tests for GoogleGenAIDriver with mocked client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from miniautogen.backends.errors import CancelNotSupportedError
from miniautogen.backends.google_genai.driver import GoogleGenAIDriver
from miniautogen.backends.models import (
    AgentEvent,
    BackendCapabilities,
    CancelTurnRequest,
    SendTurnRequest,
    StartSessionRequest,
)


def _mock_google_response(content: str = "Hello from Gemini!") -> MagicMock:
    """Create a mock that looks like a google-genai GenerateContentResponse."""
    response = MagicMock()
    response.text = content
    response.candidates = [MagicMock()]
    response.candidates[0].content.parts = [MagicMock(text=content)]

    usage = MagicMock()
    usage.prompt_token_count = 10
    usage.candidates_token_count = 5
    usage.total_token_count = 15
    response.usage_metadata = usage

    return response


@pytest.fixture
def mock_google_client() -> AsyncMock:
    client = AsyncMock()
    client.aio.models.generate_content = AsyncMock(
        return_value=_mock_google_response(),
    )
    return client


@pytest.fixture
def driver(mock_google_client: AsyncMock) -> GoogleGenAIDriver:
    return GoogleGenAIDriver(
        client=mock_google_client,
        model="gemini-2.5-pro",
    )


class TestGoogleGenAIDriverSendTurn:
    @pytest.mark.asyncio
    async def test_yields_event_sequence(self, driver: GoogleGenAIDriver) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="google"),
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
        assert events[1].payload["text"] == "Hello from Gemini!"
        assert events[2].type == "turn_completed"

    @pytest.mark.asyncio
    async def test_capabilities(self, driver: GoogleGenAIDriver) -> None:
        caps = await driver.capabilities()
        assert caps.streaming is True
        assert caps.tools is True
        assert caps.multimodal is True

    @pytest.mark.asyncio
    async def test_cancel_raises(self, driver: GoogleGenAIDriver) -> None:
        with pytest.raises(CancelNotSupportedError):
            await driver.cancel_turn(CancelTurnRequest(session_id="s1"))
