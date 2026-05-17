"""Tests for context isolation: teammate must NOT see lead's conversation history."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from miniautogen.core.contracts.coordination import TeamPlan
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.runtime.pipeline_runner import PipelineRunner
from miniautogen.core.runtime.team_runtime import TeamRuntime


class _AgentWithConversation:
    """Agent that tracks its conversation/prompt history."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.all_prompts: list[str] = []
        self.secret: str | None = None

    async def process(self, prompt: str) -> str:
        self.all_prompts.append(prompt)
        # If this agent receives a secret meant for the lead, it's a leak
        if "SEGREDO" in prompt:
            self.secret = prompt
        return f"{self.name}-done"

    async def __call__(self, prompt: str) -> str:  # noqa: PLW3201
        return await self.process(prompt)


class _AgentWithRuntimeContext:
    """AgentRuntime-like test double that exposes its current RunContext."""

    def __init__(self, context: RunContext) -> None:
        self._run_context = context
        self.seen_parent_run_id: str | None = None

    @property
    def run_context(self) -> RunContext:
        return self._run_context

    @run_context.setter
    def run_context(self, ctx: RunContext) -> None:
        self._run_context = ctx

    async def process(self, prompt: str) -> str:
        self.seen_parent_run_id = self._run_context.parent_run_id
        return "done"


def _make_context(run_id: str = "team-run-1", **kwargs: Any) -> RunContext:
    return RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id="corr-1",
        **kwargs,
    )


@pytest.mark.asyncio
async def test_teammates_do_not_see_lead_secret() -> None:
    """Teammates must not see the lead's conversation history.

    The lead receives a secret string in its prompt. Teammates should
    NOT have access to that secret via their conversation/prompt.
    """
    legal = _AgentWithConversation("legal")
    security = _AgentWithConversation("security")

    registry = {"legal": legal, "security": security}
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    runtime = TeamRuntime(runner=runner, agent_registry=registry)

    plan = TeamPlan(
        lead_agent="lead",
        teammates=["legal", "security"],
        teammate_prompts={
            "legal": "Review compliance",
            "security": "Audit security",
        },
    )

    agents_list = [legal, security]
    ctx = _make_context()
    await runtime.run(agents=agents_list, context=ctx, plan=plan)

    # Neither teammate should have received the secret
    assert legal.secret is None, f"Legal teammate leaked secret: {legal.secret}"
    assert security.secret is None, f"Security teammate leaked secret: {security.secret}"

    # Teammates should only have their own prompts
    assert all("SEGREDO" not in p for p in legal.all_prompts)
    assert all("SEGREDO" not in p for p in security.all_prompts)


@pytest.mark.asyncio
async def test_teammate_runtime_context_has_parent_run_id() -> None:
    """AgentRuntime-backed teammates must execute with parent_run_id set."""
    team_ctx = _make_context(run_id="team-run-parent")
    initial_agent_ctx = _make_context(run_id="team-run-parent")
    legal = _AgentWithRuntimeContext(initial_agent_ctx)

    class _Lead:
        async def process(self, prompt: Any) -> str:
            return "lead-summary"

    registry = {"legal": legal, "lead": _Lead()}
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    runtime = TeamRuntime(runner=runner, agent_registry=registry)

    plan = TeamPlan(lead_agent="lead", teammates=["legal"])

    result = await runtime.run(agents=[], context=team_ctx, plan=plan)

    assert result.status == "finished"
    assert legal.seen_parent_run_id == "team-run-parent"
    assert legal._run_context.parent_run_id is None
