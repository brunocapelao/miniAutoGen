"""Tests for the ScriptBuilder imperative API."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from miniautogen.core.contracts.enums import RunStatus
from miniautogen.scripting.builder import ScriptBuilder, _AgentDef


class TestAgentDef:
    def test_defaults(self) -> None:
        agent = _AgentDef(name="test")
        assert agent.model == "gpt-4o"
        assert agent.provider == "openai"
        assert agent.temperature == 0.2
        assert agent.tools == []

    def test_custom_values(self) -> None:
        agent = _AgentDef(
            name="custom",
            model="claude-3-5-sonnet",
            provider="anthropic",
            role="analyst",
        )
        assert agent.model == "claude-3-5-sonnet"
        assert agent.provider == "anthropic"
        assert agent.role == "analyst"


class TestScriptBuilder:
    def test_add_agent(self) -> None:
        builder = ScriptBuilder()
        result = builder.add_agent("test", model="gpt-4o", role="tester")
        # Returns self for chaining
        assert result is builder
        assert "test" in builder._agents
        assert builder._agents["test"].model == "gpt-4o"

    def test_add_agent_chaining(self) -> None:
        builder = ScriptBuilder()
        builder.add_agent("a", model="gpt-4o").add_agent("b", model="gpt-4o")
        assert len(builder._agents) == 2

    def test_add_tool(self) -> None:
        builder = ScriptBuilder()
        builder.add_agent("test")
        mock_tool = MagicMock()
        result = builder.add_tool("test", mock_tool)
        assert result is builder
        assert mock_tool in builder._agents["test"].tools

    def test_add_tool_unknown_agent_raises(self) -> None:
        builder = ScriptBuilder()
        with pytest.raises(KeyError, match="Agent 'unknown' not found"):
            builder.add_tool("unknown", MagicMock())

    @pytest.mark.anyio
    async def test_single_run_unknown_agent_raises(self) -> None:
        builder = ScriptBuilder()
        with pytest.raises(KeyError, match="Agent 'unknown' not found"):
            await builder.single_run("unknown", input="test")

    @pytest.mark.anyio
    async def test_workflow_unknown_agent_raises(self) -> None:
        builder = ScriptBuilder()
        builder.add_agent("a")
        with pytest.raises(KeyError, match="Agent 'b' not found"):
            await builder.workflow(["a", "b"], input="test")

    @pytest.mark.anyio
    async def test_deliberation_unknown_leader_raises(self) -> None:
        builder = ScriptBuilder()
        builder.add_agent("a")
        with pytest.raises(KeyError, match="Leader agent 'b' not found"):
            await builder.deliberation(
                topic="test", participants=["a"], leader="b",
            )

    @pytest.mark.anyio
    async def test_loop_unknown_router_raises(self) -> None:
        builder = ScriptBuilder()
        builder.add_agent("a")
        with pytest.raises(KeyError, match="Router agent 'b' not found"):
            await builder.loop(
                router="b", participants=["a"], initial_message="hi",
            )

    @pytest.mark.anyio
    async def test_single_run_with_mock_driver(self) -> None:
        """Test single_run with a mocked driver to verify the full flow."""
        builder = ScriptBuilder()
        builder.add_agent("test", model="gpt-4o", role="tester")

        # Mock the _build_runtimes to return a mock agent
        mock_agent = AsyncMock()
        mock_agent.process = AsyncMock(return_value="test output")
        mock_agent.initialize = AsyncMock()
        mock_agent.close = AsyncMock()

        with patch.object(builder, "_build_runtimes", return_value={"test": mock_agent}):
            result = await builder.single_run("test", input="do something")

        assert result.status == RunStatus.FINISHED
        assert result.output == "test output"
        mock_agent.initialize.assert_called_once()
        mock_agent.process.assert_called_once_with("do something")
        mock_agent.close.assert_called_once()

    @pytest.mark.anyio
    async def test_single_run_failure_returns_failed_result(self) -> None:
        builder = ScriptBuilder()
        builder.add_agent("test")

        mock_agent = AsyncMock()
        mock_agent.initialize = AsyncMock(side_effect=RuntimeError("boom"))
        mock_agent.close = AsyncMock()

        with patch.object(builder, "_build_runtimes", return_value={"test": mock_agent}):
            result = await builder.single_run("test", input="fail")

        assert result.status == RunStatus.FAILED
        assert "boom" in (result.error or "")

    @pytest.mark.anyio
    async def test_workflow_with_mock_runtimes(self) -> None:
        builder = ScriptBuilder()
        builder.add_agent("a").add_agent("b")

        mock_a = AsyncMock()
        mock_a.process = AsyncMock(return_value="from a")
        mock_a.agent_id = "a"
        mock_a.initialize = AsyncMock()
        mock_a.close = AsyncMock()

        mock_b = AsyncMock()
        mock_b.process = AsyncMock(return_value="from b")
        mock_b.agent_id = "b"
        mock_b.initialize = AsyncMock()
        mock_b.close = AsyncMock()

        runtimes = {"a": mock_a, "b": mock_b}

        with patch.object(builder, "_build_runtimes", return_value=runtimes):
            result = await builder.workflow(["a", "b"], input="start")

        assert result.status == RunStatus.FINISHED

    def test_unknown_provider_captured(self) -> None:
        builder = ScriptBuilder()
        builder.add_agent("test", provider="unknown_provider")
        # The error should be raised when building runtimes, not when adding
        assert builder._agents["test"].provider == "unknown_provider"


class TestScriptBuilderSystemPrompt:
    def test_system_prompt_parts(self) -> None:
        builder = ScriptBuilder()
        builder.add_agent(
            "test",
            system_prompt="You are helpful",
            role="analyst",
            goal="analyze data",
        )
        agent = builder._agents["test"]
        assert agent.system_prompt == "You are helpful"
        assert agent.role == "analyst"
        assert agent.goal == "analyze data"
