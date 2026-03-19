"""DeliberationRuntime — multi-round deliberation with peer review (phases 3A-3C).

Implements the full deliberation cycle:
  1. Contribution — each participant produces structured output
  2. Peer Review — each participant reviews other participants' outputs
  3. Consolidation — leader synthesizes contributions and reviews
  4. Sufficiency check — leader decides if another round is needed
  5. Final document — leader produces a final document when sufficient or max rounds reached
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from miniautogen.core.contracts.coordination import (
    CoordinationKind,
    DeliberationPlan,
)
from miniautogen.core.contracts.deliberation import (
    DeliberationState,
    PeerReview,
    ResearchOutput,
)
from miniautogen.core.contracts.enums import RunStatus, SupervisionStrategy
from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.run_result import RunResult
from miniautogen.core.events.types import EventType
from miniautogen.core.runtime.classifier import classify_error
from miniautogen.core.runtime.deliberation import (
    build_follow_up_tasks,
    summarize_peer_reviews,
)
from miniautogen.core.runtime.final_document import render_final_document_markdown
from miniautogen.core.runtime.flow_supervisor import FlowSupervisor
from miniautogen.core.runtime.pipeline_runner import PipelineRunner
from miniautogen.observability import get_logger
from miniautogen.policies.effect import EffectPolicy

_SCOPE = "deliberation_runtime"

_EVT_STARTED = EventType.DELIBERATION_STARTED.value
_EVT_FINISHED = EventType.DELIBERATION_FINISHED.value
_EVT_FAILED = EventType.DELIBERATION_FAILED.value


class DeliberationRuntime:
    """Multi-round deliberation coordinator with peer review."""

    kind: CoordinationKind = CoordinationKind.DELIBERATION

    def __init__(
        self,
        runner: PipelineRunner,
        agent_registry: dict[str, Any] | None = None,
        effect_policy: EffectPolicy | None = None,
    ) -> None:
        self._runner = runner
        self._registry: dict[str, Any] = agent_registry or {}
        self._logger = get_logger(__name__)

        self._effect_interceptor: Any = None
        if effect_policy is not None:
            from miniautogen.core.effect_interceptor import EffectInterceptor
            from miniautogen.stores.in_memory_effect_journal import InMemoryEffectJournal

            self._effect_interceptor = EffectInterceptor(
                journal=InMemoryEffectJournal(),
                policy=effect_policy,
                event_sink=runner.event_sink,
            )

    # ------------------------------------------------------------------
    # CoordinationMode.run
    # ------------------------------------------------------------------

    async def run(
        self,
        agents: list[Any],
        context: RunContext,
        plan: DeliberationPlan,
    ) -> RunResult:
        """Execute a deliberation plan and return a RunResult.

        Note: ``agents`` is part of the CoordinationMode protocol signature
        for composability.  Actual agent resolution uses the ``agent_registry``
        injected at construction time.
        """
        correlation_id = context.correlation_id or str(uuid4())
        logger = self._logger.bind(
            run_id=context.run_id,
            correlation_id=correlation_id,
            scope=_SCOPE,
        )

        # --- validate BEFORE emitting started event ---
        if not plan.participants:
            error_msg = "Deliberation requires at least one participant"
            logger.error("deliberation_validation_failed", error=error_msg)
            return RunResult(
                run_id=context.run_id,
                status=RunStatus.FAILED,
                error=error_msg,
            )

        missing = [p for p in plan.participants if p not in self._registry]
        if missing:
            error_msg = f"Participants not found in registry: {', '.join(missing)}"
            logger.error("deliberation_validation_failed", missing=missing)
            return RunResult(
                run_id=context.run_id,
                status=RunStatus.FAILED,
                error=error_msg,
            )

        leader_name = plan.leader_agent or plan.participants[0]
        if leader_name not in self._registry:
            error_msg = f"Leader agent '{leader_name}' not found in registry"
            logger.error("deliberation_validation_failed", error=error_msg)
            return RunResult(
                run_id=context.run_id,
                status=RunStatus.FAILED,
                error=error_msg,
            )

        # --- emit started event (only after validation passes) ---
        await self._emit(
            event_type=_EVT_STARTED,
            run_id=context.run_id,
            correlation_id=correlation_id,
            payload={"topic": plan.topic, "participants": plan.participants},
        )
        logger.info(
            "deliberation_started",
            topic=plan.topic,
            participants=plan.participants,
        )

        # --- resolve leader ---
        leader_agent = self._registry[leader_name]

        supervisor = FlowSupervisor(event_sink=self._runner.event_sink)
        state = DeliberationState()
        contributions: list[ResearchOutput] = []
        follow_ups: dict[str, list[str]] = {}

        for round_num in range(plan.max_rounds):
            logger.info("round_started", round_num=round_num + 1)

            # --- phase 1: contributions ---
            contributions = []
            for participant_name in plan.participants:
                agent = self._registry[participant_name]
                step_id = f"contribute:{participant_name}"
                restart_count = 0
                error_categories: list[str] = []

                while True:
                    try:
                        output = await agent.contribute(plan.topic)
                        contributions.append(output)
                        logger.info(
                            "contribution_collected",
                            participant=participant_name,
                            round_num=round_num + 1,
                        )
                        if restart_count > 0:
                            await supervisor.emit_retry_succeeded(
                                step_id=step_id,
                                total_attempts=restart_count + 1,
                                error_categories_encountered=error_categories,
                            )
                        break
                    except BaseException as exc:
                        if not isinstance(exc, Exception):
                            raise

                        supervision = plan.default_supervision
                        if supervision is None:
                            error_msg = (
                                f"Agent '{participant_name}' failed "
                                f"during contribution: {type(exc).__name__}"
                            )
                            logger.error(
                                "contribution_failed",
                                participant=participant_name,
                                error=str(exc),
                            )
                            await self._emit(
                                event_type=_EVT_FAILED,
                                run_id=context.run_id,
                                correlation_id=correlation_id,
                                payload={"error": error_msg},
                            )
                            return RunResult(
                                run_id=context.run_id,
                                status=RunStatus.FAILED,
                                error=error_msg,
                            )

                        category = classify_error(exc)
                        error_categories.append(category.value)
                        decision = await supervisor.handle_step_failure(
                            step_id=step_id,
                            error=exc,
                            error_category=category,
                            supervision=supervision,
                            restart_count=restart_count,
                        )

                        if decision.action == SupervisionStrategy.RESTART:
                            restart_count += 1
                            continue

                        # STOP or ESCALATE → fail the deliberation
                        error_msg = f"Agent '{participant_name}' failed during contribution: {type(exc).__name__}"
                        logger.error(
                            "contribution_failed",
                            participant=participant_name,
                            error=str(exc),
                        )
                        await self._emit(
                            event_type=_EVT_FAILED,
                            run_id=context.run_id,
                            correlation_id=correlation_id,
                            payload={"error": error_msg},
                        )
                        return RunResult(
                            run_id=context.run_id,
                            status=RunStatus.FAILED,
                            error=error_msg,
                        )

            # --- phase 2: peer review (3B) ---
            reviews: list[PeerReview] = []
            for participant_name in plan.participants:
                agent = self._registry[participant_name]
                for contribution in contributions:
                    # Each agent reviews OTHER agents' outputs
                    if contribution.role_name == participant_name:
                        continue

                    step_id = f"review:{participant_name}:{contribution.role_name}"
                    restart_count = 0
                    error_categories = []

                    while True:
                        try:
                            review = await agent.review(
                                contribution.role_name, contribution
                            )
                            reviews.append(review)
                            logger.info(
                                "peer_review_collected",
                                reviewer=participant_name,
                                target=contribution.role_name,
                            )
                            if restart_count > 0:
                                await supervisor.emit_retry_succeeded(
                                    step_id=step_id,
                                    total_attempts=restart_count + 1,
                                    error_categories_encountered=error_categories,
                                )
                            break
                        except BaseException as exc:
                            if not isinstance(exc, Exception):
                                raise

                            supervision = plan.default_supervision
                            if supervision is None:
                                error_msg = (
                                    f"Agent '{participant_name}' failed during "
                                    f"peer review of '{contribution.role_name}': {type(exc).__name__}"
                                )
                                logger.error(
                                    "peer_review_failed",
                                    reviewer=participant_name,
                                    target=contribution.role_name,
                                    error=str(exc),
                                )
                                await self._emit(
                                    event_type=_EVT_FAILED,
                                    run_id=context.run_id,
                                    correlation_id=correlation_id,
                                    payload={"error": error_msg},
                                )
                                return RunResult(
                                    run_id=context.run_id,
                                    status=RunStatus.FAILED,
                                    error=error_msg,
                                )

                            category = classify_error(exc)
                            error_categories.append(category.value)
                            decision = await supervisor.handle_step_failure(
                                step_id=step_id,
                                error=exc,
                                error_category=category,
                                supervision=supervision,
                                restart_count=restart_count,
                            )

                            if decision.action == SupervisionStrategy.RESTART:
                                restart_count += 1
                                continue

                            # STOP or ESCALATE → fail the deliberation
                            error_msg = (
                                f"Agent '{participant_name}' failed during "
                                f"peer review of '{contribution.role_name}': {type(exc).__name__}"
                            )
                            logger.error(
                                "peer_review_failed",
                                reviewer=participant_name,
                                target=contribution.role_name,
                                error=str(exc),
                            )
                            await self._emit(
                                event_type=_EVT_FAILED,
                                run_id=context.run_id,
                                correlation_id=correlation_id,
                                payload={"error": error_msg},
                            )
                            return RunResult(
                                run_id=context.run_id,
                                status=RunStatus.FAILED,
                                error=error_msg,
                            )

            grouped_reviews = summarize_peer_reviews(reviews)
            follow_ups = build_follow_up_tasks(grouped_reviews)

            logger.info(
                "peer_reviews_summarized",
                review_count=len(reviews),
                follow_up_count=sum(len(v) for v in follow_ups.values()),
            )

            # --- phase 3: leader consolidation ---
            try:
                state = await leader_agent.consolidate(
                    plan.topic, contributions, reviews
                )
                logger.info(
                    "consolidation_complete",
                    leader=leader_name,
                    round_num=round_num + 1,
                )
            except Exception as exc:
                error_msg = f"Leader '{leader_name}' failed during consolidation: {type(exc).__name__}"
                logger.error(
                    "consolidation_failed",
                    leader=leader_name,
                    error=str(exc),
                )
                await self._emit(
                    event_type=_EVT_FAILED,
                    run_id=context.run_id,
                    correlation_id=correlation_id,
                    payload={"error": error_msg},
                )
                return RunResult(
                    run_id=context.run_id,
                    status=RunStatus.FAILED,
                    error=error_msg,
                )

            # --- phase 4: sufficiency check (3C) ---
            if state.is_sufficient:
                logger.info(
                    "deliberation_sufficient",
                    round_num=round_num + 1,
                )
                break

            logger.info(
                "deliberation_insufficient",
                round_num=round_num + 1,
                rejection_reasons=state.rejection_reasons,
            )

        # --- phase 5: final document (3C) ---
        try:
            final_doc = await leader_agent.produce_final_document(
                state, contributions
            )
            rendered = render_final_document_markdown(final_doc)
            logger.info("final_document_produced", leader=leader_name)
        except Exception as exc:
            error_msg = f"Leader '{leader_name}' failed producing final document: {type(exc).__name__}"
            logger.error(
                "final_document_failed",
                leader=leader_name,
                error=str(exc),
            )
            await self._emit(
                event_type=_EVT_FAILED,
                run_id=context.run_id,
                correlation_id=correlation_id,
                payload={"error": error_msg},
            )
            return RunResult(
                run_id=context.run_id,
                status=RunStatus.FAILED,
                error=error_msg,
            )

        # --- emit finished event ---
        await self._emit(
            event_type=_EVT_FINISHED,
            run_id=context.run_id,
            correlation_id=correlation_id,
            payload={
                "leader": leader_name,
                "contributions_count": len(contributions),
                "rounds_completed": state.review_cycle,
            },
        )
        logger.info("deliberation_finished")

        return RunResult(
            run_id=context.run_id,
            status=RunStatus.FINISHED,
            output=state,
            metadata={
                "final_document": final_doc.model_dump(),
                "rendered_markdown": rendered,
                "follow_up_tasks": follow_ups,
            },
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _emit(
        self,
        *,
        event_type: str,
        run_id: str,
        correlation_id: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        await self._runner.event_sink.publish(
            ExecutionEvent(
                type=event_type,
                timestamp=datetime.now(timezone.utc),
                run_id=run_id,
                correlation_id=correlation_id,
                scope=_SCOPE,
                payload=payload or {},
            )
        )
