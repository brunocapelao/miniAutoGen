"""Tests for TeamRuntime on_teammate_failure='abort_team' policy.

When on_teammate_failure='abort_team', the first failure must cancel
the entire team, and the lead must NOT be invoked.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import anyio
import pytest

from miniautogen.core.contracts.coordination import TeamPlan
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.events.types import EventType
from miniautogen.core.runtime.pipeline_runner import PipelineRunner
from miniautogen.core.runtime.team_runtime import TeamRuntime


class _FakeAgent:
    def __init__(self, name: str, should_fail: bool = False) -> None:
        self.name = name
        self.should_fail = should_fail
        self.called = False

    async def process(self, prompt: str) -> str:
        self.called = True
        await anyio.sleep(0.01)
        if self.should_fail:
            raise RuntimeError(f"{self.name} exploded")
        return f"{self.name}-done"


def _make_context(run_id: str = "team-run-1", **kwargs: Any) -> RunContext:
    return RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id="corr-1",
        **kwargs,
    )


@pytest.mark.asyncio
async def test_abort_team_on_first_failure() -> None:
    """With abort_team, the first failure must cancel all teammates."""
    agent_a = _FakeAgent("legal", should_fail=False)
    agent_b = _FakeAgent("failing", should_fail=True)

    registry = {"legal": agent_a, "failing": agent_b}
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    runtime = TeamRuntime(runner=runner, agent_registry=registry)

    plan = TeamPlan(
        lead_agent="lead",
        teammates=["legal", "failing"],
        teammate_prompts={"legal": "Review", "failing": "Will fail"},
        on_teammate_failure="abort_team",
    )

    ctx = _make_context()
    result = await runtime.run(agents=[agent_a, agent_b], context=ctx, plan=plan)

    assert result.status == "failed"
    assert result.error is not None


@pytest.mark.asyncio
async def test_abort_team_lead_not_invoked() -> None:
    """With abort_team, the lead must NOT be invoked."""
    agent_a = _FakeAgent("legal", should_fail=False)
    agent_b = _FakeAgent("failing", should_fail=True)
    lead_called = False

    class _LeadAgent:
        async def process(self, prompt: str) -> str:
            nonlocal lead_called
            lead_called = True
            return "lead-summary"

    registry = {"legal": agent_a, "failing": agent_b, "lead": _LeadAgent()}
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    runtime = TeamRuntime(runner=runner, agent_registry=registry)

    plan = TeamPlan(
        lead_agent="lead",
        teammates=["legal", "failing"],
        teammate_prompts={"legal": "Review", "failing": "Will fail"},
        on_teammate_failure="abort_team",
    )

    ctx = _make_context()
    await runtime.run(agents=[agent_a, agent_b], context=ctx, plan=plan)

    assert not lead_called, "Lead was invoked despite abort_team policy"


@pytest.mark.asyncio
async def test_abort_team_emits_team_failed_event() -> None:
    """With abort_team, TEAM_FAILED event must be emitted."""
    agent_a = _FakeAgent("legal", should_fail=False)
    agent_b = _FakeAgent("failing", should_fail=True)

    registry = {"legal": agent_a, "failing": agent_b}
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    runtime = TeamRuntime(runner=runner, agent_registry=registry)

    plan = TeamPlan(
        lead_agent="lead",
        teammates=["legal", "failing"],
        teammate_prompts={"legal": "Review", "failing": "Will fail"},
        on_teammate_failure="abort_team",
    )

    ctx = _make_context()
    await runtime.run(agents=[agent_a, agent_b], context=ctx, plan=plan)

    event_types = [e.type for e in event_sink.events]
    assert EventType.TEAM_FAILED.value in event_types
