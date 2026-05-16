"""Tests for TeamRuntime parallel execution of teammates."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import anyio
import pytest

from miniautogen.core.contracts.coordination import TeamPlan
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.runtime.pipeline_runner import PipelineRunner
from miniautogen.core.runtime.team_runtime import TeamRuntime


class _SleepAgent:
    """Agent that sleeps for a given duration and returns a string."""

    def __init__(self, name: str, sleep_seconds: float) -> None:
        self.name = name
        self.sleep_seconds = sleep_seconds
        self.received_prompt: str | None = None
        self.received_input: Any = None

    async def process(self, prompt: str) -> str:
        self.received_prompt = prompt if isinstance(prompt, str) else str(prompt)
        self.received_input = prompt
        await anyio.sleep(self.sleep_seconds)
        return f"{self.name}-done"


class _LeadAgent:
    """Agent that receives contributions dict and returns a summary."""

    def __init__(self) -> None:
        self.received: Any = None

    async def process(self, input_data: Any) -> str:
        self.received = input_data
        if isinstance(input_data, dict) and "_contributions" in input_data:
            contribs = input_data["_contributions"]
            names = list(contribs.keys())
            return f"lead-consolidated: {', '.join(sorted(names))}"
        return "lead-summary"


def _make_context(run_id: str = "team-run-1", **kwargs: Any) -> RunContext:
    return RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id="corr-1",
        **kwargs,
    )


@pytest.mark.asyncio
async def test_three_teammates_run_concurrently() -> None:
    """3 teammates sleeping 100/200/300ms must complete in < ~350ms (parallelism)."""
    agent_a = _SleepAgent("legal", 0.1)
    agent_b = _SleepAgent("security", 0.2)
    agent_c = _SleepAgent("architect", 0.3)
    lead = _LeadAgent()

    registry = {
        "legal": agent_a,
        "security": agent_b,
        "architect": agent_c,
        "lead": lead,
    }
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    runtime = TeamRuntime(runner=runner, agent_registry=registry)

    plan = TeamPlan(
        lead_agent="lead",
        teammates=["legal", "security", "architect"],
        teammate_prompts={
            "legal": "Review legal",
            "security": "Audit security",
            "architect": "Check arch",
        },
        on_teammate_failure="isolate",
    )

    agents_list = [agent_a, agent_b, agent_c, lead]
    ctx = _make_context()
    start = datetime.now()
    result = await runtime.run(agents=agents_list, context=ctx, plan=plan)
    elapsed = (datetime.now() - start).total_seconds()

    assert result.status == "finished"
    # If truly parallel, total < sum of sleeps (~0.6s sequential)
    # Allow overhead: should be < 0.5s (max sleep 0.3 + overhead)
    assert elapsed < 0.5, f"Parallel execution took {elapsed:.3f}s, expected < 0.5s"

    # Lead should have received summaries for all teammates
    assert lead.received is not None
    assert isinstance(lead.received, dict)
    assert "_contributions" in lead.received
    contributions = lead.received["_contributions"]
    for name in ["legal", "security", "architect"]:
        assert name in contributions
        assert contributions[name].status == "finished"

    # Result output is the lead's summary (sorted order)
    assert result.output == "lead-consolidated: architect, legal, security"


@pytest.mark.asyncio
async def test_all_teammates_receive_correct_prompts() -> None:
    """Each teammate must receive its own prompt from teammate_prompts."""
    agent_a = _SleepAgent("legal", 0.01)
    agent_b = _SleepAgent("security", 0.01)
    lead = _LeadAgent()

    registry = {
        "legal": agent_a,
        "security": agent_b,
        "lead": lead,
    }
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    runtime = TeamRuntime(runner=runner, agent_registry=registry)

    plan = TeamPlan(
        lead_agent="lead",
        teammates=["legal", "security"],
        teammate_prompts={
            "legal": "You are a legal reviewer",
            "security": "You are a security auditor",
        },
    )

    agents_list = [agent_a, agent_b, lead]
    ctx = _make_context()
    await runtime.run(agents=agents_list, context=ctx, plan=plan)

    assert agent_a.received_prompt == "You are a legal reviewer"
    assert agent_b.received_prompt == "You are a security auditor"
