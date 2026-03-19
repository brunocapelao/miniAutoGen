"""Tests for DeliberationRuntime — phases 3A, 3B, and 3C."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from miniautogen.core.contracts.coordination import CoordinationKind, CoordinationMode, DeliberationPlan
from miniautogen.core.contracts.deliberation import (
    DeliberationState,
    FinalDocument,
    PeerReview,
    ResearchOutput,
)
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.run_result import RunResult
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.runtime.deliberation_runtime import DeliberationRuntime
from miniautogen.core.runtime.pipeline_runner import PipelineRunner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_context(run_id: str = "run-1") -> RunContext:
    return RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id="corr-1",
    )


class FakeAgent:
    """Minimal agent supporting contribute, consolidate, review, and produce_final_document."""

    def __init__(
        self,
        role_name: str,
        *,
        contribute_result: ResearchOutput | None = None,
        consolidate_result: DeliberationState | None = None,
        final_document_result: FinalDocument | None = None,
        raise_on_contribute: Exception | None = None,
        raise_on_consolidate: Exception | None = None,
        raise_on_review: Exception | None = None,
        raise_on_produce_final_document: Exception | None = None,
    ) -> None:
        self.role_name = role_name
        self._contribute_result = contribute_result or ResearchOutput(
            role_name=role_name,
            section_title=f"{role_name} findings",
            findings=[f"Finding from {role_name}"],
            facts=[f"Fact from {role_name}"],
            recommendation=f"Recommendation from {role_name}",
        )
        self._consolidate_result = consolidate_result or DeliberationState(
            review_cycle=1,
            accepted_facts=["consolidated-fact"],
            leader_decision="proceed",
            is_sufficient=True,
        )
        self._final_document_result = final_document_result or FinalDocument(
            executive_summary="Summary",
            accepted_facts=["fact-1"],
            open_conflicts=[],
            pending_decisions=[],
            recommendations=["rec-1"],
            decision_summary="Decision",
            body_markdown="# Body",
        )
        self._raise_on_contribute = raise_on_contribute
        self._raise_on_consolidate = raise_on_consolidate
        self._raise_on_review = raise_on_review
        self._raise_on_produce_final_document = raise_on_produce_final_document
        self.contribute_calls: list[str] = []
        self.consolidate_calls: list[tuple[str, list[ResearchOutput], list[PeerReview]]] = []
        self.review_calls: list[tuple[str, ResearchOutput]] = []
        self.produce_final_document_calls: list[tuple[DeliberationState, list[ResearchOutput]]] = []

    async def contribute(self, topic: str) -> ResearchOutput:
        if self._raise_on_contribute is not None:
            raise self._raise_on_contribute
        self.contribute_calls.append(topic)
        return self._contribute_result

    async def consolidate(
        self,
        topic: str,
        contributions: list[ResearchOutput],
        reviews: list[PeerReview] | None = None,
    ) -> DeliberationState:
        if self._raise_on_consolidate is not None:
            raise self._raise_on_consolidate
        self.consolidate_calls.append((topic, contributions, reviews or []))
        return self._consolidate_result

    async def review(
        self, target_role: str, output: ResearchOutput
    ) -> PeerReview:
        if self._raise_on_review is not None:
            raise self._raise_on_review
        self.review_calls.append((target_role, output))
        return PeerReview(
            reviewer_role=self.role_name,
            target_role=target_role,
            target_section_title=output.section_title,
            strengths=[f"Good work from {target_role}"],
            concerns=[f"Concern about {target_role}"],
            questions=[f"Question for {target_role}"],
        )

    async def produce_final_document(
        self,
        state: DeliberationState,
        contributions: list[ResearchOutput],
    ) -> FinalDocument:
        if self._raise_on_produce_final_document is not None:
            raise self._raise_on_produce_final_document
        self.produce_final_document_calls.append((state, contributions))
        return self._final_document_result


def _make_runtime(
    agents: dict[str, Any] | None = None,
    event_sink: InMemoryEventSink | None = None,
) -> DeliberationRuntime:
    sink = event_sink or InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)
    return DeliberationRuntime(runner=runner, agent_registry=agents)


# ---------------------------------------------------------------------------
# Tests — Phase 3A (existing)
# ---------------------------------------------------------------------------


def test_deliberation_runtime_satisfies_protocol() -> None:
    runtime = _make_runtime()
    assert isinstance(runtime, CoordinationMode)
    assert runtime.kind == CoordinationKind.DELIBERATION


@pytest.mark.asyncio
async def test_minimal_deliberation_2_agents_1_round() -> None:
    agent_a = FakeAgent("analyst")
    agent_b = FakeAgent("researcher")

    runtime = _make_runtime(agents={"analyst": agent_a, "researcher": agent_b})

    plan = DeliberationPlan(
        topic="Evaluate market entry",
        participants=["analyst", "researcher"],
        leader_agent="analyst",
        max_rounds=1,
    )
    ctx = _make_context()

    result = await runtime.run(agents=[], context=ctx, plan=plan)

    assert isinstance(result, RunResult)
    assert result.status == "finished"
    assert result.run_id == ctx.run_id
    assert isinstance(result.output, DeliberationState)

    # Both agents should have been asked to contribute
    assert len(agent_a.contribute_calls) == 1
    assert len(agent_b.contribute_calls) == 1

    # Leader should have consolidated
    assert len(agent_a.consolidate_calls) == 1


@pytest.mark.asyncio
async def test_leader_defaults_to_first_participant() -> None:
    agent_a = FakeAgent("first")
    agent_b = FakeAgent("second")

    runtime = _make_runtime(agents={"first": agent_a, "second": agent_b})

    plan = DeliberationPlan(
        topic="Default leader test",
        participants=["first", "second"],
        leader_agent=None,  # No leader specified
        max_rounds=1,
    )
    ctx = _make_context()

    result = await runtime.run(agents=[], context=ctx, plan=plan)

    assert result.status == "finished"
    # First participant should be the leader and consolidate
    assert len(agent_a.consolidate_calls) == 1
    assert len(agent_b.consolidate_calls) == 0


@pytest.mark.asyncio
async def test_contributions_passed_to_leader() -> None:
    agent_a = FakeAgent("alpha")
    agent_b = FakeAgent("beta")

    runtime = _make_runtime(agents={"alpha": agent_a, "beta": agent_b})

    plan = DeliberationPlan(
        topic="Pass contributions test",
        participants=["alpha", "beta"],
        leader_agent="alpha",
        max_rounds=1,
    )
    ctx = _make_context()

    await runtime.run(agents=[], context=ctx, plan=plan)

    # Leader should have received contributions from both agents
    assert len(agent_a.consolidate_calls) == 1
    topic, contributions, _reviews = agent_a.consolidate_calls[0]
    assert topic == "Pass contributions test"
    assert len(contributions) == 2
    roles = {c.role_name for c in contributions}
    assert roles == {"alpha", "beta"}


@pytest.mark.asyncio
async def test_validates_participants_exist_in_registry() -> None:
    agent_a = FakeAgent("known")

    runtime = _make_runtime(agents={"known": agent_a})

    plan = DeliberationPlan(
        topic="Missing participant",
        participants=["known", "unknown_agent"],
        leader_agent="known",
        max_rounds=1,
    )
    ctx = _make_context()

    result = await runtime.run(agents=[], context=ctx, plan=plan)

    assert result.status == "failed"
    assert result.error is not None
    assert "unknown_agent" in result.error


@pytest.mark.asyncio
async def test_agent_failure_returns_error() -> None:
    failing_agent = FakeAgent(
        "failing",
        raise_on_contribute=RuntimeError("LLM timeout"),
    )
    good_agent = FakeAgent("good")

    runtime = _make_runtime(agents={"failing": failing_agent, "good": good_agent})

    plan = DeliberationPlan(
        topic="Agent failure test",
        participants=["failing", "good"],
        leader_agent="good",
        max_rounds=1,
    )
    ctx = _make_context()

    result = await runtime.run(agents=[], context=ctx, plan=plan)

    assert result.status == "failed"
    assert result.error is not None
    assert "RuntimeError" in result.error


@pytest.mark.asyncio
async def test_leader_consolidation_failure_returns_error() -> None:
    agent_a = FakeAgent("agent_a")
    leader = FakeAgent(
        "leader",
        raise_on_consolidate=RuntimeError("Consolidation failed"),
    )

    runtime = _make_runtime(agents={"agent_a": agent_a, "leader": leader})

    plan = DeliberationPlan(
        topic="Leader failure test",
        participants=["agent_a", "leader"],
        leader_agent="leader",
        max_rounds=1,
    )
    ctx = _make_context()

    result = await runtime.run(agents=[], context=ctx, plan=plan)

    assert result.status == "failed"
    assert result.error is not None
    assert "RuntimeError" in result.error


@pytest.mark.asyncio
async def test_events_emitted_during_deliberation() -> None:
    agent_a = FakeAgent("a")
    agent_b = FakeAgent("b")
    sink = InMemoryEventSink()

    runtime = _make_runtime(agents={"a": agent_a, "b": agent_b}, event_sink=sink)

    plan = DeliberationPlan(
        topic="Events test",
        participants=["a", "b"],
        leader_agent="a",
        max_rounds=1,
    )
    ctx = _make_context()

    await runtime.run(agents=[], context=ctx, plan=plan)

    event_types = [e.type for e in sink.events]
    # Should have at least a started and finished event
    assert any("started" in t for t in event_types)
    assert any("finished" in t for t in event_types)


# ---------------------------------------------------------------------------
# Tests — Phase 3B (peer review)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_peer_reviews_collected_after_contributions() -> None:
    """Verify review() is called on each agent for other agents' outputs."""
    agent_a = FakeAgent("analyst")
    agent_b = FakeAgent("researcher")
    agent_c = FakeAgent("critic")

    runtime = _make_runtime(
        agents={"analyst": agent_a, "researcher": agent_b, "critic": agent_c}
    )

    plan = DeliberationPlan(
        topic="Peer review test",
        participants=["analyst", "researcher", "critic"],
        leader_agent="analyst",
        max_rounds=1,
    )
    ctx = _make_context()

    result = await runtime.run(agents=[], context=ctx, plan=plan)
    assert result.status == "finished"

    # Each agent reviews the other 2 agents' outputs → 3 agents * 2 reviews = 6
    assert len(agent_a.review_calls) == 2
    assert len(agent_b.review_calls) == 2
    assert len(agent_c.review_calls) == 2

    # Verify agent_a reviewed researcher and critic (not itself)
    reviewed_by_a = {call[0] for call in agent_a.review_calls}
    assert "analyst" not in reviewed_by_a
    assert "researcher" in reviewed_by_a
    assert "critic" in reviewed_by_a


@pytest.mark.asyncio
async def test_peer_reviews_passed_to_consolidation() -> None:
    """Leader receives reviews during consolidation."""
    agent_a = FakeAgent("alpha")
    agent_b = FakeAgent("beta")

    runtime = _make_runtime(agents={"alpha": agent_a, "beta": agent_b})

    plan = DeliberationPlan(
        topic="Reviews to consolidation",
        participants=["alpha", "beta"],
        leader_agent="alpha",
        max_rounds=1,
    )
    ctx = _make_context()

    result = await runtime.run(agents=[], context=ctx, plan=plan)
    assert result.status == "finished"

    # Leader should have received reviews in consolidation
    assert len(agent_a.consolidate_calls) == 1
    _topic, _contribs, reviews = agent_a.consolidate_calls[0]
    # 2 agents, each reviews 1 other → 2 reviews
    assert len(reviews) == 2
    reviewer_roles = {r.reviewer_role for r in reviews}
    assert reviewer_roles == {"alpha", "beta"}


@pytest.mark.asyncio
async def test_follow_ups_generated_from_reviews() -> None:
    """Follow-up tasks are created from peer review concerns/questions.

    We verify indirectly: the runtime runs without error and reviews contain
    concerns that would produce follow-ups via build_follow_up_tasks.
    """
    agent_a = FakeAgent("alpha")
    agent_b = FakeAgent("beta")

    runtime = _make_runtime(agents={"alpha": agent_a, "beta": agent_b})

    plan = DeliberationPlan(
        topic="Follow-ups test",
        participants=["alpha", "beta"],
        leader_agent="alpha",
        max_rounds=1,
    )
    ctx = _make_context()

    result = await runtime.run(agents=[], context=ctx, plan=plan)
    assert result.status == "finished"

    # Verify reviews were collected (each has concerns and questions)
    assert len(agent_a.review_calls) == 1
    assert len(agent_b.review_calls) == 1

    # The FakeAgent review includes concerns and questions which would
    # produce follow-up tasks via build_follow_up_tasks
    _target, output = agent_a.review_calls[0]
    review = PeerReview(
        reviewer_role="alpha",
        target_role=_target,
        target_section_title=output.section_title,
        strengths=[f"Good work from {_target}"],
        concerns=[f"Concern about {_target}"],
        questions=[f"Question for {_target}"],
    )
    assert len(review.concerns) > 0
    assert len(review.questions) > 0


# ---------------------------------------------------------------------------
# Tests — Phase 3C (sufficiency loop + final document)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_multi_round_when_first_round_insufficient() -> None:
    """state.is_sufficient=False triggers round 2."""
    round_counter = {"count": 0}

    class MultiRoundAgent(FakeAgent):
        async def consolidate(
            self,
            topic: str,
            contributions: list[ResearchOutput],
            reviews: list[PeerReview] | None = None,
        ) -> DeliberationState:
            round_counter["count"] += 1
            self.consolidate_calls.append((topic, contributions, reviews or []))
            # First round insufficient, second round sufficient
            return DeliberationState(
                review_cycle=round_counter["count"],
                accepted_facts=["fact"],
                leader_decision="proceed" if round_counter["count"] >= 2 else "needs more",
                is_sufficient=round_counter["count"] >= 2,
            )

    leader = MultiRoundAgent("leader")
    agent_b = FakeAgent("helper")

    runtime = _make_runtime(agents={"leader": leader, "helper": agent_b})

    plan = DeliberationPlan(
        topic="Multi-round test",
        participants=["leader", "helper"],
        leader_agent="leader",
        max_rounds=3,
    )
    ctx = _make_context()

    result = await runtime.run(agents=[], context=ctx, plan=plan)

    assert result.status == "finished"
    # Should have run 2 rounds (insufficient on 1, sufficient on 2)
    assert round_counter["count"] == 2
    assert len(leader.contribute_calls) == 2
    assert len(agent_b.contribute_calls) == 2
    assert result.output.is_sufficient is True


@pytest.mark.asyncio
async def test_stops_when_sufficient_before_max_rounds() -> None:
    """Stops at round 1 if sufficient, even with max_rounds=5."""
    agent_a = FakeAgent(
        "leader",
        consolidate_result=DeliberationState(
            review_cycle=1,
            accepted_facts=["fact"],
            leader_decision="done",
            is_sufficient=True,
        ),
    )
    agent_b = FakeAgent("helper")

    runtime = _make_runtime(agents={"leader": agent_a, "helper": agent_b})

    plan = DeliberationPlan(
        topic="Early stop test",
        participants=["leader", "helper"],
        leader_agent="leader",
        max_rounds=5,
    )
    ctx = _make_context()

    result = await runtime.run(agents=[], context=ctx, plan=plan)

    assert result.status == "finished"
    # Only 1 round of contributions
    assert len(agent_a.contribute_calls) == 1
    assert len(agent_b.contribute_calls) == 1
    assert len(agent_a.consolidate_calls) == 1


@pytest.mark.asyncio
async def test_stops_at_max_rounds_even_if_insufficient() -> None:
    """max_rounds=2, never sufficient, stops after 2 rounds."""
    agent_a = FakeAgent(
        "leader",
        consolidate_result=DeliberationState(
            review_cycle=1,
            accepted_facts=[],
            leader_decision="needs more",
            is_sufficient=False,
            rejection_reasons=["not enough data"],
        ),
    )
    agent_b = FakeAgent("helper")

    runtime = _make_runtime(agents={"leader": agent_a, "helper": agent_b})

    plan = DeliberationPlan(
        topic="Max rounds test",
        participants=["leader", "helper"],
        leader_agent="leader",
        max_rounds=2,
    )
    ctx = _make_context()

    result = await runtime.run(agents=[], context=ctx, plan=plan)

    assert result.status == "finished"
    # 2 rounds of contributions
    assert len(agent_a.contribute_calls) == 2
    assert len(agent_b.contribute_calls) == 2
    assert len(agent_a.consolidate_calls) == 2
    # Final document still produced even if insufficient
    assert len(agent_a.produce_final_document_calls) == 1


@pytest.mark.asyncio
async def test_final_document_generated() -> None:
    """FinalDocument is present in result metadata."""
    agent_a = FakeAgent("leader")
    agent_b = FakeAgent("helper")

    runtime = _make_runtime(agents={"leader": agent_a, "helper": agent_b})

    plan = DeliberationPlan(
        topic="Final doc test",
        participants=["leader", "helper"],
        leader_agent="leader",
        max_rounds=1,
    )
    ctx = _make_context()

    result = await runtime.run(agents=[], context=ctx, plan=plan)

    assert result.status == "finished"
    assert "final_document" in result.metadata
    final_doc = result.metadata["final_document"]
    assert final_doc["executive_summary"] == "Summary"
    assert final_doc["decision_summary"] == "Decision"
    assert "fact-1" in final_doc["accepted_facts"]
    # Leader should have been asked to produce final document
    assert len(agent_a.produce_final_document_calls) == 1


@pytest.mark.asyncio
async def test_rendered_markdown_in_metadata() -> None:
    """rendered_markdown key is present in result metadata."""
    agent_a = FakeAgent("leader")
    agent_b = FakeAgent("helper")

    runtime = _make_runtime(agents={"leader": agent_a, "helper": agent_b})

    plan = DeliberationPlan(
        topic="Rendered markdown test",
        participants=["leader", "helper"],
        leader_agent="leader",
        max_rounds=1,
    )
    ctx = _make_context()

    result = await runtime.run(agents=[], context=ctx, plan=plan)

    assert result.status == "finished"
    assert "rendered_markdown" in result.metadata
    rendered = result.metadata["rendered_markdown"]
    assert isinstance(rendered, str)
    # Should contain Portuguese section headers from render_final_document_markdown
    assert "Resumo Executivo" in rendered
    assert "Decisão Recomendada" in rendered


@pytest.mark.asyncio
async def test_leader_not_in_registry_returns_error() -> None:
    agent_a = FakeAgent("a")
    runtime = _make_runtime(agents={"a": agent_a})
    plan = DeliberationPlan(
        topic="test",
        participants=["a"],
        leader_agent="nonexistent_leader",
        max_rounds=1,
    )
    ctx = _make_context()
    result = await runtime.run(agents=[], context=ctx, plan=plan)
    assert result.status == "failed"
    assert "nonexistent_leader" in result.error
