"""Tests for PermissionsEnforcerHook -- blocks disallowed tool calls."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from miniautogen.core.contracts.agent_hook import AgentHook
from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.events.types import EventType
from miniautogen.core.runtime.agent_hooks import PermissionsEnforcerHook
from miniautogen.policies.permission import PermissionDeniedError, PermissionPolicy


def _make_context() -> RunContext:
    return RunContext(
        run_id="run-1",
        started_at=datetime.now(timezone.utc),
        correlation_id="corr-1",
    )


def test_permissions_enforcer_satisfies_protocol() -> None:
    policy = PermissionPolicy(allowed_actions=("read_file", "search"))
    hook = PermissionsEnforcerHook(policy=policy)
    assert isinstance(hook, AgentHook)


@pytest.mark.anyio
async def test_permissions_enforcer_allows_permitted_tool_call() -> None:
    policy = PermissionPolicy(allowed_actions=("read_file", "search"))
    hook = PermissionsEnforcerHook(policy=policy)
    event = ExecutionEvent(
        type=EventType.BACKEND_TOOL_CALL_REQUESTED.value,
        run_id="run-1",
        payload={"tool_name": "read_file"},
    )
    ctx = _make_context()

    result = await hook.after_event(event, ctx)
    assert result.type == EventType.BACKEND_TOOL_CALL_REQUESTED.value


@pytest.mark.anyio
async def test_permissions_enforcer_blocks_disallowed_tool_call() -> None:
    policy = PermissionPolicy(allowed_actions=("read_file",))
    hook = PermissionsEnforcerHook(policy=policy)
    event = ExecutionEvent(
        type=EventType.BACKEND_TOOL_CALL_REQUESTED.value,
        run_id="run-1",
        payload={"tool_name": "delete_file"},
    )
    ctx = _make_context()

    with pytest.raises(PermissionDeniedError):
        await hook.after_event(event, ctx)


@pytest.mark.anyio
async def test_permissions_enforcer_allows_all_when_allow_all() -> None:
    policy = PermissionPolicy(allow_all=True)
    hook = PermissionsEnforcerHook(policy=policy)
    event = ExecutionEvent(
        type=EventType.BACKEND_TOOL_CALL_REQUESTED.value,
        run_id="run-1",
        payload={"tool_name": "anything"},
    )
    ctx = _make_context()

    result = await hook.after_event(event, ctx)
    assert result.type == EventType.BACKEND_TOOL_CALL_REQUESTED.value


@pytest.mark.anyio
async def test_permissions_enforcer_passes_non_tool_events() -> None:
    policy = PermissionPolicy(allowed_actions=("read_file",))
    hook = PermissionsEnforcerHook(policy=policy)
    event = ExecutionEvent(type="backend_message_completed", run_id="run-1")
    ctx = _make_context()

    result = await hook.after_event(event, ctx)
    assert result.type == "backend_message_completed"


@pytest.mark.anyio
async def test_permissions_enforcer_before_turn_is_passthrough() -> None:
    policy = PermissionPolicy(allowed_actions=("read_file",))
    hook = PermissionsEnforcerHook(policy=policy)
    messages: list[dict[str, Any]] = [{"role": "user", "content": "hello"}]
    ctx = _make_context()

    result = await hook.before_turn(messages, ctx)
    assert result == messages


@pytest.mark.anyio
async def test_permissions_enforcer_on_error_propagates() -> None:
    policy = PermissionPolicy(allowed_actions=("read_file",))
    hook = PermissionsEnforcerHook(policy=policy)
    ctx = _make_context()

    result = await hook.on_error(RuntimeError("test"), ctx)
    assert result is None
