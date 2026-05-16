"""TeamRuntime — peer-to-peer agent team coordination mode.

Each team has a lead and N teammates running concurrently via
anyio.create_task_group. The lead consolidates results after all
teammates finish.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import anyio

from miniautogen.core.contracts.coordination import (
    ContributionSummary,
    CoordinationKind,
    TeamPlan,
)
from miniautogen.core.contracts.enums import RunStatus
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.run_result import RunResult
from miniautogen.core.events.types import EventType
from miniautogen.observability import get_logger

if TYPE_CHECKING:
    from miniautogen.core.runtime.pipeline_runner import PipelineRunner


class TeamAgentTimeout(Exception):
    """Raised internally when a team agent turn times out."""


class TeamRuntime:
    """Coordination mode for agent teams with a lead and concurrent teammates.

    Implements the CoordinationMode[TeamPlan] protocol.
    """

    kind: CoordinationKind = CoordinationKind.TEAM

    def __init__(
        self,
        runner: PipelineRunner,
        agent_registry: dict[str, Any] | None = None,
        timeout_policy: Any | None = None,
    ) -> None:
        self._runner = runner
        self._registry = agent_registry or {}
        self._timeout_policy = timeout_policy
        self._logger = get_logger(__name__)

    async def run(
        self,
        agents: list[Any],
        context: RunContext,
        plan: TeamPlan,
    ) -> RunResult:
        """Execute a team run: validate, spawn teammates concurrently, consolidate.

        Args:
            agents: List of agent runtimes (used if registry fails).
            context: The team-level RunContext.
            plan: The TeamPlan describing lead, teammates, and policies.

        Returns:
            RunResult with consolidated output or error.
        """
        run_id = context.run_id
        self._logger.info("team_run_started", run_id=run_id, lead=plan.lead_agent)

        # 1. Validate plan
        try:
            self._validate_plan(plan)
        except ValueError as exc:
            await self._emit(
                EventType.TEAM_FAILED,
                run_id,
                payload={"error": str(exc), "error_category": "configuration"},
            )
            return RunResult(
                run_id=run_id,
                status=RunStatus.FAILED,
                error=str(exc),
            )

        # 2. Emit TEAM_STARTED
        await self._emit(
            EventType.TEAM_STARTED,
            run_id,
            payload={
                "lead": plan.lead_agent,
                "teammates": plan.teammates,
                "team_run_id": run_id,
            },
        )

        # 3. Run teammates concurrently inside a task group
        contributions: dict[str, ContributionSummary] = {}
        abort = False
        was_cancelled = False
        limiter = (
            anyio.CapacityLimiter(plan.max_concurrent_teammates)
            if plan.max_concurrent_teammates is not None
            else None
        )

        try:
            async with anyio.create_task_group() as tg:
                for teammate_name in plan.teammates:
                    agent = self._registry.get(teammate_name)
                    if agent is None:
                        msg = f"Teammate '{teammate_name}' not found in registry"
                        self._logger.error(msg)
                        abort = True
                        break

                    prompt = plan.teammate_prompts.get(teammate_name, "")
                    sub_run_id = f"{run_id}/{teammate_name}"

                    # Create child RunContext with parent_run_id
                    child_ctx = context.model_copy(
                        update={"parent_run_id": run_id},
                    )

                    # Emit TEAMMATE_SPAWNED
                    await self._emit(
                        EventType.TEAMMATE_SPAWNED,
                        run_id,
                        payload={
                            "teammate": teammate_name,
                            "sub_run_id": sub_run_id,
                            "parent_run_id": run_id,
                        },
                    )

                    tg.start_soon(
                        self._run_teammate,
                        teammate_name,
                        agent,
                        prompt,
                        child_ctx,
                        plan.on_teammate_failure,
                        contributions,
                        run_id,
                        tg.cancel_scope,
                        limiter,
                    )

                if abort:
                    tg.cancel_scope.cancel()

        except anyio.get_cancelled_exc_class():
            was_cancelled = True

        # 4. Check for abort / cancellation
        if abort:
            return RunResult(
                run_id=run_id,
                status=RunStatus.FAILED,
                error="Teammate(s) not found in registry",
            )

        if was_cancelled:
            await self._emit(
                EventType.TEAM_FINISHED,
                run_id,
                payload={
                    "team_run_id": run_id,
                    "status": "cancelled",
                },
            )
            return RunResult(
                run_id=run_id,
                status=RunStatus.CANCELLED,
            )

        # 5. If on_teammate_failure=abort_team and any failed
        failed = [name for name, s in contributions.items() if s.status in ("failed",)]
        if failed and plan.on_teammate_failure == "abort_team":
            await self._emit(
                EventType.TEAM_FAILED,
                run_id,
                payload={
                    "team_run_id": run_id,
                    "error_category": "execution",
                    "message": f"Teammates failed: {', '.join(failed)}",
                },
            )
            return RunResult(
                run_id=run_id,
                status=RunStatus.FAILED,
                error=f"Teammates failed: {', '.join(failed)}",
            )

        # 6. Run lead with contributions summary
        lead_result = await self._run_lead(
            plan,
            run_id,
            context,
            contributions,
        )

        lead_finished = lead_result.status == RunStatus.FINISHED
        status = RunStatus.FINISHED if lead_finished else lead_result.status

        lead_output = lead_result.output if lead_finished else None

        await self._emit(
            EventType.TEAM_FINISHED,
            run_id,
            payload={
                "team_run_id": run_id,
                "status": status.value,
                "lead_summary": lead_output,
            },
        )

        return RunResult(
            run_id=run_id,
            status=status,
            output=lead_output,
            error=lead_result.error,
        )

    async def _run_teammate(
        self,
        name: str,
        agent: Any,
        prompt: str,
        context: RunContext,
        failure_policy: str,
        contributions: dict[str, ContributionSummary],
        run_id: str,
        cancel_scope: anyio.CancelScope | None = None,
        limiter: anyio.CapacityLimiter | None = None,
    ) -> None:
        """Run a single teammate, capturing result or failure."""
        try:
            if limiter is None:
                output = await self._invoke_agent(
                    agent_id=name,
                    agent=agent,
                    input_data=prompt,
                    context=context,
                    round_name="teammate",
                )
            else:
                async with limiter:
                    output = await self._invoke_agent(
                        agent_id=name,
                        agent=agent,
                        input_data=prompt,
                        context=context,
                        round_name="teammate",
                    )

            contributions[name] = ContributionSummary(
                teammate=name,
                status="finished",
                output=output,
            )
            await self._emit(
                EventType.TEAMMATE_FINISHED,
                run_id,
                payload={
                    "teammate": name,
                    "status": "finished",
                    "sub_run_id": f"{run_id}/{name}",
                },
            )
        except anyio.get_cancelled_exc_class():
            contributions[name] = ContributionSummary(
                teammate=name,
                status="cancelled",
            )
            await self._emit(
                EventType.TEAMMATE_FINISHED,
                run_id,
                payload={
                    "teammate": name,
                    "status": "cancelled",
                    "sub_run_id": f"{run_id}/{name}",
                },
            )
            raise
        except TeamAgentTimeout:
            contributions[name] = ContributionSummary(
                teammate=name,
                status="failed",
                error_category="timeout",
                error_message="agent_timeout",
            )
            await self._emit(
                EventType.TEAMMATE_FAILED,
                run_id,
                payload={
                    "teammate": name,
                    "sub_run_id": f"{run_id}/{name}",
                    "error_category": "timeout",
                    "message": "agent_timeout",
                },
            )
            if failure_policy == "abort_team" and cancel_scope is not None:
                cancel_scope.cancel()
        except Exception as exc:
            error_category = "execution"
            contributions[name] = ContributionSummary(
                teammate=name,
                status="failed",
                error_category=error_category,
                error_message=str(exc),
            )
            await self._emit(
                EventType.TEAMMATE_FAILED,
                run_id,
                payload={
                    "teammate": name,
                    "sub_run_id": f"{run_id}/{name}",
                    "error_category": error_category,
                    "message": str(exc),
                },
            )

            if failure_policy == "abort_team" and cancel_scope is not None:
                cancel_scope.cancel()

    async def _run_lead(
        self,
        plan: TeamPlan,
        run_id: str,
        context: RunContext,
        contributions: dict[str, ContributionSummary],
    ) -> RunResult:
        """Run the lead agent with consolidated contributions."""
        lead_agent = self._registry.get(plan.lead_agent)
        if lead_agent is None:
            return RunResult(
                run_id=run_id,
                status=RunStatus.FAILED,
                error=f"Lead agent '{plan.lead_agent}' not found in registry",
            )

        lead_prompt = plan.lead_prompt or "Consolidate the team findings."

        try:
            output = await self._invoke_agent(
                agent_id=plan.lead_agent,
                agent=lead_agent,
                input_data={"_contributions": contributions, "_prompt": lead_prompt},
                context=context,
                round_name="lead",
            )

            return RunResult(
                run_id=run_id,
                status=RunStatus.FINISHED,
                output=output,
            )
        except TeamAgentTimeout:
            return RunResult(
                run_id=run_id,
                status=RunStatus.TIMED_OUT,
                error="agent_timeout",
            )
        except Exception as exc:
            error = str(exc)
            return RunResult(
                run_id=run_id,
                status=RunStatus.FAILED,
                error=error,
            )

    def _validate_plan(self, plan: TeamPlan) -> None:
        """Validate TeamPlan before execution."""
        if plan.lead_agent not in self._registry:
            msg = (
                f"Lead agent '{plan.lead_agent}' not found in registry. "
                f"Available: {', '.join(self._registry.keys())}"
            )
            raise ValueError(msg)

        for teammate in plan.teammates:
            if teammate not in self._registry:
                msg = (
                    f"Teammate '{teammate}' not found in registry. "
                    f"Available: {', '.join(self._registry.keys())}"
                )
                raise ValueError(msg)

    async def _invoke_agent(
        self,
        *,
        agent_id: str,
        agent: Any,
        input_data: Any,
        context: RunContext,
        round_name: str,
    ) -> Any:
        """Invoke an agent with child context and optional timeout policy."""
        if self._timeout_policy is None:
            return await self._call_agent_with_context(agent, input_data, context)

        result = None
        timed_out = False

        async def emit_timeout_event(event_type: str, **payload: object) -> None:
            nonlocal timed_out
            if event_type == EventType.AGENT_TURN_TIMED_OUT.value:
                timed_out = True
            await self._emit_raw(
                event_type,
                context.run_id,
                correlation_id=context.correlation_id,
                payload=payload,
            )

        try:
            async with self._timeout_policy.scope_for_turn(
                agent_id=agent_id,
                round_name=round_name,
                emit=emit_timeout_event,
            ):
                result = await self._call_agent_with_context(agent, input_data, context)
        except TimeoutError as exc:
            raise TeamAgentTimeout("agent_timeout") from exc

        if timed_out:
            raise TeamAgentTimeout("agent_timeout")
        return result

    async def _call_agent_with_context(
        self,
        agent: Any,
        input_data: Any,
        context: RunContext,
    ) -> Any:
        """Call an agent while temporarily applying the provided RunContext."""
        previous_context = getattr(agent, "_run_context", None)
        has_context = hasattr(agent, "_run_context")
        if has_context:
            agent._run_context = context  # noqa: SLF001
        try:
            if hasattr(agent, "process"):
                return await agent.process(input_data)
            return await agent(input_data)
        finally:
            if has_context:
                agent._run_context = previous_context  # noqa: SLF001

    async def _emit(
        self,
        event_type: EventType,
        run_id: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Emit an execution event through the runner's event sink."""
        from miniautogen.core.contracts.events import ExecutionEvent

        event = ExecutionEvent(
            type=event_type.value,
            timestamp=datetime.now(timezone.utc),
            run_id=run_id,
            correlation_id=run_id,
            scope="team_runtime",
            payload=payload or {},
        )
        await self._runner.event_sink.publish(event)

    async def _emit_raw(
        self,
        event_type: str,
        run_id: str,
        *,
        correlation_id: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Emit a raw event type through the runner's event sink."""
        from miniautogen.core.contracts.events import ExecutionEvent

        event = ExecutionEvent(
            type=event_type,
            timestamp=datetime.now(timezone.utc),
            run_id=run_id,
            correlation_id=correlation_id,
            scope="team_runtime",
            payload=payload or {},
        )
        await self._runner.event_sink.publish(event)
