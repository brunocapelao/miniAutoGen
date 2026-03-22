"""Tests for the quick_run convenience function."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from miniautogen.core.contracts.enums import RunStatus
from miniautogen.scripting.quick import quick_run


class TestQuickRun:
    @pytest.mark.anyio
    async def test_quick_run_delegates_to_builder(self) -> None:
        """Verify quick_run creates a builder and delegates properly."""
        mock_result = AsyncMock()
        mock_result.status = RunStatus.FINISHED
        mock_result.output = "result"

        with patch(
            "miniautogen.scripting.builder.ScriptBuilder"
        ) as MockBuilder:
            instance = MockBuilder.return_value
            instance.add_agent.return_value = instance
            instance.single_run = AsyncMock(return_value=mock_result)

            result = await quick_run(agent="gpt-4o", task="do something")

        assert result.status == RunStatus.FINISHED
        instance.add_agent.assert_called_once()
        instance.single_run.assert_called_once_with("default", input="do something")

    @pytest.mark.anyio
    async def test_quick_run_with_tools(self) -> None:
        mock_tool = object()
        mock_result = AsyncMock()
        mock_result.status = RunStatus.FINISHED

        with patch(
            "miniautogen.scripting.builder.ScriptBuilder"
        ) as MockBuilder:
            instance = MockBuilder.return_value
            instance.add_agent.return_value = instance
            instance.add_tool.return_value = instance
            instance.single_run = AsyncMock(return_value=mock_result)

            await quick_run(agent="gpt-4o", task="test", tools=[mock_tool])

        instance.add_tool.assert_called_once_with("default", mock_tool)

    @pytest.mark.anyio
    async def test_quick_run_passes_provider_params(self) -> None:
        mock_result = AsyncMock()
        mock_result.status = RunStatus.FINISHED

        with patch(
            "miniautogen.scripting.builder.ScriptBuilder"
        ) as MockBuilder:
            instance = MockBuilder.return_value
            instance.add_agent.return_value = instance
            instance.single_run = AsyncMock(return_value=mock_result)

            await quick_run(
                agent="claude-3-5-sonnet",
                task="test",
                provider="anthropic",
                api_key="sk-test",
                temperature=0.5,
            )

        call_kwargs = instance.add_agent.call_args[1]
        assert call_kwargs["model"] == "claude-3-5-sonnet"
        assert call_kwargs["provider"] == "anthropic"
        assert call_kwargs["api_key"] == "sk-test"
        assert call_kwargs["temperature"] == 0.5
