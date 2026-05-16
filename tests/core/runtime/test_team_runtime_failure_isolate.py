"""Tests for TeamRuntime on_teammate_failure='isolate' policy.

When one teammate fails, the others must continue and the lead must
receive a summary with the error information.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import anyio
import pytest

from miniautogen.core.contracts.coordination import ContributionSummary, TeamPlan
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.events.event_sink import InMemoryEventSink
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
            raise ValueError(f"{self.name} failed")
        return f"{self.name}-done"


class _LeadAgent:
    def __init__(self) -> None:
        self.received: Any = None

    async def process(self, input_data: Any) -> str:
        self.received = input_data
        return "lead-summary"


def _make_context(run_id: str = "team-run-1", **kwargs: Any) -> RunContext:
    return RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id="corr-1",
        **kwargs,
    )


@pytest.mark.asyncio
async def test_failing_teammate_isolated_others_complete() -> None:
    """With isolate policy, 1 failing teammate must not stop others."""
    agent_a = _FakeAgent("legal", should_fail=False)
    agent_b = _FakeAgent("failing", should_fail=True)
    agent_c = _FakeAgent("architect", should_fail=False)
    lead = _LeadAgent()

    registry = {
        "legal": agent_a,
        "failing": agent_b,
        "architect": agent_c,
        "lead": lead,
    }
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    runtime = TeamRuntime(runner=runner, agent_registry=registry)

    plan = TeamPlan(
        lead_agent="lead",
        teammates=["legal", "failing", "architect"],
        teammate_prompts={
            "legal": "Review",
            "failing": "Will fail",
            "architect": "Check",
        },
        on_teammate_failure="isolate",
    )

    agents_list = [agent_a, agent_b, agent_c, lead]
    ctx = _make_context()
    result = await runtime.run(agents=agents_list, context=ctx, plan=plan)

    # Must finish (not fail the whole team)
    assert result.status == "finished"
    # Lead must have received summaries
    assert lead.received is not None
    assert isinstance(lead.received, dict)
    assert "_contributions" in lead.received
    contribs = lead.received["_contributions"]

    # Successful teammates
    assert contribs["legal"].status == "finished"
    assert contribs["architect"].status == "finished"

    # Failing teammate should have failed summary
    assert contribs["failing"].status == "failed"
    assert contribs["failing"].error_message is not None


@pytest.mark.asyncio
async def test_isolate_all_succeed() -> None:
    """With isolate policy and no failures, all must be finished."""
    agent_a = _FakeAgent("legal", should_fail=False)
    agent_b = _FakeAgent("security", should_fail=False)
    lead = _LeadAgent()

    registry = {"legal": agent_a, "security": agent_b, "lead": lead}
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    runtime = TeamRuntime(runner=runner, agent_registry=registry)

    plan = TeamPlan(
        lead_agent="lead",
        teammates=["legal", "security"],
        teammate_prompts={"legal": "Review", "security": "Audit"},
        on_teammate_failure="isolate",
    )

    ctx = _make_context()
    result = await runtime.run(agents=[agent_a, agent_b, lead], context=ctx, plan=plan)

    assert result.status == "finished"
    assert all(agent.called for agent in [agent_a, agent_b])


@pytest.mark.asyncio
async def test_contribution_summary_model() -> None:
    """ContributionSummary must be a proper Pydantic model."""
    summary = ContributionSummary(
        teammate="legal",
        status="finished",
        output="legal-done",
    )
    assert summary.teammate == "legal"
    assert summary.status == "finished"
    assert summary.output == "legal-done"
    assert summary.error_category is None
    assert summary.error_message is None

    # Serialization
    dumped = summary.model_dump(mode="json")
    assert dumped["teammate"] == "legal"
    assert dumped["status"] == "finished"
