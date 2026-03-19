"""Tests for BaseDriver wrapper."""

from __future__ import annotations

from typing import AsyncIterator

import pytest

from miniautogen.backends.base_driver import BaseDriver
from miniautogen.backends.errors import CancelNotSupportedError, TurnExecutionError
from miniautogen.backends.models import (
    AgentEvent,
    BackendCapabilities,
    CancelTurnRequest,
    SendTurnRequest,
    StartSessionRequest,
)
from tests.backends.conftest import FakeDriver


@pytest.fixture
def wrapped_driver() -> BaseDriver:
    inner = FakeDriver(
        caps=BackendCapabilities(sessions=True, streaming=True),
        events=[
            AgentEvent(
                type="message_completed",
                session_id="",
                payload={"text": "Hello"},
            ),
        ],
    )
    return BaseDriver(inner=inner, capabilities=BackendCapabilities(sessions=True, streaming=True))


class TestBaseDriverDelegation:
    @pytest.mark.asyncio
    async def test_start_session_delegates(self, wrapped_driver: BaseDriver) -> None:
        resp = await wrapped_driver.start_session(
            StartSessionRequest(backend_id="test"),
        )
        assert resp.session_id.startswith("fake_sess_")

    @pytest.mark.asyncio
    async def test_send_turn_delegates_and_yields_events(
        self, wrapped_driver: BaseDriver,
    ) -> None:
        resp = await wrapped_driver.start_session(
            StartSessionRequest(backend_id="test"),
        )
        events: list[AgentEvent] = []
        async for ev in wrapped_driver.send_turn(
            SendTurnRequest(
                session_id=resp.session_id,
                messages=[{"role": "user", "content": "hi"}],
            ),
        ):
            events.append(ev)
        types = [e.type for e in events]
        assert "message_completed" in types
        assert "turn_completed" in types

    @pytest.mark.asyncio
    async def test_capabilities_returns_wrapper_caps(
        self, wrapped_driver: BaseDriver,
    ) -> None:
        caps = await wrapped_driver.capabilities()
        assert caps.streaming is True
        assert caps.sessions is True

    @pytest.mark.asyncio
    async def test_close_session_delegates(self, wrapped_driver: BaseDriver) -> None:
        resp = await wrapped_driver.start_session(
            StartSessionRequest(backend_id="test"),
        )
        await wrapped_driver.close_session(resp.session_id)

    @pytest.mark.asyncio
    async def test_list_artifacts_delegates(self, wrapped_driver: BaseDriver) -> None:
        result = await wrapped_driver.list_artifacts("s1")
        assert result == []

    @pytest.mark.asyncio
    async def test_cancel_turn_delegates(self, wrapped_driver: BaseDriver) -> None:
        with pytest.raises(CancelNotSupportedError):
            inner_caps = BackendCapabilities(cancel=False)
            inner = FakeDriver(caps=inner_caps)
            driver = BaseDriver(inner=inner, capabilities=inner_caps)
            await driver.cancel_turn(CancelTurnRequest(session_id="s1"))


class TestBaseDriverSanitization:
    @pytest.mark.asyncio
    async def test_empty_messages_filtered(self) -> None:
        inner = FakeDriver(
            events=[
                AgentEvent(type="message_completed", session_id="", payload={"text": "ok"}),
            ],
        )
        driver = BaseDriver(inner=inner, capabilities=BackendCapabilities())
        resp = await driver.start_session(StartSessionRequest(backend_id="test"))
        events: list[AgentEvent] = []
        async for ev in driver.send_turn(
            SendTurnRequest(
                session_id=resp.session_id,
                messages=[
                    {"role": "user", "content": "hello"},
                    {"role": "user", "content": ""},
                    {"role": "user", "content": "   "},
                ],
            ),
        ):
            events.append(ev)
        # Should still work -- empty messages removed before sending
        assert any(e.type == "message_completed" for e in events)


class TestBaseDriverErrorNormalization:
    @pytest.mark.asyncio
    async def test_inner_exception_yields_error_event(self) -> None:
        class FailingDriver(FakeDriver):
            async def send_turn(
                self, request: SendTurnRequest,
            ) -> AsyncIterator[AgentEvent]:
                raise TurnExecutionError("boom")
                yield  # make it an async generator  # noqa: RUF027

        inner = FailingDriver()
        driver = BaseDriver(inner=inner, capabilities=BackendCapabilities())
        resp = await driver.start_session(StartSessionRequest(backend_id="test"))
        events: list[AgentEvent] = []
        async for ev in driver.send_turn(
            SendTurnRequest(
                session_id=resp.session_id,
                messages=[{"role": "user", "content": "hi"}],
            ),
        ):
            events.append(ev)
        assert len(events) == 1
        assert events[0].type == "backend_error"
        assert events[0].payload.get("error") == "TurnExecutionError"
