"""Tests for the ScriptBuilder imperative API."""

from __future__ import annotations

import os
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

        with patch.object(
            builder, "_build_runtimes",
            return_value=({"test": mock_agent}, []),
        ):
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

        with patch.object(
            builder, "_build_runtimes",
            return_value=({"test": mock_agent}, []),
        ):
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

        with patch.object(
            builder, "_build_runtimes",
            return_value=(runtimes, []),
        ):
            result = await builder.workflow(["a", "b"], input="start")

        assert result.status == RunStatus.FINISHED

    def test_unknown_provider_captured(self) -> None:
        builder = ScriptBuilder()
        builder.add_agent("test", provider="unknown_provider")
        # The error should be raised when building runtimes, not when adding
        assert builder._agents["test"].provider == "unknown_provider"

    @pytest.mark.anyio
    async def test_env_keys_cleaned_up_on_success(self) -> None:
        """Environment variables created for API keys are cleaned up."""
        builder = ScriptBuilder()
        builder.add_agent("test")

        mock_agent = AsyncMock()
        mock_agent.process = AsyncMock(return_value="ok")
        mock_agent.initialize = AsyncMock()
        mock_agent.close = AsyncMock()

        env_key = "_MINIAUTOGEN_SCRIPT_TEST_KEY"
        os.environ[env_key] = "secret"

        with patch.object(
            builder, "_build_runtimes",
            return_value=({"test": mock_agent}, [env_key]),
        ):
            result = await builder.single_run("test", input="go")

        assert result.status == RunStatus.FINISHED
        assert env_key not in os.environ

    @pytest.mark.anyio
    async def test_env_keys_cleaned_up_on_failure(self) -> None:
        """Environment variables are cleaned up even on failure."""
        builder = ScriptBuilder()
        builder.add_agent("test")

        mock_agent = AsyncMock()
        mock_agent.initialize = AsyncMock(side_effect=RuntimeError("fail"))
        mock_agent.close = AsyncMock()

        env_key = "_MINIAUTOGEN_SCRIPT_FAIL_KEY"
        os.environ[env_key] = "secret"

        with patch.object(
            builder, "_build_runtimes",
            return_value=({"test": mock_agent}, [env_key]),
        ):
            result = await builder.single_run("test", input="go")

        assert result.status == RunStatus.FAILED
        assert env_key not in os.environ


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


class TestScriptBuilderDeliberation:
    @pytest.mark.anyio
    async def test_deliberation_with_mock_runtimes(self) -> None:
        builder = ScriptBuilder()
        builder.add_agent("a").add_agent("b")

        mock_a = AsyncMock()
        mock_a.agent_id = "a"
        mock_a.initialize = AsyncMock()
        mock_a.close = AsyncMock()

        mock_b = AsyncMock()
        mock_b.agent_id = "b"
        mock_b.initialize = AsyncMock()
        mock_b.close = AsyncMock()

        runtimes = {"a": mock_a, "b": mock_b}

        from miniautogen.core.contracts.run_result import RunResult
        from miniautogen.core.contracts.enums import RunStatus

        with patch.object(
            builder, "_build_runtimes",
            return_value=(runtimes, []),
        ), patch(
            "miniautogen.core.runtime.deliberation_runtime.DeliberationRuntime",
        ) as mock_delib_cls:
            mock_delib = AsyncMock()
            mock_delib.run = AsyncMock(return_value=RunResult(
                run_id="test", status=RunStatus.FINISHED, output="result",
            ))
            mock_delib_cls.return_value = mock_delib
            result = await builder.deliberation(
                topic="test", participants=["a", "b"], leader="a",
            )

        assert result.status == RunStatus.FINISHED


class TestScriptBuilderLoop:
    @pytest.mark.anyio
    async def test_loop_with_mock_runtimes(self) -> None:
        builder = ScriptBuilder()
        builder.add_agent("router").add_agent("worker")

        mock_router = AsyncMock()
        mock_router.agent_id = "router"
        mock_router.initialize = AsyncMock()
        mock_router.close = AsyncMock()

        mock_worker = AsyncMock()
        mock_worker.agent_id = "worker"
        mock_worker.initialize = AsyncMock()
        mock_worker.close = AsyncMock()

        runtimes = {"router": mock_router, "worker": mock_worker}

        from miniautogen.core.contracts.run_result import RunResult
        from miniautogen.core.contracts.enums import RunStatus

        with patch.object(
            builder, "_build_runtimes",
            return_value=(runtimes, []),
        ), patch(
            "miniautogen.scripting.builder.AgenticLoopRuntime",
            create=True,
        ) as mock_loop_cls:
            mock_loop = AsyncMock()
            mock_loop.run = AsyncMock(return_value=RunResult(
                run_id="test", status=RunStatus.FINISHED, output="done",
            ))
            mock_loop_cls.return_value = mock_loop
            result = await builder.loop(
                router="router",
                participants=["router", "worker"],
                initial_message="hi",
            )

        assert result.status == RunStatus.FINISHED


class TestScriptBuilderBuildRuntimes:
    @pytest.mark.anyio
    async def test_unknown_provider_raises(self) -> None:
        builder = ScriptBuilder()
        builder.add_agent("test", provider="nonexistent")
        with pytest.raises(ValueError, match="Unknown provider 'nonexistent'"):
            await builder._build_runtimes("run-1")

    @pytest.mark.anyio
    async def test_api_key_creates_env_var(self) -> None:
        builder = ScriptBuilder()
        builder.add_agent("test", api_key="sk-test-123")
        try:
            # This will fail because we don't have real backends,
            # but we can verify env var creation pattern
            await builder._build_runtimes("run-1")
        except Exception:
            pass
        # Check that a _MINIAUTOGEN_SCRIPT_ env var was created
        found_keys = [
            k for k in os.environ
            if k.startswith("_MINIAUTOGEN_SCRIPT_") and k.endswith("_KEY")
        ]
        # Clean up
        for k in found_keys:
            if os.environ.get(k) == "sk-test-123":
                del os.environ[k]
        assert len(found_keys) >= 1
