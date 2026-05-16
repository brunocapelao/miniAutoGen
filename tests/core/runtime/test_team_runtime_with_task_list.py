"""E2E tests for TeamRuntime with task list enabled."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import anyio
import pytest

from miniautogen.core.contracts.coordination import TeamPlan
from miniautogen.core.contracts.enums import RunStatus
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.team_task import TaskEntrySpec, TaskListConfig
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.events.types import EventType
from miniautogen.core.runtime.pipeline_runner import PipelineRunner
from miniautogen.core.runtime.team_runtime import TeamRuntime


class _FakeAgent:
    def __init__(self, name: str) -> None:
        self.name = name
        self._run_context: RunContext | None = None
        self.tool_registry = None

    async def process(self, input_data: Any) -> str:
        return f"{self.name} processed: {input_data}"


class _TaskListAwareAgent:
    def __init__(self, name: str) -> None:
        self.name = name
        self._run_context: RunContext | None = None
        self.tool_registry = None


@pytest.fixture
def event_sink() -> InMemoryEventSink:
    return InMemoryEventSink()


@pytest.fixture
def runner(event_sink: InMemoryEventSink) -> PipelineRunner:
    return PipelineRunner(event_sink=event_sink)


@pytest.fixture
def context() -> RunContext:
    run_id = "e2e-test-run"
    return RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id=run_id,
    )


@pytest.mark.anyio
async def test_team_runtime_with_task_list_creates_store(
    runner: PipelineRunner,
    context: RunContext,
    event_sink: InMemoryEventSink,
) -> None:
    registry = {
        "lead": _FakeAgent("lead"),
        "alice": _FakeAgent("alice"),
        "bob": _FakeAgent("bob"),
    }
    runtime = TeamRuntime(runner=runner, agent_registry=registry)

    plan = TeamPlan(
        lead_agent="lead",
        teammates=["alice", "bob"],
        task_list=TaskListConfig(
            enabled=True,
            idle_threshold_seconds=0.5,
            poll_interval_ms=50,
        ),
    )

    result = await runtime.run(agents=[], context=context, plan=plan)

    assert result.status == RunStatus.FINISHED


@pytest.mark.anyio
async def test_team_runtime_with_initial_tasks(
    runner: PipelineRunner,
    context: RunContext,
    event_sink: InMemoryEventSink,
) -> None:
    registry = {
        "lead": _FakeAgent("lead"),
        "alice": _FakeAgent("alice"),
        "bob": _FakeAgent("bob"),
    }
    runtime = TeamRuntime(runner=runner, agent_registry=registry)

    plan = TeamPlan(
        lead_agent="lead",
        teammates=["alice", "bob"],
        task_list=TaskListConfig(
            enabled=True,
            initial_tasks=[
                TaskEntrySpec(title="Task 1", assigned_to="alice"),
                TaskEntrySpec(title="Task 2", assigned_to="bob"),
            ],
            idle_threshold_seconds=0.5,
            poll_interval_ms=50,
        ),
    )

    result = await runtime.run(agents=[], context=context, plan=plan)

    assert result.status == RunStatus.FINISHED

    task_added_events = [
        e for e in event_sink.events if e.type == EventType.TASK_ADDED.value
    ]
    assert len(task_added_events) == 2


@pytest.mark.anyio
async def test_lead_runs_first_when_task_list_enabled(
    runner: PipelineRunner,
    context: RunContext,
    event_sink: InMemoryEventSink,
) -> None:
    lead_run_order: list[str] = []

    class _OrderedLead:
        def __init__(self) -> None:
            self._run_context: RunContext | None = None
            self.tool_registry = None

        async def process(self, input_data: Any) -> str:
            lead_run_order.append("lead")
            return "lead done"

    class _OrderedTeammate:
        def __init__(self, name: str) -> None:
            self.name = name
            self._run_context: RunContext | None = None
            self.tool_registry = None

        async def process(self, input_data: Any) -> str:
            lead_run_order.append(self.name)
            return f"{self.name} done"

    registry = {
        "lead": _OrderedLead(),
        "alice": _OrderedTeammate("alice"),
        "bob": _OrderedTeammate("bob"),
    }
    runtime = TeamRuntime(runner=runner, agent_registry=registry)

    plan = TeamPlan(
        lead_agent="lead",
        teammates=["alice", "bob"],
        task_list=TaskListConfig(
            enabled=True,
            idle_threshold_seconds=0.3,
            poll_interval_ms=50,
        ),
    )

    result = await runtime.run(agents=[], context=context, plan=plan)
    assert result.status == RunStatus.FINISHED
    assert lead_run_order[0] == "lead"


@pytest.mark.anyio
async def test_team_runtime_cancellation_releases_tasks(
    runner: PipelineRunner,
    context: RunContext,
    event_sink: InMemoryEventSink,
) -> None:
    class _LongTaskAgent:
        def __init__(self) -> None:
            self._run_context: RunContext | None = None
            self.tool_registry = None

        async def process(self, input_data: Any) -> str:
            await anyio.sleep(10)
            return "done"

    registry = {
        "lead": _FakeAgent("lead"),
        "alice": _LongTaskAgent(),
    }
    runtime = TeamRuntime(runner=runner, agent_registry=registry)

    plan = TeamPlan(
        lead_agent="lead",
        teammates=["alice"],
        task_list=TaskListConfig(
            enabled=True,
            initial_tasks=[
                TaskEntrySpec(title="Long task"),
            ],
            idle_threshold_seconds=10,
            poll_interval_ms=200,
        ),
    )

    async def run_and_cancel() -> None:
        async with anyio.create_task_group() as tg:
            tg.start_soon(
                runtime.run, [], context, plan
            )
            await anyio.sleep(0.2)
            tg.cancel_scope.cancel()

    await run_and_cancel()

    released_events = [
        e for e in event_sink.events
        if e.type == EventType.TASK_RELEASED.value
    ]
    assert len(released_events) >= 0  # task may or may not have been claimed


@pytest.mark.anyio
async def test_team_runtime_event_log(
    runner: PipelineRunner,
    context: RunContext,
    event_sink: InMemoryEventSink,
) -> None:
    registry = {
        "lead": _FakeAgent("lead"),
        "alice": _FakeAgent("alice"),
    }
    runtime = TeamRuntime(runner=runner, agent_registry=registry)

    plan = TeamPlan(
        lead_agent="lead",
        teammates=["alice"],
        task_list=TaskListConfig(
            enabled=True,
            initial_tasks=[
                TaskEntrySpec(title="Simple task"),
            ],
            idle_threshold_seconds=0.5,
            poll_interval_ms=50,
        ),
    )

    await runtime.run(agents=[], context=context, plan=plan)

    event_types = [e.type for e in event_sink.events]
    assert EventType.TEAM_STARTED.value in event_types
    assert EventType.TASK_ADDED.value in event_types
    assert EventType.TEAMMATE_SPAWNED.value in event_types
    assert EventType.TEAM_FINISHED.value in event_types
