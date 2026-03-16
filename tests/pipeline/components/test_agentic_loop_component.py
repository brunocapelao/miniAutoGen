"""Tests for AgenticLoopComponent delegation to AgenticLoopRuntime."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from miniautogen.core.contracts.agentic_loop import ConversationPolicy
from miniautogen.pipeline.components.agentic_loop import AgenticLoopComponent


def test_dataclass_with_policy_only() -> None:
    """AgenticLoopComponent still works as a simple dataclass with policy."""
    component = AgenticLoopComponent(policy=ConversationPolicy(max_turns=5))
    assert component.policy.max_turns == 5
    assert component.runtime is None


@pytest.mark.asyncio
async def test_execute_delegates_to_runtime() -> None:
    """execute() forwards call to runtime.run()."""
    sentinel = MagicMock(name="run_result")
    mock_runtime = MagicMock()
    mock_runtime.run = AsyncMock(return_value=sentinel)

    component = AgenticLoopComponent(
        policy=ConversationPolicy(max_turns=10),
        runtime=mock_runtime,
    )

    agents = [MagicMock()]
    context = MagicMock()
    plan = MagicMock()

    result = await component.execute(agents, context, plan)

    mock_runtime.run.assert_awaited_once_with(agents, context, plan)
    assert result is sentinel


@pytest.mark.asyncio
async def test_execute_raises_without_runtime() -> None:
    """execute() raises RuntimeError when no runtime is set."""
    component = AgenticLoopComponent(policy=ConversationPolicy(max_turns=5))

    with pytest.raises(RuntimeError, match="requires a runtime"):
        await component.execute([], MagicMock(), MagicMock())
