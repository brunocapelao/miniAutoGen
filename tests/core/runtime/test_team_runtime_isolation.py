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
