"""Extended tests for DeliberationRuntime — covering uncovered lines.

Targets:
  - Lines 86-88: empty participants validation
  - Lines 186-203: peer review failure
  - Lines 268-281: final document production failure
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from miniautogen.core.contracts.coordination import (
    CoordinationKind,
    DeliberationPlan,
)
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
# Helpers (reusable across extended tests)
# ---------------------------------------------------------------------------


def _make_context(run_id: str = "run-ext") -> RunContext:
    return RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id="corr-ext",
    )


class FakeAgent:
    """Minimal agent supporting contribute, consolidate, review, produce_final_document."""

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

    async def contribute(self, topic: str) -> ResearchOutput:
        if self._raise_on_contribute is not None:
            raise self._raise_on_contribute
        return self._contribute_result

    async def consolidate(
        self,
        topic: str,
        contributions: list[ResearchOutput],
        reviews: list[PeerReview] | None = None,
    ) -> DeliberationState:
        if self._raise_on_consolidate is not None:
            raise self._raise_on_consolidate
        return self._consolidate_result

    async def review(
        self, target_role: str, output: ResearchOutput
    ) -> PeerReview:
        if self._raise_on_review is not None:
            raise self._raise_on_review
        return PeerReview(
            reviewer_role=self.role_name,
            target_role=target_role,
            target_section_title=output.section_title,
            strengths=["good"],
            concerns=["concern"],
            questions=["question"],
        )

    async def produce_final_document(
        self,
        state: DeliberationState,
        contributions: list[ResearchOutput],
    ) -> FinalDocument:
        if self._raise_on_produce_final_document is not None:
            raise self._raise_on_produce_final_document
        return self._final_document_result


def _make_runtime(
    agents: dict[str, Any] | None = None,
    event_sink: InMemoryEventSink | None = None,
) -> tuple[DeliberationRuntime, InMemoryEventSink]:
    sink = event_sink or InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)
    return DeliberationRuntime(runner=runner, agent_registry=agents), sink


# ---------------------------------------------------------------------------
# Tests — Validation failures (lines 85-112)
# ---------------------------------------------------------------------------


class TestDeliberationValidation:
    @pytest.mark.anyio
    async def test_empty_participants_returns_failed(self) -> None:
        """Covers lines 85-92: plan with no participants.

        Uses model_construct to bypass Pydantic min_length=1 validation,
        exercising the runtime's own defense-in-depth check.
        """
        runtime, sink = _make_runtime(agents={})
        plan = DeliberationPlan.model_construct(
            topic="Empty plan",
            participants=[],
            leader_agent=None,
            max_rounds=1,
        )
        ctx = _make_context()
        result = await runtime.run(agents=[], context=ctx, plan=plan)

        assert result.status == "failed"
        assert "at least one participant" in result.error
        # No started event should have been emitted
        event_types = [e.type for e in sink.events]
        assert not any("started" in t for t in event_types)

    @pytest.mark.anyio
    async def test_missing_participant_in_registry(self) -> None:
        """Covers lines 94-102: participant not found."""
        agent_a = FakeAgent("known")
        runtime, _ = _make_runtime(agents={"known": agent_a})
        plan = DeliberationPlan(
            topic="Missing participant",
            participants=["known", "ghost"],
            leader_agent="known",
            max_rounds=1,
        )
        ctx = _make_context()
        result = await runtime.run(agents=[], context=ctx, plan=plan)

        assert result.status == "failed"
        assert "ghost" in result.error

    @pytest.mark.anyio
    async def test_leader_not_in_registry(self) -> None:
        """Covers lines 104-112: explicit leader not found."""
        agent_a = FakeAgent("a")
        runtime, _ = _make_runtime(agents={"a": agent_a})
        plan = DeliberationPlan(
            topic="Leader missing",
            participants=["a"],
            leader_agent="nonexistent_leader",
            max_rounds=1,
        )
        ctx = _make_context()
        result = await runtime.run(agents=[], context=ctx, plan=plan)

        assert result.status == "failed"
        assert "nonexistent_leader" in result.error


# ---------------------------------------------------------------------------
# Tests — Peer review failure (lines 186-203)
# ---------------------------------------------------------------------------


class TestPeerReviewFailure:
    @pytest.mark.anyio
    async def test_peer_review_exception_returns_failed(self) -> None:
        """Covers lines 186-207: agent raises during review()."""
        good_agent = FakeAgent("good")
        failing_reviewer = FakeAgent(
            "bad_reviewer",
            raise_on_review=RuntimeError("Review crashed"),
        )
        runtime, sink = _make_runtime(
            agents={"good": good_agent, "bad_reviewer": failing_reviewer}
        )
        plan = DeliberationPlan(
            topic="Review failure",
            participants=["good", "bad_reviewer"],
            leader_agent="good",
            max_rounds=1,
        )
        ctx = _make_context()
        result = await runtime.run(agents=[], context=ctx, plan=plan)

        assert result.status == "failed"
        assert "bad_reviewer" in result.error
        assert "RuntimeError" in result.error
        # A failed event should have been emitted
        event_types = [e.type for e in sink.events]
        assert any("failed" in t for t in event_types)


# ---------------------------------------------------------------------------
# Tests — Final document failure (lines 268-281)
# ---------------------------------------------------------------------------


class TestFinalDocumentFailure:
    @pytest.mark.anyio
    async def test_final_document_exception_returns_failed(self) -> None:
        """Covers lines 268-285: leader raises during produce_final_document()."""
        leader = FakeAgent(
            "leader",
            raise_on_produce_final_document=RuntimeError("Doc generation failed"),
        )
        helper = FakeAgent("helper")
        runtime, sink = _make_runtime(
            agents={"leader": leader, "helper": helper}
        )
        plan = DeliberationPlan(
            topic="Final doc failure",
            participants=["leader", "helper"],
            leader_agent="leader",
            max_rounds=1,
        )
        ctx = _make_context()
        result = await runtime.run(agents=[], context=ctx, plan=plan)

        assert result.status == "failed"
        assert "RuntimeError" in result.error
        assert "leader" in result.error.lower()
        # Failed event emitted
        event_types = [e.type for e in sink.events]
        assert any("failed" in t for t in event_types)


# ---------------------------------------------------------------------------
# Tests — Insufficient deliberation round
# ---------------------------------------------------------------------------


class TestInsufficientDeliberation:
    @pytest.mark.anyio
    async def test_insufficient_round_continues(self) -> None:
        """Verify that is_sufficient=False leads to more rounds."""
        round_counter = {"n": 0}

        class CountingAgent(FakeAgent):
            async def consolidate(
                self,
                topic: str,
                contributions: list[ResearchOutput],
                reviews: list[PeerReview] | None = None,
            ) -> DeliberationState:
                round_counter["n"] += 1
                return DeliberationState(
                    review_cycle=round_counter["n"],
                    accepted_facts=["fact"],
                    leader_decision="proceed" if round_counter["n"] >= 3 else "not yet",
                    is_sufficient=round_counter["n"] >= 3,
                    rejection_reasons=[] if round_counter["n"] >= 3 else ["need more"],
                )

        leader = CountingAgent("leader")
        helper = FakeAgent("helper")
        runtime, _ = _make_runtime(agents={"leader": leader, "helper": helper})
        plan = DeliberationPlan(
            topic="Multi-round",
            participants=["leader", "helper"],
            leader_agent="leader",
            max_rounds=5,
        )
        ctx = _make_context()
        result = await runtime.run(agents=[], context=ctx, plan=plan)

        assert result.status == "finished"
        assert round_counter["n"] == 3
