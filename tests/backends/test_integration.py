# tests/backends/test_integration.py
"""End-to-end integration test for the backend driver foundation."""

from __future__ import annotations

import pytest

from miniautogen.backends.config import BackendConfig, DriverType
from miniautogen.backends.models import (
    AgentEvent,
    ArtifactRef,
    BackendCapabilities,
    SendTurnRequest,
    StartSessionRequest,
)
from miniautogen.backends.resolver import BackendResolver
from miniautogen.backends.sessions import SessionManager, SessionState

from tests.backends.conftest import FakeDriver


@pytest.mark.asyncio
async def test_full_lifecycle() -> None:
    """Config -> Resolve -> Start session -> Send turn -> Artifacts -> Close."""
    # 1. Configure
    resolver = BackendResolver()
    resolver.register_factory(
        DriverType.ACP,
        lambda cfg: FakeDriver(
            caps=BackendCapabilities(
                sessions=True, streaming=True, artifacts=True,
            ),
            events=[
                AgentEvent(
                    type="message_delta",
                    session_id="",
                    payload={"delta": "Hello "},
                ),
                AgentEvent(
                    type="message_completed",
                    session_id="",
                    payload={"text": "Hello world"},
                ),
            ],
            artifacts=[
                ArtifactRef(artifact_id="a1", kind="file", name="output.py"),
            ],
        ),
    )
    resolver.add_backend(
        BackendConfig(backend_id="test_agent", driver=DriverType.ACP, command=["acpx"]),
    )

    # 2. Resolve
    driver = resolver.get_driver("test_agent")

    # 3. Start session
    session_mgr = SessionManager()
    resp = await driver.start_session(
        StartSessionRequest(backend_id="test_agent"),
    )
    session_mgr.create(
        session_id=resp.session_id,
        backend_id="test_agent",
        capabilities=resp.capabilities,
    )
    session_mgr.transition(resp.session_id, SessionState.ACTIVE)

    # 4. Send turn
    session_mgr.transition(resp.session_id, SessionState.BUSY)
    events: list[AgentEvent] = []
    async for ev in driver.send_turn(
        SendTurnRequest(
            session_id=resp.session_id,
            messages=[{"role": "user", "content": "Write hello world"}],
        ),
    ):
        events.append(ev)
    session_mgr.transition(resp.session_id, SessionState.ACTIVE)

    # Verify events
    assert len(events) == 3  # 2 custom + 1 turn_completed
    assert events[0].type == "message_delta"
    assert events[1].type == "message_completed"
    assert events[2].type == "turn_completed"

    # 5. Collect artifacts
    artifacts = await driver.list_artifacts(resp.session_id)
    assert len(artifacts) == 1
    assert artifacts[0].name == "output.py"

    # 6. Close session
    session_mgr.transition(resp.session_id, SessionState.COMPLETED)
    await driver.close_session(resp.session_id)
    session_mgr.transition(resp.session_id, SessionState.CLOSED)

    assert session_mgr.get(resp.session_id).state == SessionState.CLOSED
