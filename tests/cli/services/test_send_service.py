"""Tests for send_service -- single agent turn without a full pipeline run."""

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

    return tmp_path


@pytest.fixture
def workspace_no_agents(tmp_path: Path) -> Path:
    """Create a workspace with no agents."""
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
    return tmp_path


@pytest.mark.anyio
async def test_send_message_returns_response(workspace: Path) -> None:
    """Happy path: sends a message and gets a response dict."""
    mock_runtime = AsyncMock()
    mock_runtime.process = AsyncMock(return_value="Hello back!")
    mock_runtime.close = AsyncMock()

    with patch(
        "miniautogen.cli.services.send_service.create_runtime",
        return_value=(mock_runtime, "send-abcdef01"),
    ):
        from miniautogen.cli.services.send_service import send_message

        result = await send_message(workspace, "Hello agent")

    assert result["agent"] == "coder"
    assert result["message"] == "Hello agent"
    assert result["response"] == "Hello back!"
    assert result["run_id"].startswith("send-")
    mock_runtime.process.assert_awaited_once_with("Hello agent")
    mock_runtime.close.assert_awaited_once()


@pytest.mark.anyio
async def test_send_message_default_agent(workspace: Path) -> None:
    """When agent_name is None, uses the first agent in workspace."""
    mock_runtime = AsyncMock()

    with patch(
        "miniautogen.cli.services.send_service.create_runtime",
        return_value=(mock_runtime, "send-abcdef01"),
    ):
        from miniautogen.cli.services.send_service import send_message

        result = await send_message(workspace, "Hi", agent_name=None)

    assert result["agent"] == "coder"


@pytest.mark.anyio
async def test_send_message_agent_not_found(workspace: Path) -> None:
    """Raises ValueError when the requested agent doesn't exist."""
    from miniautogen.cli.services.send_service import send_message

    with pytest.raises(ValueError, match="Agent 'nonexistent' not found"):
        await send_message(workspace, "Hello", agent_name="nonexistent")


@pytest.mark.anyio
async def test_send_message_no_agents(workspace_no_agents: Path) -> None:
    """Raises ValueError when workspace has no agents."""
    from miniautogen.cli.services.send_service import send_message

    with pytest.raises(ValueError, match="No agents found"):
        await send_message(workspace_no_agents, "Hello")


@pytest.mark.anyio
async def test_send_message_closes_runtime_on_error(workspace: Path) -> None:
    """Runtime.close() is called even when process() raises."""
    mock_runtime = AsyncMock()
    mock_runtime.process = AsyncMock(side_effect=RuntimeError("LLM error"))
    mock_runtime.close = AsyncMock()

    with patch(
        "miniautogen.cli.services.send_service.create_runtime",
        return_value=(mock_runtime, "send-abcdef01"),
    ):
        from miniautogen.cli.services.send_service import send_message

        with pytest.raises(RuntimeError, match="LLM error"):
            await send_message(workspace, "Hello")

    mock_runtime.close.assert_awaited_once()
