"""TeamRuntime — peer-to-peer agent team coordination mode.

Each team has a lead and N teammates running concurrently via
anyio.create_task_group. The lead consolidates results after all
teammates finish.

Spec 016: team task list support (shared kanban board).
Spec 017: team mailbox + plan approval gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import monotonic
from typing import TYPE_CHECKING, Any

import anyio

from miniautogen.core.contracts.coordination import (
    ContributionSummary,
    CoordinationKind,
    MailboxConfig,
    PlanApprovalConfig,
    TeamPlan,
)
from miniautogen.core.contracts.enums import RunStatus
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.run_result import RunResult
from miniautogen.core.contracts.team_task import (
    TaskEntry,
    TaskFilter,
    TaskStatus,
)
from miniautogen.core.events.types import EventType
from miniautogen.observability import get_logger

if TYPE_CHECKING:
    from miniautogen.core.runtime.pipeline_runner import PipelineRunner


@dataclass
class IdleAggregator:
    agents: set[str] = field(default_factory=set)
    _lock: anyio.Lock = field(default_factory=anyio.Lock)

    async def mark_idle(self, agent: str) -> None:
        async with self._lock:
            self.agents.add(agent)

    async def mark_busy(self, agent: str) -> None:
        async with self._lock:
            self.agents.discard(agent)

    async def all_idle(self, total: int) -> bool:
        async with self._lock:
            return len(self.agents) >= total

    async def is_idle(self, agent: str) -> bool:
        async with self._lock:
            return agent in self.agents


class TeamAgentTimeout(Exception):
    """Raised internally when a team agent turn times out."""


class TeamRuntime:
    """Coordination mode for agent teams with a lead and concurrent teammates.

    Implements the CoordinationMode[TeamPlan] protocol.
    Supports Spec 015 (static fan-out) and Spec 016 (dynamic task list).
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
        self._plan: TeamPlan | None = None

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
        self._plan = plan
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

        # 1b. If task list enabled, use the task-list-driven flow
        if plan.task_list and plan.task_list.enabled:
            return await self._run_with_task_list(agents, context, plan)

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

    async def _parse_mailbox_config(self, plan: TeamPlan) -> MailboxConfig | None:
        raw = plan.mailbox
        if raw is None:
            return None
        if isinstance(raw, MailboxConfig):
            return raw if raw.enabled else None
        if isinstance(raw, dict):
            cfg = MailboxConfig(**raw)
            return cfg if cfg.enabled else None
        return None

    async def _parse_plan_approval_config(self, plan: TeamPlan) -> PlanApprovalConfig | None:
        raw = plan.plan_approval
        if raw is None:
            return None
        if isinstance(raw, PlanApprovalConfig):
            return raw
        if isinstance(raw, dict):
            return PlanApprovalConfig(**raw)
        return None

    async def _run_with_task_list(
        self,
        agents: list[Any],
        context: RunContext,
        plan: TeamPlan,
    ) -> RunResult:
        """Task-list-driven team execution: lead populates board, teammates drain it."""
        run_id = context.run_id
        task_list_config = plan.task_list
        assert task_list_config is not None  # checked by caller

        mailbox_cfg = await self._parse_mailbox_config(plan)
        plan_approval_cfg = await self._parse_plan_approval_config(plan)

        # Create store
        from miniautogen.core.runtime.team_task_list import InMemoryTaskListStore

        store = InMemoryTaskListStore(
            team_run_id=run_id,
            event_sink=self._runner.event_sink,
        )

        # Create mailbox store if enabled
        mailbox = None
        approvals = None
        idle_aggregator = IdleAggregator()
        mail_agents = list(plan.teammates)

        if mailbox_cfg is not None:
            from miniautogen.core.runtime.team_mailbox import InMemoryMailboxStore
            from miniautogen.core.runtime.team_plan_approval import (
                PlanApprovalRegistry,
            )

            mailbox = InMemoryMailboxStore(
                agents=[plan.lead_agent] + plan.teammates,
                buffer_size=mailbox_cfg.buffer_size,
                event_sink=self._runner.event_sink,
                team_run_id=run_id,
            )
            approvals = PlanApprovalRegistry(
                event_sink=self._runner.event_sink,
                team_run_id=run_id,
            )

        # Populate initial tasks
        for spec in task_list_config.initial_tasks:
            entry = TaskEntry(
                title=spec.title,
                description=spec.description,
                assigned_to=spec.assigned_to,
                labels=list(spec.labels),
                depends_on=list(spec.depends_on),
                created_by=plan.lead_agent,
            )
            await store.add(entry, actor=plan.lead_agent)

        # Emit TEAM_STARTED
        await self._emit(
            EventType.TEAM_STARTED,
            run_id,
            payload={
                "lead": plan.lead_agent,
                "teammates": plan.teammates,
                "team_run_id": run_id,
                "task_list_enabled": True,
                "mailbox_enabled": mailbox_cfg is not None,
            },
        )

        was_cancelled = False

        # Run lead first
        if plan.lead_runs_first:
            lead_agent = self._registry.get(plan.lead_agent)
            if lead_agent is not None:
                self._inject_task_tools(lead_agent, store, plan.lead_agent)
                if mailbox is not None and approvals is not None:
                    self._inject_mailbox_tools(
                        lead_agent, plan.lead_agent, True, mailbox, approvals, run_id, plan
                    )
                await self._run_lead_with_task_list(
                    plan, run_id, context, {}, store,
                )

        # Run teammates with drain loop
        contributions: dict[str, ContributionSummary] = {}
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
                        self._logger.error(
                            "Teammate '%s' not found in registry", teammate_name
                        )
                        continue

                    self._inject_task_tools(agent, store, teammate_name)
                    if mailbox is not None and approvals is not None:
                        self._inject_mailbox_tools(
                            agent, teammate_name, False, mailbox, approvals, run_id, plan
                        )

                    child_ctx = context.model_copy(
                        update={"parent_run_id": run_id},
                    )

                    await self._emit(
                        EventType.TEAMMATE_SPAWNED,
                        run_id,
                        payload={
                            "teammate": teammate_name,
                            "sub_run_id": f"{run_id}/{teammate_name}",
                            "parent_run_id": run_id,
                            "loop_mode": "drain_board",
                            "mailbox_enabled": mailbox is not None,
                        },
                    )

                    if mailbox is not None:
                        tg.start_soon(
                            self._run_teammate_drain_loop_with_mailbox,
                            teammate_name,
                            agent,
                            child_ctx,
                            plan.on_teammate_failure,
                            contributions,
                            run_id,
                            tg.cancel_scope,
                            limiter,
                            store,
                            mailbox_cfg.idle_threshold_seconds if mailbox_cfg else 5.0,
                            task_list_config.poll_interval_ms,
                            mailbox,
                            approvals,
                            idle_aggregator,
                            mail_agents,
                        )
                    else:
                        tg.start_soon(
                            self._run_teammate_drain_loop,
                            teammate_name,
                            agent,
                            child_ctx,
                            plan.on_teammate_failure,
                            contributions,
                            run_id,
                            tg.cancel_scope,
                            limiter,
                            store,
                            task_list_config.idle_threshold_seconds,
                            task_list_config.poll_interval_ms,
                        )

        except anyio.get_cancelled_exc_class():
            was_cancelled = True
        finally:
            if mailbox is not None:
                try:
                    await mailbox.aclose()
                except Exception:
                    self._logger.warning("mailbox.aclose failed", exc_info=True)

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

        # Run lead after teammates (if not already run first)
        if not plan.lead_runs_first:
            lead_agent = self._registry.get(plan.lead_agent)
            if lead_agent is not None:
                self._inject_task_tools(lead_agent, store, plan.lead_agent)
                await self._run_lead_with_task_list(
                    plan, run_id, context, contributions, store,
                )

        await self._emit(
            EventType.TEAM_FINISHED,
            run_id,
            payload={
                "team_run_id": run_id,
                "status": RunStatus.FINISHED.value,
            },
        )

        return RunResult(
            run_id=run_id,
            status=RunStatus.FINISHED,
        )

    def _inject_task_tools(self, agent: Any, store: Any, agent_name: str) -> None:
        """Compose team task tools into an agent's tool registry."""
        from miniautogen.core.runtime.composite_tool_registry import (
            CompositeToolRegistry,
        )
        from miniautogen.core.runtime.team_task_tools import build_team_task_tools
        from miniautogen.core.runtime.tool_registry import InMemoryToolRegistry

        team_registry = InMemoryToolRegistry()
        for definition, handler in build_team_task_tools(store, agent_name):
            team_registry.register(definition, handler)

        existing = getattr(agent, "tool_registry", None)
        if existing is not None:
            if isinstance(existing, CompositeToolRegistry):
                existing._registries = list(existing._registries) + [team_registry]
            else:
                agent.tool_registry = CompositeToolRegistry([existing, team_registry])
        else:
            agent.tool_registry = team_registry

    def _inject_mailbox_tools(
        self,
        agent: Any,
        agent_name: str,
        is_lead: bool,
        mailbox: Any,
        approvals: Any,
        run_id: str,
        plan: TeamPlan,
    ) -> None:
        from miniautogen.core.runtime.approval_gated_tool_registry import (
            ApprovalGatedToolRegistry,
        )
        from miniautogen.core.runtime.builtin_team_tools import build_team_tools
        from miniautogen.core.runtime.composite_tool_registry import (
            CompositeToolRegistry,
        )
        from miniautogen.core.runtime.tool_registry import InMemoryToolRegistry

        team_registry = InMemoryToolRegistry()
        for definition, handler in build_team_tools(
            agent_id=agent_name,
            is_lead=is_lead,
            mailbox=mailbox,
            approvals=approvals,
            event_sink=self._runner.event_sink,
            team_run_id=run_id,
            lead_agent=plan.lead_agent,
        ):
            team_registry.register(definition, handler)

        plan_approval_cfg = None
        try:
            raw = plan.plan_approval
            if isinstance(raw, PlanApprovalConfig):
                plan_approval_cfg = raw
            elif isinstance(raw, dict):
                plan_approval_cfg = PlanApprovalConfig(**raw)
        except Exception:
            pass

        if plan_approval_cfg is not None and plan_approval_cfg.required_for and not is_lead:
            from miniautogen.core.runtime.builtin_team_tools import (
                _make_request_plan_approval_handler,
            )

            approval_handler = _make_request_plan_approval_handler(
                mailbox, approvals, agent_name, plan.lead_agent,
                self._runner.event_sink, run_id,
            )

            async def _approval_wrapper(plan_summary: str | dict) -> str:
                result = await approval_handler(
                    {"plan": plan_summary, "timeout_seconds": 60.0}
                )
                if result.success:
                    return result.output.get("decision", "denied")
                return "denied"

            wrapped = ApprovalGatedToolRegistry(
                inner=team_registry,
                approval_tool=_approval_wrapper,
                required_for=set(plan_approval_cfg.required_for),
                agent_id=agent_name,
                event_sink=self._runner.event_sink,
            )
            team_registry = wrapped  # type: ignore[assignment]

        existing = getattr(agent, "tool_registry", None)
        if existing is not None:
            if isinstance(existing, CompositeToolRegistry):
                existing._registries = list(existing._registries) + [team_registry]
            else:
                agent.tool_registry = CompositeToolRegistry([existing, team_registry])
        else:
            agent.tool_registry = team_registry

    async def _run_teammate_drain_loop(
        self,
        name: str,
        agent: Any,
        context: RunContext,
        failure_policy: str,
        contributions: dict[str, ContributionSummary],
        run_id: str,
        cancel_scope: anyio.CancelScope | None = None,
        limiter: anyio.CapacityLimiter | None = None,
        store: Any | None = None,
        idle_threshold: float = 5.0,
        poll_interval_ms: int = 200,
    ) -> None:
        """Run a teammate in drain-board loop: claim -> execute -> complete/fail."""
        poll_seconds = poll_interval_ms / 1000.0
        idle_start: float | None = None

        while True:
            try:
                entry = await store.claim(None, teammate=name, labels=None)
            except anyio.get_cancelled_exc_class():
                raise

            if entry is not None:
                idle_start = None
                try:
                    if limiter is None:
                        output = await self._invoke_agent(
                            agent_id=name,
                            agent=agent,
                            input_data=self._build_task_prompt(entry),
                            context=context,
                            round_name="teammate",
                        )
                    else:
                        async with limiter:
                            output = await self._invoke_agent(
                                agent_id=name,
                                agent=agent,
                                input_data=self._build_task_prompt(entry),
                                context=context,
                                round_name="teammate",
                            )

                    await store.update_status(
                        entry.id,
                        TaskStatus.COMPLETED,
                        summary=str(output),
                        actor=name,
                    )
                    await self._emit(
                        EventType.TEAMMATE_FINISHED,
                        run_id,
                        payload={
                            "teammate": name,
                            "status": "finished",
                            "task_id": entry.id,
                            "sub_run_id": f"{run_id}/{name}",
                        },
                    )

                except anyio.get_cancelled_exc_class():
                    with anyio.CancelScope(shield=True):
                        await store.release(entry.id, actor=name)
                    raise
                except Exception as exc:
                    await store.update_status(
                        entry.id,
                        TaskStatus.FAILED,
                        summary=str(exc),
                        actor=name,
                    )
                    await self._emit(
                        EventType.TEAMMATE_FAILED,
                        run_id,
                        payload={
                            "teammate": name,
                            "task_id": entry.id,
                            "status": "failed",
                            "error": str(exc),
                        },
                    )
                    if failure_policy == "abort_team" and cancel_scope is not None:
                        cancel_scope.cancel()
                        return
            else:
                in_progress = await store.list_tasks(
                    filter=TaskFilter(status=TaskStatus.IN_PROGRESS),
                )
                pending = await store.list_tasks(
                    filter=TaskFilter(status=TaskStatus.PENDING),
                )

                if not pending and not in_progress:
                    if idle_start is None:
                        idle_start = monotonic()
                    elif monotonic() - idle_start >= idle_threshold:
                        break
                else:
                    idle_start = None

                await anyio.sleep(poll_seconds)

        contributions[name] = ContributionSummary(
            teammate=name,
            status="finished",
            output="drain_board_completed",
        )

    async def _run_teammate_drain_loop_with_mailbox(
        self,
        name: str,
        agent: Any,
        context: RunContext,
        failure_policy: str,
        contributions: dict[str, ContributionSummary],
        run_id: str,
        cancel_scope: anyio.CancelScope | None = None,
        limiter: anyio.CapacityLimiter | None = None,
        store: Any | None = None,
        idle_threshold: float = 5.0,
        poll_interval_ms: int = 200,
        mailbox: Any | None = None,
        approvals: Any | None = None,
        idle_aggregator: IdleAggregator | None = None,
        mail_agents: list[str] | None = None,
    ) -> None:
        """Run a teammate in drain-board loop WITH mailbox branch.

        Loop:
          1. Try to receive a message from inbox (with idle_threshold timeout)
          2. If message: process/resolve and continue
          3. If no message: try to claim a task
          4. If no task: mark idle; if all idle, break
        """
        poll_seconds = poll_interval_ms / 1000.0

        while True:
            msg = None
            try:
                if mailbox is not None:
                    with anyio.move_on_after(idle_threshold) as scope:
                        stream = mailbox.receive_stream(name)
                        msg = await anext(stream, None)
                        if msg is not None and idle_aggregator is not None:
                            await idle_aggregator.mark_busy(name)

                if msg is not None:
                    if approvals is not None and msg.kind in {"plan_approval_granted", "plan_approval_denied"}:
                        decision = "granted" if msg.kind.endswith("granted") else "denied"
                        if msg.correlation_id:
                            await approvals.resolve(msg.correlation_id, decision)
                        continue
                    output = await self._invoke_agent(
                        agent_id=name, agent=agent,
                        input_data=msg.content,
                        context=context, round_name="teammate",
                    )
                    continue
            except anyio.get_cancelled_exc_class():
                raise
            except Exception:
                self._logger.warning("mailbox receive failed", exc_info=True)

            try:
                entry = await store.claim(None, teammate=name, labels=None)
            except anyio.get_cancelled_exc_class():
                raise

            if entry is not None:
                if idle_aggregator is not None:
                    await idle_aggregator.mark_busy(name)
                try:
                    if limiter is None:
                        output = await self._invoke_agent(
                            agent_id=name,
                            agent=agent,
                            input_data=self._build_task_prompt(entry),
                            context=context,
                            round_name="teammate",
                        )
                    else:
                        async with limiter:
                            output = await self._invoke_agent(
                                agent_id=name,
                                agent=agent,
                                input_data=self._build_task_prompt(entry),
                                context=context,
                                round_name="teammate",
                            )

                    await store.update_status(
                        entry.id,
                        TaskStatus.COMPLETED,
                        summary=str(output),
                        actor=name,
                    )
                    await self._emit(
                        EventType.TEAMMATE_FINISHED,
                        run_id,
                        payload={
                            "teammate": name,
                            "status": "finished",
                            "task_id": entry.id,
                            "sub_run_id": f"{run_id}/{name}",
                        },
                    )

                except anyio.get_cancelled_exc_class():
                    with anyio.CancelScope(shield=True):
                        await store.release(entry.id, actor=name)
                    raise
                except Exception as exc:
                    await store.update_status(
                        entry.id,
                        TaskStatus.FAILED,
                        summary=str(exc),
                        actor=name,
                    )
                    await self._emit(
                        EventType.TEAMMATE_FAILED,
                        run_id,
                        payload={
                            "teammate": name,
                            "task_id": entry.id,
                            "status": "failed",
                            "error": str(exc),
                        },
                    )
                    if failure_policy == "abort_team" and cancel_scope is not None:
                        cancel_scope.cancel()
                        return
            else:
                in_progress = await store.list_tasks(
                    filter=TaskFilter(status=TaskStatus.IN_PROGRESS),
                )
                pending = await store.list_tasks(
                    filter=TaskFilter(status=TaskStatus.PENDING),
                )

                pending_count = 0
                if mailbox is not None:
                    try:
                        pending_count = await mailbox.pending_count(name)
                    except Exception:
                        pass

                if not pending and not in_progress and pending_count == 0:
                    if idle_aggregator is not None:
                        await idle_aggregator.mark_idle(name)

                    mail_agents_list = mail_agents or [name]
                    if idle_aggregator is not None and await idle_aggregator.all_idle(
                        len(mail_agents_list),
                    ):
                        await self._emit(
                            EventType.TEAMMATE_IDLE,
                            run_id,
                            payload={
                                "teammate": name,
                                "all_idle": True,
                                "team_run_id": run_id,
                            },
                        )
                        break
                    else:
                        await self._emit(
                            EventType.TEAMMATE_IDLE,
                            run_id,
                            payload={
                                "teammate": name,
                                "all_idle": False,
                                "team_run_id": run_id,
                            },
                        )
                        await anyio.sleep(poll_seconds)
                else:
                    if idle_aggregator is not None:
                        await idle_aggregator.mark_busy(name)
                    await anyio.sleep(poll_seconds)

        contributions[name] = ContributionSummary(
            teammate=name,
            status="finished",
            output="drain_board_completed",
        )

    def _build_task_prompt(self, entry: TaskEntry) -> str:
        prompt = f"Task: {entry.title}"
        if entry.description:
            prompt += f"\n\nDescription: {entry.description}"
        prompt += (
            "\n\nYou have access to task tools (task_list, task_claim, "
            "task_complete, task_fail, task_add, task_view). "
            "Execute this task and then use task_complete to mark it done."
        )
        return prompt

    async def _run_lead_with_task_list(
        self,
        plan: TeamPlan,
        run_id: str,
        context: RunContext,
        contributions: dict[str, ContributionSummary],
        store: Any,
    ) -> None:
        """Run the lead agent with task list tools available."""
        lead_agent = self._registry.get(plan.lead_agent)
        if lead_agent is None:
            return

        lead_prompt = plan.lead_prompt or (
            "You are the team lead. Use task_add to create tasks for your team. "
            "Use task_list to check progress."
        )

        try:
            output = await self._invoke_agent(
                agent_id=plan.lead_agent,
                agent=lead_agent,
                input_data={"_contributions": contributions, "_prompt": lead_prompt},
                context=context,
                round_name="lead",
            )
            self._logger.info(
                "lead_finished_with_task_list",
                run_id=run_id,
                output=output,
            )
        except Exception as exc:
            self._logger.error(
                "lead_failed",
                run_id=run_id,
                error=str(exc),
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
