"""Tests for CLIAgentDriver with mocked subprocess."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from miniautogen.backends.cli.driver import CLIAgentDriver
from miniautogen.backends.errors import CancelNotSupportedError
from miniautogen.backends.models import (
    AgentEvent,
    BackendCapabilities,
    CancelTurnRequest,
    SendTurnRequest,
    StartSessionRequest,
)


@pytest.fixture
def driver() -> CLIAgentDriver:
    return CLIAgentDriver(
        command=["echo", "test"],
        provider="claude-code",
    )


class TestCLIAgentDriverStartSession:
    @pytest.mark.asyncio
    async def test_returns_session_id(self, driver: CLIAgentDriver) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="cli"),
        )
        assert resp.session_id.startswith("sess_")

    @pytest.mark.asyncio
    async def test_capabilities(self, driver: CLIAgentDriver) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="cli"),
        )
        assert resp.capabilities.streaming is True
        assert resp.capabilities.tools is True
        assert resp.capabilities.sessions is True


class TestCLIAgentDriverOtherMethods:
    @pytest.mark.asyncio
    async def test_cancel_raises(self, driver: CLIAgentDriver) -> None:
        with pytest.raises(CancelNotSupportedError):
            await driver.cancel_turn(CancelTurnRequest(session_id="s1"))

    @pytest.mark.asyncio
    async def test_list_artifacts_empty(self, driver: CLIAgentDriver) -> None:
        result = await driver.list_artifacts("s1")
        assert result == []

    @pytest.mark.asyncio
    async def test_capabilities(self, driver: CLIAgentDriver) -> None:
        caps = await driver.capabilities()
        assert isinstance(caps, BackendCapabilities)
        assert caps.streaming is True
        assert caps.tools is True
        assert caps.sessions is True
        assert caps.artifacts is True

    @pytest.mark.asyncio
    async def test_close_session_succeeds(self, driver: CLIAgentDriver) -> None:
        # Should not raise
        await driver.close_session("s1")
