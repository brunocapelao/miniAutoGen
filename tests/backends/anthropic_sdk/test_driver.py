"""Tests for AnthropicSDKDriver with mocked anthropic client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from miniautogen.backends.anthropic_sdk.driver import AnthropicSDKDriver
from miniautogen.backends.errors import CancelNotSupportedError
from miniautogen.backends.models import (
    AgentEvent,
    BackendCapabilities,
    CancelTurnRequest,
    SendTurnRequest,
    StartSessionRequest,
)


def _mock_anthropic_response(
    content: str = "Hello!",
    model: str = "claude-sonnet-4-20250514",
) -> MagicMock:
    """Create a mock that looks like an Anthropic Messages response."""
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = content

    usage = MagicMock()
    usage.input_tokens = 10
    usage.output_tokens = 5

    response = MagicMock()
    response.content = [text_block]
    response.model = model
    response.role = "assistant"
    response.usage = usage
    response.stop_reason = "end_turn"
    return response


@pytest.fixture
def mock_anthropic_client() -> AsyncMock:
    client = AsyncMock()
    client.messages.create = AsyncMock(
        return_value=_mock_anthropic_response(),
    )
    return client


@pytest.fixture
def driver(mock_anthropic_client: AsyncMock) -> AnthropicSDKDriver:
    return AnthropicSDKDriver(
        client=mock_anthropic_client,
        model="claude-sonnet-4-20250514",
    )


class TestAnthropicSDKDriverSendTurn:
    @pytest.mark.asyncio
    async def test_yields_event_sequence(self, driver: AnthropicSDKDriver) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="anthropic"),
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
    async def test_transforms_messages_for_anthropic(
        self, driver: AnthropicSDKDriver, mock_anthropic_client: AsyncMock,
    ) -> None:
        """Anthropic requires system message to be separate."""
        resp = await driver.start_session(
            StartSessionRequest(backend_id="anthropic"),
        )
        async for _ in driver.send_turn(
            SendTurnRequest(
                session_id=resp.session_id,
                messages=[
                    {"role": "system", "content": "You are helpful."},
                    {"role": "user", "content": "hi"},
                ],
            ),
        ):
            pass
        call_kwargs = mock_anthropic_client.messages.create.call_args.kwargs
        # System message should be extracted to `system` parameter
        assert call_kwargs.get("system") == "You are helpful."
        # Messages should only contain non-system messages
        assert all(m["role"] != "system" for m in call_kwargs["messages"])

    @pytest.mark.asyncio
    async def test_capabilities(self, driver: AnthropicSDKDriver) -> None:
        caps = await driver.capabilities()
        assert caps.streaming is True
        assert caps.tools is True
        assert caps.sessions is False

    @pytest.mark.asyncio
    async def test_cancel_raises(self, driver: AnthropicSDKDriver) -> None:
        with pytest.raises(CancelNotSupportedError):
            await driver.cancel_turn(CancelTurnRequest(session_id="s1"))
