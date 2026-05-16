"""E2E test: full team run with mailbox + task list + plan approval."""

from __future__ import annotations

from typing import Any

import anyio
import pytest

from miniautogen.core.contracts.coordination import TeamPlan
from datetime import datetime, timezone

from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.run_result import RunResult
from miniautogen.core.events.event_sink import InMemoryEventSink, EventSink
from miniautogen.core.events.types import EventType


class FakeAgent:
    """Minimal agent stub that yields canned responses based on prompt content."""

    def __init__(self, agent_id: str, tool_registry: Any = None) -> None:
        self.agent_id = agent_id
        self.tool_registry = tool_registry
        self._run_context: RunContext | None = None
        self.call_count = 0

    async def process(self, input_data: Any) -> str:
        self.call_count += 1
        if isinstance(input_data, dict):
            prompt = input_data.get("_prompt", "")
            if "shell_command" in prompt or "Execute this task" in prompt:
                return f"{self.agent_id} completed task with shell"
            return f"{self.agent_id} processed: {prompt[:50]}"
        return f"{self.agent_id} processed input"


class FakePipelineRunner:
    """Stub PipelineRunner for testing TeamRuntime."""

    def __init__(self, event_sink: EventSink) -> None:
        self.event_sink = event_sink


@pytest.mark.anyio
async def test_team_runs_with_mailbox_and_plan_approval() -> None:
    from miniautogen.core.runtime.team_runtime import TeamRuntime

    sink = InMemoryEventSink()
    runner = FakePipelineRunner(event_sink=sink)

    runtime = TeamRuntime(
        runner=runner,
        agent_registry={
            "lead": FakeAgent("lead"),
            "worker_a": FakeAgent("worker_a"),
            "worker_b": FakeAgent("worker_b"),
        },
    )

    plan = TeamPlan(
        lead_agent="lead",
        teammates=["worker_a", "worker_b"],
        mailbox={
            "enabled": True,
            "buffer_size": 256,
            "idle_threshold_seconds": 0.3,
        },
        task_list={
            "enabled": True,
            "initial_tasks": [
                {"title": "Task 1", "labels": ["urgent"]},
                {"title": "Task 2", "labels": ["normal"]},
            ],
            "idle_threshold_seconds": 0.3,
        },
    )

    now = datetime.now(timezone.utc)
    context = RunContext(
        run_id="e2e-test-run",
        started_at=now,
        correlation_id="e2e-test-run",
    )

    result = await runtime.run(
        agents=[],
        context=context,
        plan=plan,
    )

    assert result.status.value in ("finished", "failed")
    if result.status.value == "failed":
        assert False, f"Team run failed: {result.error}"

    event_types = {e.type for e in sink.events}
    assert EventType.TEAM_STARTED.value in event_types
    assert EventType.TEAM_FINISHED.value in event_types


@pytest.mark.anyio
async def test_team_without_mailbox_still_works() -> None:
    from miniautogen.core.runtime.team_runtime import TeamRuntime

    sink = InMemoryEventSink()
    runner = FakePipelineRunner(event_sink=sink)

    runtime = TeamRuntime(
        runner=runner,
        agent_registry={
            "lead": FakeAgent("lead"),
            "worker": FakeAgent("worker"),
        },
    )

    plan = TeamPlan(
        lead_agent="lead",
        teammates=["worker"],
    )

    now = datetime.now(timezone.utc)
    context = RunContext(
        run_id="no-mailbox-test",
        started_at=now,
        correlation_id="no-mailbox-test",
    )

    result = await runtime.run(
        agents=[],
        context=context,
        plan=plan,
    )

    assert result.status.value == "finished"


@pytest.mark.anyio
async def test_team_with_mailbox_emits_canonical_events() -> None:
    from miniautogen.core.runtime.team_runtime import TeamRuntime

    sink = InMemoryEventSink()
    runner = FakePipelineRunner(event_sink=sink)

    runtime = TeamRuntime(
        runner=runner,
        agent_registry={
            "lead": FakeAgent("lead"),
            "worker": FakeAgent("worker"),
        },
    )

    plan = TeamPlan(
        lead_agent="lead",
        teammates=["worker"],
        mailbox={
            "enabled": True,
            "buffer_size": 256,
            "idle_threshold_seconds": 0.5,
        },
    )

    now = datetime.now(timezone.utc)
    context = RunContext(
        run_id="event-log-test",
        started_at=now,
        correlation_id="event-log-test",
    )

    result = await runtime.run(
        agents=[],
        context=context,
        plan=plan,
    )

    assert result.status.value == "finished"

    event_types = {e.type for e in sink.events}
    assert EventType.TEAM_STARTED.value in event_types
    assert EventType.TEAM_FINISHED.value in event_types
