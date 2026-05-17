"""Tests for LeadAgentSession — unified lead agent session."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import yaml


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Create a minimal workspace with config and agent files."""
    config_data = {
        "project": {"name": "test-project", "version": "0.1.0"},
        "defaults": {"engine": "openai"},
        "engines": {
            "openai": {
                "provider": "openai",
                "model": "gpt-4o-mini",
            }
        },
        "flows": {
            "main": {
                "mode": "workflow",
                "participants": ["coder"],
            },
        },
    }
    (tmp_path / "miniautogen.yaml").write_text(yaml.dump(config_data))

    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "coder.yaml").write_text(
        yaml.dump({
            "id": "coder",
            "name": "coder",
            "role": "assistant",
            "goal": "Write clean code",
            "engine_profile": "openai",
        })
    )

    return tmp_path


@pytest.mark.anyio
async def test_lead_session_create(workspace: Path) -> None:
    """Creates a session with mocked runtime and correct defaults."""
    mock_runtime = AsyncMock()

    with patch(
        "miniautogen.cli.services.lead_agent_session.create_runtime",
        return_value=(mock_runtime, "lead-abcdef01"),
    ):
        from miniautogen.cli.services.lead_agent_session import LeadAgentSession

        session = await LeadAgentSession.create(workspace)

    assert session.agent_name == "coder"
    assert session.run_id.startswith("lead-")
    assert session.history == []
    assert session.is_closed is False
    assert session.recent_events == []


@pytest.mark.anyio
async def test_lead_session_send_tracks_history(workspace: Path) -> None:
    """History grows with each user/assistant message pair."""
    mock_runtime = AsyncMock()
    mock_runtime.process = AsyncMock(side_effect=["Response 1", "Response 2"])

    with patch(
        "miniautogen.cli.services.lead_agent_session.create_runtime",
        return_value=(mock_runtime, "lead-abcdef01"),
    ):
        from miniautogen.cli.services.lead_agent_session import LeadAgentSession

        session = await LeadAgentSession.create(workspace)
        resp1 = await session.send("Hello")
        resp2 = await session.send("How are you?")

    assert resp1 == "Response 1"
    assert resp2 == "Response 2"
    assert len(session.history) == 4
    assert session.history[0] == {"role": "user", "content": "Hello"}
    assert session.history[1] == {"role": "assistant", "content": "Response 1"}
    assert session.history[2] == {"role": "user", "content": "How are you?"}
    assert session.history[3] == {"role": "assistant", "content": "Response 2"}


@pytest.mark.anyio
async def test_lead_session_events_are_captured(workspace: Path) -> None:
    """Events are captured during send() calls."""
    mock_runtime = AsyncMock()
    mock_runtime.process = AsyncMock(return_value="Response")

    with patch(
        "miniautogen.cli.services.lead_agent_session.create_runtime",
        return_value=(mock_runtime, "lead-abcdef01"),
    ):
        from miniautogen.cli.services.lead_agent_session import LeadAgentSession

        session = await LeadAgentSession.create(workspace)
        await session.send("Hello")

    events = session.recent_events
    assert len(events) == 2
    assert events[0].type == "component_started"
    assert events[1].type == "component_finished"


@pytest.mark.anyio
async def test_lead_session_clear_history(workspace: Path) -> None:
    """Clearing history removes all messages."""
    mock_runtime = AsyncMock()

    with patch(
        "miniautogen.cli.services.lead_agent_session.create_runtime",
        return_value=(mock_runtime, "lead-abcdef01"),
    ):
        from miniautogen.cli.services.lead_agent_session import LeadAgentSession

        session = await LeadAgentSession.create(workspace)
        await session.send("Hello")
        assert len(session.history) == 2

        session.clear_history()
        assert session.history == []


@pytest.mark.anyio
async def test_lead_session_close(workspace: Path) -> None:
    """Closing the session marks it closed and calls runtime.close()."""
    mock_runtime = AsyncMock()

    with patch(
        "miniautogen.cli.services.lead_agent_session.create_runtime",
        return_value=(mock_runtime, "lead-abcdef01"),
    ):
        from miniautogen.cli.services.lead_agent_session import LeadAgentSession

        session = await LeadAgentSession.create(workspace)
        assert session.is_closed is False

        await session.close()
        assert session.is_closed is True
        mock_runtime.close.assert_awaited_once()


@pytest.mark.anyio
async def test_lead_session_send_after_close(workspace: Path) -> None:
    """Sending a message after close raises RuntimeError."""
    mock_runtime = AsyncMock()

    with patch(
        "miniautogen.cli.services.lead_agent_session.create_runtime",
        return_value=(mock_runtime, "lead-abcdef01"),
    ):
        from miniautogen.cli.services.lead_agent_session import LeadAgentSession

        session = await LeadAgentSession.create(workspace)
        await session.close()

        with pytest.raises(RuntimeError, match="session is closed"):
            await session.send("Hello")


@pytest.mark.anyio
async def test_lead_session_injects_workspace_tools(workspace: Path) -> None:
    """Workspace tools are injected into the runtime's tool registry."""
    mock_runtime = AsyncMock()
    mock_runtime.tool_registry = None

    with patch(
        "miniautogen.cli.services.lead_agent_session.create_runtime",
        return_value=(mock_runtime, "lead-abcdef01"),
    ):
        from miniautogen.cli.services.lead_agent_session import LeadAgentSession

        session = await LeadAgentSession.create(workspace)

    assert session.agent_name == "coder"
    # After creation, tool_registry should not be None anymore
    assert mock_runtime.tool_registry is not None

    tools = mock_runtime.tool_registry.list_tools()
    tool_names = [t.name for t in tools]

    assert "list_agents" in tool_names
    assert "list_flows" in tool_names
    assert "list_engines" in tool_names
    assert "run_flow" in tool_names
    assert "get_events" in tool_names
    assert "check_project" in tool_names
