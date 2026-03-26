"""Tests for chat_service -- interactive multi-turn conversation with an agent."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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
        "flows": {},
    }
    (tmp_path / "miniautogen.yaml").write_text(yaml.dump(config_data))

    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    agent_data = {
        "id": "coder",
        "name": "coder",
        "role": "assistant",
        "goal": "Write clean code",
        "engine_profile": "openai",
    }
    (agents_dir / "coder.yaml").write_text(yaml.dump(agent_data))

    reviewer_data = {
        "id": "reviewer",
        "name": "reviewer",
        "role": "assistant",
        "goal": "Review code thoroughly",
        "engine_profile": "openai",
    }
    (agents_dir / "reviewer.yaml").write_text(yaml.dump(reviewer_data))

    return tmp_path


def _make_mocks() -> tuple[MagicMock, AsyncMock]:
    """Build mock EngineResolver and AgentRuntime."""
    mock_driver = MagicMock()

    mock_resolver_instance = MagicMock()
    mock_resolver_instance.create_fresh_driver.return_value = mock_driver

    mock_runtime_instance = AsyncMock()
    mock_runtime_instance.initialize = AsyncMock()
    mock_runtime_instance.process = AsyncMock(return_value="Hello back!")
    mock_runtime_instance.close = AsyncMock()

    return mock_resolver_instance, mock_runtime_instance


@pytest.mark.anyio
async def test_create_session(workspace: Path) -> None:
    """Creates a session with mocked runtime and correct defaults."""
    mock_resolver, mock_runtime = _make_mocks()

    with (
        patch(
            "miniautogen.backends.engine_resolver.EngineResolver",
            return_value=mock_resolver,
        ),
        patch(
            "miniautogen.core.runtime.agent_runtime.AgentRuntime",
            return_value=mock_runtime,
        ),
    ):
        from miniautogen.cli.services.chat_service import ChatSession

        session = await ChatSession.create(workspace)

    assert session.agent_name == "coder"
    assert session.run_id.startswith("chat-")
    assert session.history == []
    assert session.is_closed is False
    mock_runtime.initialize.assert_awaited_once()


@pytest.mark.anyio
async def test_send_message_tracks_history(workspace: Path) -> None:
    """History grows with each user/assistant message pair."""
    mock_resolver, mock_runtime = _make_mocks()
    mock_runtime.process = AsyncMock(side_effect=["Response 1", "Response 2"])

    with (
        patch(
            "miniautogen.backends.engine_resolver.EngineResolver",
            return_value=mock_resolver,
        ),
        patch(
            "miniautogen.core.runtime.agent_runtime.AgentRuntime",
            return_value=mock_runtime,
        ),
    ):
        from miniautogen.cli.services.chat_service import ChatSession

        session = await ChatSession.create(workspace)
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
async def test_clear_history(workspace: Path) -> None:
    """Clearing history removes all messages."""
    mock_resolver, mock_runtime = _make_mocks()

    with (
        patch(
            "miniautogen.backends.engine_resolver.EngineResolver",
            return_value=mock_resolver,
        ),
        patch(
            "miniautogen.core.runtime.agent_runtime.AgentRuntime",
            return_value=mock_runtime,
        ),
    ):
        from miniautogen.cli.services.chat_service import ChatSession

        session = await ChatSession.create(workspace)
        await session.send("Hello")
        assert len(session.history) == 2

        session.clear_history()
        assert session.history == []


@pytest.mark.anyio
async def test_close_session(workspace: Path) -> None:
    """Closing the session marks it as closed and calls runtime.close()."""
    mock_resolver, mock_runtime = _make_mocks()

    with (
        patch(
            "miniautogen.backends.engine_resolver.EngineResolver",
            return_value=mock_resolver,
        ),
        patch(
            "miniautogen.core.runtime.agent_runtime.AgentRuntime",
            return_value=mock_runtime,
        ),
    ):
        from miniautogen.cli.services.chat_service import ChatSession

        session = await ChatSession.create(workspace)
        assert session.is_closed is False

        await session.close()
        assert session.is_closed is True
        mock_runtime.close.assert_awaited_once()


@pytest.mark.anyio
async def test_send_after_close(workspace: Path) -> None:
    """Sending a message after close raises RuntimeError."""
    mock_resolver, mock_runtime = _make_mocks()

    with (
        patch(
            "miniautogen.backends.engine_resolver.EngineResolver",
            return_value=mock_resolver,
        ),
        patch(
            "miniautogen.core.runtime.agent_runtime.AgentRuntime",
            return_value=mock_runtime,
        ),
    ):
        from miniautogen.cli.services.chat_service import ChatSession

        session = await ChatSession.create(workspace)
        await session.close()

        with pytest.raises(RuntimeError, match="session is closed"):
            await session.send("Hello")


@pytest.mark.anyio
async def test_list_available_agents(workspace: Path) -> None:
    """Returns list of agent names from the workspace."""
    from miniautogen.cli.services.chat_service import list_available_agents

    agents = list_available_agents(workspace)
    assert "coder" in agents
    assert "reviewer" in agents
    assert len(agents) == 2
