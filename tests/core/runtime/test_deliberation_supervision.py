"""Integration tests for supervision in DeliberationRuntime.

Verifies that DeliberationRuntime correctly integrates with FlowSupervisor to
restart, stop, or escalate on agent failures during contribution and review
phases -- while preserving backward compatibility for plans without supervision.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from miniautogen.core.contracts.coordination import DeliberationPlan
from miniautogen.core.contracts.deliberation import (
    DeliberationState,
    FinalDocument,
    PeerReview,
    ResearchOutput,
)
from miniautogen.core.contracts.enums import RunStatus, SupervisionStrategy
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.supervision import StepSupervision
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.events.types import EventType
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


class _FakeAgent:
    """Agent that supports contribute, review, consolidate, produce_final_document.

    Can fail a configurable number of times on contribute/review before succeeding.
    """

    def __init__(
        self,
        role_name: str,
        *,
        fail_contribute_times: int = 0,
        fail_review_times: int = 0,
        contribute_exc: Exception | None = None,
        review_exc: Exception | None = None,
    ) -> None:
        self.role_name = role_name
        self._fail_contribute_times = fail_contribute_times
        self._fail_review_times = fail_review_times
        self._contribute_exc = contribute_exc or ConnectionError("transient")
        self._review_exc = review_exc or ConnectionError("transient")
        self.contribute_calls = 0
        self.review_calls = 0

    async def contribute(self, topic: str) -> ResearchOutput:
        self.contribute_calls += 1
        if self.contribute_calls <= self._fail_contribute_times:
            raise self._contribute_exc
        return ResearchOutput(
            role_name=self.role_name,
            section_title=f"{self.role_name} findings",
            findings=[f"Finding from {self.role_name}"],
            facts=[f"Fact from {self.role_name}"],
            recommendation=f"Recommendation from {self.role_name}",
        )

    async def review(self, target_role: str, output: ResearchOutput) -> PeerReview:
        self.review_calls += 1
        if self.review_calls <= self._fail_review_times:
            raise self._review_exc
        return PeerReview(
            reviewer_role=self.role_name,
            target_role=target_role,
            target_section_title=output.section_title,
            strengths=["good"],
            concerns=[],
            questions=[],
        )

    async def consolidate(
        self,
        topic: str,
        contributions: list[ResearchOutput],
        reviews: list[PeerReview] | None = None,
    ) -> DeliberationState:
        return DeliberationState(
            review_cycle=1,
            accepted_facts=["fact"],
            leader_decision="proceed",
            is_sufficient=True,
        )

    async def produce_final_document(
        self, state: DeliberationState, contributions: list[ResearchOutput]
    ) -> FinalDocument:
        return FinalDocument(
            executive_summary="Summary",
            accepted_facts=["fact"],
            open_conflicts=[],
            pending_decisions=[],
            recommendations=["rec"],
            decision_summary="Decision",
            body_markdown="# Body",
        )


class _AlwaysFailContributeAgent(_FakeAgent):
    """Agent whose contribute always raises."""

    def __init__(self, role_name: str, exc: Exception) -> None:
        super().__init__(role_name)
        self._always_fail_exc = exc

    async def contribute(self, topic: str) -> ResearchOutput:
        self.contribute_calls += 1
        raise self._always_fail_exc


class _AlwaysFailReviewAgent(_FakeAgent):
    """Agent whose review always raises."""

    def __init__(self, role_name: str, exc: Exception) -> None:
        super().__init__(role_name)
        self._always_fail_review_exc = exc

    async def review(self, target_role: str, output: ResearchOutput) -> PeerReview:
        self.review_calls += 1
        raise self._always_fail_review_exc


# ---------------------------------------------------------------------------
# Tests: Backward compatibility
# ---------------------------------------------------------------------------


class TestDeliberationBackwardCompatibility:
    """No supervision = fail-fast (existing behaviour preserved)."""

    @pytest.mark.asyncio
    async def test_contribution_failure_without_supervision_fails_fast(self) -> None:
        agent = _AlwaysFailContributeAgent("alice", RuntimeError("boom"))
        registry: dict[str, Any] = {"alice": agent}
        event_sink = InMemoryEventSink()
        runner = PipelineRunner(event_sink=event_sink)
        runtime = DeliberationRuntime(runner=runner, agent_registry=registry)

        plan = DeliberationPlan(topic="test", participants=["alice"])
        result = await runtime.run(agents=[], context=_make_context(), plan=plan)

        assert result.status == RunStatus.FAILED
        assert "RuntimeError" in (result.error or "")
        assert agent.contribute_calls == 1

    @pytest.mark.asyncio
    async def test_review_failure_without_supervision_fails_fast(self) -> None:
        fail_reviewer = _AlwaysFailReviewAgent("bob", RuntimeError("review-boom"))
        ok_agent = _FakeAgent("alice")
        registry: dict[str, Any] = {"alice": ok_agent, "bob": fail_reviewer}
        event_sink = InMemoryEventSink()
        runner = PipelineRunner(event_sink=event_sink)
        runtime = DeliberationRuntime(runner=runner, agent_registry=registry)

        plan = DeliberationPlan(topic="test", participants=["alice", "bob"])
        result = await runtime.run(agents=[], context=_make_context(), plan=plan)

        assert result.status == RunStatus.FAILED
        assert "RuntimeError" in (result.error or "")


# ---------------------------------------------------------------------------
# Tests: Contribution supervision with restarts
# ---------------------------------------------------------------------------


class TestDeliberationContributionSupervision:
    """Supervision restarts on contribution failures."""

    @pytest.mark.asyncio
    async def test_transient_contribute_failure_restarts_and_succeeds(self) -> None:
        agent = _FakeAgent("alice", fail_contribute_times=2)
        registry: dict[str, Any] = {"alice": agent}
        event_sink = InMemoryEventSink()
        runner = PipelineRunner(event_sink=event_sink)
        runtime = DeliberationRuntime(runner=runner, agent_registry=registry)

        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESTART,
            max_restarts=3,
            restart_window_seconds=60.0,
        )
        plan = DeliberationPlan(
            topic="test",
            participants=["alice"],
            default_supervision=supervision,
        )

        result = await runtime.run(agents=[], context=_make_context(), plan=plan)

        assert result.status == RunStatus.FINISHED
        assert agent.contribute_calls == 3  # 2 failures + 1 success

    @pytest.mark.asyncio
    async def test_permanent_contribute_error_stops_immediately(self) -> None:
        agent = _AlwaysFailContributeAgent("alice", KeyError("missing"))
        registry: dict[str, Any] = {"alice": agent}
        event_sink = InMemoryEventSink()
        runner = PipelineRunner(event_sink=event_sink)
        runtime = DeliberationRuntime(runner=runner, agent_registry=registry)

        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESTART,
            max_restarts=5,
        )
        plan = DeliberationPlan(
            topic="test",
            participants=["alice"],
            default_supervision=supervision,
        )

        result = await runtime.run(agents=[], context=_make_context(), plan=plan)

        assert result.status == RunStatus.FAILED
        # PERMANENT forces STOP on first failure
        assert agent.contribute_calls == 1


# ---------------------------------------------------------------------------
# Tests: Review supervision with restarts
# ---------------------------------------------------------------------------


class TestDeliberationReviewSupervision:
    """Supervision restarts on review failures."""

    @pytest.mark.asyncio
    async def test_transient_review_failure_restarts_and_succeeds(self) -> None:
        # bob reviews alice's output; bob fails once then succeeds
        alice = _FakeAgent("alice")
        bob = _FakeAgent("bob", fail_review_times=1)
        registry: dict[str, Any] = {"alice": alice, "bob": bob}
        event_sink = InMemoryEventSink()
        runner = PipelineRunner(event_sink=event_sink)
        runtime = DeliberationRuntime(runner=runner, agent_registry=registry)

        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESTART,
            max_restarts=3,
            restart_window_seconds=60.0,
        )
        plan = DeliberationPlan(
            topic="test",
            participants=["alice", "bob"],
            default_supervision=supervision,
        )

        result = await runtime.run(agents=[], context=_make_context(), plan=plan)

        assert result.status == RunStatus.FINISHED
        # bob reviewed alice's output: 1 fail + 1 success = 2 calls
        assert bob.review_calls == 2

    @pytest.mark.asyncio
    async def test_permanent_review_error_stops_immediately(self) -> None:
        alice = _FakeAgent("alice")
        bob = _AlwaysFailReviewAgent("bob", KeyError("perm"))
        registry: dict[str, Any] = {"alice": alice, "bob": bob}
        event_sink = InMemoryEventSink()
        runner = PipelineRunner(event_sink=event_sink)
        runtime = DeliberationRuntime(runner=runner, agent_registry=registry)

        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESTART,
            max_restarts=5,
        )
        plan = DeliberationPlan(
            topic="test",
            participants=["alice", "bob"],
            default_supervision=supervision,
        )

        result = await runtime.run(agents=[], context=_make_context(), plan=plan)

        assert result.status == RunStatus.FAILED
        assert bob.review_calls == 1


# ---------------------------------------------------------------------------
# Tests: Retry events
# ---------------------------------------------------------------------------


class TestDeliberationRetryEvents:
    """Verify supervision events are emitted on retry."""

    @pytest.mark.asyncio
    async def test_retry_succeeded_event_emitted_on_contribute(self) -> None:
        agent = _FakeAgent("alice", fail_contribute_times=1)
        registry: dict[str, Any] = {"alice": agent}
        event_sink = InMemoryEventSink()
        runner = PipelineRunner(event_sink=event_sink)
        runtime = DeliberationRuntime(runner=runner, agent_registry=registry)

        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESTART,
            max_restarts=3,
            restart_window_seconds=60.0,
        )
        plan = DeliberationPlan(
            topic="test",
            participants=["alice"],
            default_supervision=supervision,
        )

        result = await runtime.run(agents=[], context=_make_context(), plan=plan)

        assert result.status == RunStatus.FINISHED
        retry_events = [
            e for e in event_sink.events
            if e.type == EventType.SUPERVISION_RETRY_SUCCEEDED.value
        ]
        assert len(retry_events) >= 1
