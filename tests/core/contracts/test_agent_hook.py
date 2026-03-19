"""Tests for AgentHook protocol and structural conformance."""

from __future__ import annotations

from typing import Any

from miniautogen.core.contracts.agent_hook import AgentHook
from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.contracts.run_context import RunContext

# --- Fake implementations ---


class _FakeAgentHook:
    """Satisfies AgentHook structurally."""

    async def before_turn(
        self,
        messages: list[dict[str, Any]],
        context: RunContext,
    ) -> list[dict[str, Any]]:
        return messages

    async def after_event(
        self,
        event: ExecutionEvent,
        context: RunContext,
    ) -> ExecutionEvent:
        return event

    async def on_error(
        self,
        error: Exception,
        context: RunContext,
    ) -> ExecutionEvent | None:
        return None


class _BrokenAgentHook:
    """Missing after_event -- does NOT satisfy AgentHook."""

    async def before_turn(
        self,
        messages: list[dict[str, Any]],
        context: RunContext,
    ) -> list[dict[str, Any]]:
        return messages

    async def on_error(
        self,
        error: Exception,
        context: RunContext,
    ) -> ExecutionEvent | None:
        return None


class _PartialHookMissingOnError:
    """Missing on_error -- does NOT satisfy AgentHook."""

    async def before_turn(
        self,
        messages: list[dict[str, Any]],
        context: RunContext,
    ) -> list[dict[str, Any]]:
        return messages

    async def after_event(
        self,
        event: ExecutionEvent,
        context: RunContext,
    ) -> ExecutionEvent:
        return event


# --- Tests ---


def test_agent_hook_is_runtime_checkable() -> None:
    hook = _FakeAgentHook()
    assert isinstance(hook, AgentHook)


def test_broken_agent_hook_missing_after_event() -> None:
    hook = _BrokenAgentHook()
    assert not isinstance(hook, AgentHook)


def test_partial_hook_missing_on_error() -> None:
    hook = _PartialHookMissingOnError()
    assert not isinstance(hook, AgentHook)
