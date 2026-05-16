"""Tests for TeamRuntime timeout policy integration."""

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
from miniautogen.policies.timeout_policy import TimeoutPolicy


class _SlowAgent:
    async def process(self, prompt: str) -> str:
        await anyio.sleep(0.2)
        return "slow-done"


class _LeadAgent:
    def __init__(self) -> None:
        self.received: Any = None

    async def process(self, input_data: Any) -> str:
        self.received = input_data
        return "lead-summary"


def _make_context(run_id: str = "team-run-timeout") -> RunContext:
    return RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id=run_id,
    )


@pytest.mark.asyncio
async def test_teammate_timeout_uses_timeout_policy() -> None:
    """A timed-out teammate must stop quickly and be reported to the lead."""
    lead = _LeadAgent()
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    timeout_policy = TimeoutPolicy(
        agent_timeouts={"slow": 0.01},
        round_timeouts={},
        flow_timeout=None,
        engine_timeout=120.0,
        on_timeout_action="continue",
    )
    runtime = TeamRuntime(
        runner=runner,
        agent_registry={"slow": _SlowAgent(), "lead": lead},
        timeout_policy=timeout_policy,
    )
    plan = TeamPlan(lead_agent="lead", teammates=["slow"])

    start = anyio.current_time()
    result = await runtime.run(agents=[], context=_make_context(), plan=plan)
    elapsed = anyio.current_time() - start

    assert result.status == "finished"
    assert elapsed < 0.1
    assert lead.received is not None
    contribution = lead.received["_contributions"]["slow"]
    assert contribution.status == "failed"
    assert contribution.error_category == "timeout"
    assert contribution.error_message == "agent_timeout"
    assert any(e.type == EventType.AGENT_TURN_TIMED_OUT.value for e in event_sink.events)
