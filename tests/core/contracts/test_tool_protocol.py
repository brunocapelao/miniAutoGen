"""Tests for ToolProtocol and ToolResult."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from miniautogen.core.contracts.tool import ToolProtocol, ToolResult

# --- Fake implementations ---


class _FakeTool:
    """Satisfies ToolProtocol structurally."""

    @property
    def name(self) -> str:
        return "fake_tool"

    @property
    def description(self) -> str:
        return "A fake tool for testing."

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        return ToolResult(success=True, output=params)


class _BrokenTool:
    """Does NOT satisfy ToolProtocol — missing execute()."""

    @property
    def name(self) -> str:
        return "broken"

    @property
    def description(self) -> str:
        return "broken"


# --- ToolResult tests ---


def test_tool_result_success() -> None:
    result = ToolResult(success=True, output="hello")
    assert result.success is True
    assert result.output == "hello"
    assert result.error is None


def test_tool_result_failure() -> None:
    result = ToolResult(success=False, error="something went wrong")
    assert result.success is False
    assert result.output is None
    assert result.error == "something went wrong"


def test_tool_result_serialization_roundtrip() -> None:
    original = ToolResult(success=True, output={"key": "value"})
    data = original.model_dump()
    restored = ToolResult.model_validate(data)
    assert restored == original


def test_tool_result_requires_success_field() -> None:
    with pytest.raises(ValidationError):
        ToolResult()  # type: ignore[call-arg]


def test_tool_result_rejects_success_with_error() -> None:
    with pytest.raises(ValidationError):
        ToolResult(success=True, error="should not be here")


def test_tool_result_rejects_failure_without_error() -> None:
    with pytest.raises(ValidationError):
        ToolResult(success=False)


# --- ToolProtocol isinstance checks ---


def test_tool_protocol_is_runtime_checkable() -> None:
    tool = _FakeTool()
    assert isinstance(tool, ToolProtocol)


def test_broken_tool_does_not_satisfy_protocol() -> None:
    tool = _BrokenTool()
    assert not isinstance(tool, ToolProtocol)


# --- Async execution ---


@pytest.mark.anyio
async def test_fake_tool_execute_returns_tool_result() -> None:
    tool = _FakeTool()
    result = await tool.execute({"query": "test"})
    assert isinstance(result, ToolResult)
    assert result.success is True
    assert result.output == {"query": "test"}
