"""WorkflowRuntime — coordination mode for structured, step-by-step workflows.

Supports sequential execution, fan-out parallelism, and optional synthesis.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import Any

import anyio

# TODO(review): simplify version guard (code-reviewer, 2026-03-16, Low)
if sys.version_info < (3, 11):
    from exceptiongroup import BaseExceptionGroup  # type: ignore[no-redef]

from miniautogen.core.contracts.coordination import (
    CoordinationKind,
    WorkflowPlan,
)
from miniautogen.core.contracts.enums import RunStatus, SupervisionStrategy
from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.run_result import RunResult
from miniautogen.core.events.types import EventType
from miniautogen.core.runtime.checkpoint_manager import CheckpointManager
from miniautogen.core.runtime.classifier import classify_error
from miniautogen.core.runtime.flow_supervisor import FlowSupervisor
from miniautogen.core.runtime.pipeline_runner import PipelineRunner
from miniautogen.observability import get_logger


class WorkflowRuntime:
    """Coordination mode that executes a WorkflowPlan.

    Manages sequential or parallel (fan-out) execution of steps, with
    optional synthesis at the end.
    """

    kind: CoordinationKind = CoordinationKind.WORKFLOW

    def __init__(
        self,
        runner: PipelineRunner,
        agent_registry: dict[str, Any] | None = None,
        checkpoint_manager: CheckpointManager | None = None,
    ) -> None:
        self._runner = runner
        self._registry = agent_registry or {}
        self._checkpoint_manager = checkpoint_manager
        self._logger = get_logger(__name__)

    async def run(
        self,
        agents: list[Any],
        context: RunContext,
        plan: WorkflowPlan,
    ) -> RunResult:
        """Execute a workflow plan and return a RunResult.

        Note: ``agents`` is part of the CoordinationMode protocol signature
        for composability.  Actual agent resolution uses the ``agent_registry``
        injected at construction time. The parameter is reserved for future
        override semantics.
        """
        run_id = context.run_id
        correlation_id = context.correlation_id
        logger = self._logger.bind(
            run_id=run_id,
            correlation_id=correlation_id,
            scope="workflow_runtime",
        )

        # --- Validate agent references ---
        validation_error = self._validate_plan(plan)
        if validation_error is not None:
            logger.error("workflow_validation_failed", error=validation_error)
            return RunResult(run_id=run_id, status=RunStatus.FAILED, error=validation_error)

        # --- Emit RUN_STARTED ---
        await self._emit(event_type=EventType.RUN_STARTED.value, run_id=run_id, correlation_id=correlation_id)
        logger.info("workflow_started", fan_out=plan.fan_out, steps=len(plan.steps))

        try:
            if plan.fan_out:
                outputs = await self._run_fan_out(context, plan)
            else:
                outputs = await self._run_sequential(context, plan)

            # --- Synthesis ---
            if plan.synthesis_agent is not None:
                logger.info("synthesis_started", agent=plan.synthesis_agent)
                final_output = await self._invoke_agent(
                    plan.synthesis_agent,
                    outputs,
                )
            else:
                final_output = outputs

        except BaseException as exc:
            if isinstance(exc, BaseExceptionGroup):
                error_messages = [str(e) for e in exc.exceptions]
                combined_error = "; ".join(error_messages)
            elif isinstance(exc, Exception):
                combined_error = str(exc)
            else:
                raise  # Let KeyboardInterrupt, SystemExit propagate
            try:
                await self._emit(
                    event_type=EventType.RUN_FAILED.value,
                    run_id=run_id,
                    correlation_id=correlation_id,
                    payload={"error": combined_error},
                )
            except Exception:
                logger.warning("failed_to_emit_error_event", original_error=combined_error)
            logger.error("workflow_failed", error=combined_error)
            return RunResult(run_id=run_id, status=RunStatus.FAILED, error=combined_error)

        # --- Emit RUN_FINISHED ---
        await self._emit(event_type=EventType.RUN_FINISHED.value, run_id=run_id, correlation_id=correlation_id)
        logger.info("workflow_finished")

        return RunResult(run_id=run_id, status=RunStatus.FINISHED, output=final_output)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_plan(self, plan: WorkflowPlan) -> str | None:
        """Return an error message if the plan references unknown agents."""
        for step in plan.steps:
            if step.agent_id is not None and step.agent_id not in self._registry:
                return f"Agent '{step.agent_id}' not found in registry"
        if plan.synthesis_agent is not None and plan.synthesis_agent not in self._registry:
            return f"Synthesis agent '{plan.synthesis_agent}' not found in registry"
        return None

    async def _run_sequential(
        self,
        context: RunContext,
        plan: WorkflowPlan,
    ) -> Any:
        """Execute steps one-by-one, chaining outputs.

        Steps with ``agent_id=None`` act as pass-through (consistent with
        fan-out behaviour).  When a step has supervision configured (or the
        plan has ``default_supervision``), failures are handled by the
        FlowSupervisor which may restart, stop, or escalate.

        When a CheckpointManager is available:
        - Before execution, loads existing checkpoint to skip completed steps.
        - After each successful step, saves checkpoint with current step_index.
        - On RESUME decision, saves checkpoint before retrying the failed step.
        """
        supervisor = FlowSupervisor(event_sink=self._runner.event_sink)
        current_input = context.input_payload
        run_id = context.run_id
        start_index = 0

        # Load existing checkpoint to skip already-completed steps
        if self._checkpoint_manager is not None:
            checkpoint = await self._checkpoint_manager.get_last_checkpoint(
                run_id,
            )
            if checkpoint is not None:
                saved_state, saved_step_index = checkpoint
                start_index = saved_step_index
                current_input = saved_state

        for step_idx, step in enumerate(plan.steps):
            if step_idx < start_index:
                # Skip already-completed steps (restored from checkpoint)
                continue

            if step.agent_id is None:
                # pass-through: current_input unchanged
                # Still save checkpoint for pass-through steps
                if self._checkpoint_manager is not None:
                    await self._checkpoint_manager.atomic_transition(
                        run_id,
                        new_state=current_input,
                        events=[],
                        step_index=step_idx + 1,
                    )
                continue

            restart_count = 0
            error_categories: list[str] = []

            while True:
                try:
                    current_input = await self._invoke_agent(
                        step.agent_id, current_input,
                    )
                    # Save checkpoint after successful step
                    if self._checkpoint_manager is not None:
                        await self._checkpoint_manager.atomic_transition(
                            run_id,
                            new_state=current_input,
                            events=[],
                            step_index=step_idx + 1,
                        )
                    # Emit retry-succeeded if we recovered from failures
                    if restart_count > 0:
                        await supervisor.emit_retry_succeeded(
                            step_id=step.component_name,
                            total_attempts=restart_count + 1,
                            error_categories_encountered=error_categories,
                        )
                    break
                except BaseException as exc:
                    if not isinstance(exc, Exception):
                        raise

                    supervision = (
                        step.supervision or plan.default_supervision
                    )
                    # No supervision configured -> fail-fast
                    if supervision is None:
                        raise

                    category = classify_error(exc)
                    error_categories.append(category.value)
                    decision = await supervisor.handle_step_failure(
                        step_id=step.component_name,
                        error=exc,
                        error_category=category,
                        supervision=supervision,
                        restart_count=restart_count,
                    )

                    if decision.action == SupervisionStrategy.RESUME:
                        # Save checkpoint before retrying
                        if self._checkpoint_manager is not None:
                            await self._checkpoint_manager.atomic_transition(
                                run_id,
                                new_state=current_input,
                                events=[],
                                step_index=step_idx,
                            )
                        restart_count += 1
                        continue

                    if decision.action == SupervisionStrategy.RESTART:
                        restart_count += 1
                        continue

                    # STOP or ESCALATE -> re-raise so run() handles it
                    raise

        return current_input

    async def _run_fan_out(
        self,
        context: RunContext,
        plan: WorkflowPlan,
    ) -> list[Any]:
        """Execute all steps in parallel, returning a list of outputs.

        Each branch has independent supervision handling.  When supervision is
        configured the branch retries according to the supervisor decision.
        Branches that exhaust their retry budget raise so that ``anyio`` can
        propagate the ``ExceptionGroup`` to the caller.
        """
        supervisor = FlowSupervisor(event_sink=self._runner.event_sink)
        initial_input = context.input_payload
        results: list[Any] = [None] * len(plan.steps)

        async def _run_branch(index: int, step: Any) -> None:
            if step.agent_id is None:
                results[index] = initial_input
                return

            supervision = step.supervision or plan.default_supervision

            # No supervision → original fail-fast behaviour
            if supervision is None:
                results[index] = await self._invoke_agent(step.agent_id, initial_input)
                return

            restart_count = 0
            error_categories: list[str] = []

            while True:
                try:
                    results[index] = await self._invoke_agent(step.agent_id, initial_input)
                    if restart_count > 0:
                        await supervisor.emit_retry_succeeded(
                            step_id=step.component_name,
                            total_attempts=restart_count + 1,
                            error_categories_encountered=error_categories,
                        )
                    return
                except BaseException as exc:
                    if not isinstance(exc, Exception):
                        raise

                    category = classify_error(exc)
                    error_categories.append(category.value)
                    decision = await supervisor.handle_step_failure(
                        step_id=step.component_name,
                        error=exc,
                        error_category=category,
                        supervision=supervision,
                        restart_count=restart_count,
                    )

                    if decision.action == SupervisionStrategy.RESTART:
                        restart_count += 1
                        continue

                    # STOP / ESCALATE → let the exception propagate
                    raise

        async with anyio.create_task_group() as tg:
            for i, step in enumerate(plan.steps):
                tg.start_soon(_run_branch, i, step)

        return results

    async def _invoke_agent(self, agent_id: str, input_data: Any) -> Any:
        """Call an agent from the registry. Supports both process() and __call__."""
        agent = self._registry[agent_id]
        if hasattr(agent, "process"):
            return await agent.process(input_data)
        return await agent(input_data)

    async def _emit(
        self,
        *,
        event_type: str,
        run_id: str,
        correlation_id: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Emit an event through the runner's event_sink."""
        event = ExecutionEvent(
            type=event_type,
            timestamp=datetime.now(timezone.utc),
            run_id=run_id,
            correlation_id=correlation_id,
            scope="workflow_runtime",
            payload=payload or {},
        )
        await self._runner.event_sink.publish(event)
