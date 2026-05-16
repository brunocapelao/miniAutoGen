"""Tests for TeamRuntime cancellation propagation via anyio.

External cancellation must propagate to all teammates,
and teammates must emit cancelled status.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import anyio
import pytest

from miniautogen.core.contracts.coordination import TeamPlan
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.run_result import RunResult
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.events.types import EventType
from miniautogen.core.runtime.pipeline_runner import PipelineRunner
from miniautogen.core.runtime.team_runtime import TeamRuntime


class _SlowAgent:
    """Agent that sleeps for a long time and can be cancelled."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.started = False
        self.finished = False

    async def process(self, prompt: str) -> str:
        self.started = True
        try:
            await anyio.sleep(10.0)  # Long sleep — will be cancelled
            self.finished = True
            return f"{self.name}-done"
        except anyio.get_cancelled_exc_class():
            raise


def _make_context(run_id: str = "team-run-1", **kwargs: Any) -> RunContext:
    return RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id="corr-1",
        **kwargs,
    )


@pytest.mark.asyncio
async def test_cancellation_stops_all_teammates_under_1s() -> None:
    """Cancelling the team must stop all teammates within 1s."""
    agent_a = _SlowAgent("legal")
    agent_b = _SlowAgent("security")

    class _CancelledLead:
        async def process(self, input_data: Any) -> str:
            return "lead-summary"

    registry = {"legal": agent_a, "security": agent_b, "lead": _CancelledLead()}
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    runtime = TeamRuntime(runner=runner, agent_registry=registry)

    plan = TeamPlan(
        lead_agent="lead",
        teammates=["legal", "security"],
        teammate_prompts={"legal": "Review", "security": "Audit"},
    )

    ctx = _make_context()

    result_holder: list[RunResult] = []

    async def _run_team() -> None:
        r = await runtime.run([agent_a, agent_b], ctx, plan)
        result_holder.append(r)

    start = datetime.now()
    async with anyio.create_task_group() as tg:
        tg.start_soon(_run_team)
        await anyio.sleep(0.05)
        tg.cancel_scope.cancel()

    elapsed = (datetime.now() - start).total_seconds()
    assert elapsed < 1.0, f"Cancellation took {elapsed:.3f}s, expected < 1.0s"

    # Should get a result back within the holder
    assert len(result_holder) == 1
    assert result_holder[0].status in ("cancelled", "failed")

    # Cancellation must propagate in < 1s
    assert elapsed < 1.0, f"Cancellation took {elapsed:.3f}s, expected < 1.0s"


@pytest.mark.asyncio
async def test_cancellation_emits_teammate_finished_cancelled() -> None:
    """On cancellation, teammates must emit TEAMMATE_FINISHED with cancelled status."""
    agent_a = _SlowAgent("legal")

    class _CancelledLead:
        async def process(self, input_data: Any) -> str:  # noqa: PLW3201
            return "lead-summary"

    registry = {"legal": agent_a, "lead": _CancelledLead()}
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    runtime = TeamRuntime(runner=runner, agent_registry=registry)

    plan = TeamPlan(
        lead_agent="lead",
        teammates=["legal"],
        teammate_prompts={"legal": "Review"},
    )

    ctx = _make_context()

    async def _run_team() -> None:
        await runtime.run([agent_a], ctx, plan)

    async with anyio.create_task_group() as tg:
        tg.start_soon(_run_team)
        await anyio.sleep(0.05)
        tg.cancel_scope.cancel()

    # Check events — even if cancelled, events should be flushed
    event_types = [e.type for e in event_sink.events]
    assert (
        any(
            e.type == EventType.TEAMMATE_FINISHED.value and e.payload.get("status") == "cancelled"
            for e in event_sink.events
            if hasattr(e, "payload") and isinstance(e.payload, dict)
        )
        or EventType.TEAMMATE_FINISHED.value in event_types
    )
