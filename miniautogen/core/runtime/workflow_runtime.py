"""WorkflowRuntime — coordination mode for structured, step-by-step workflows.

Supports sequential execution, fan-out parallelism, and optional synthesis.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import Any

import anyio

if sys.version_info >= (3, 11):
    pass  # BaseExceptionGroup is a builtin
else:
    from exceptiongroup import BaseExceptionGroup  # type: ignore[no-redef]

from miniautogen.core.contracts.coordination import (
    CoordinationKind,
    WorkflowPlan,
)
from miniautogen.core.contracts.enums import RunStatus
from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.run_result import RunResult
from miniautogen.core.events.types import EventType
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
    ) -> None:
        self._runner = runner
        self._registry = agent_registry or {}
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

        except BaseExceptionGroup as exc:
            error_messages = [str(e) for e in exc.exceptions]
            combined_error = "; ".join(error_messages)
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
        except Exception as exc:
            combined_error = str(exc)
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
        fan-out behaviour).
        """
        current_input = context.input_payload
        for step in plan.steps:
            if step.agent_id is not None:
                current_input = await self._invoke_agent(step.agent_id, current_input)
            # agent_id is None → pass-through: current_input unchanged
        return current_input

    async def _run_fan_out(
        self,
        context: RunContext,
        plan: WorkflowPlan,
    ) -> list[Any]:
        """Execute all steps in parallel, returning a list of outputs."""
        initial_input = context.input_payload
        results: list[Any] = [None] * len(plan.steps)

        async def _run_branch(index: int, step: Any) -> None:
            if step.agent_id is None:
                results[index] = initial_input
            else:
                results[index] = await self._invoke_agent(step.agent_id, initial_input)

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
