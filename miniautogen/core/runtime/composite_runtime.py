"""CompositeRuntime — composes coordination modes in sequence.

Enables the core MiniAutoGen innovation: workflow → deliberation → workflow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from miniautogen.core.contracts.coordination import (
    CoordinationKind,
    CoordinationPlan,
)
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.run_result import RunResult
from miniautogen.observability import get_logger

_SCOPE = "composite_runtime"


@dataclass
class CompositionStep:
    """A single step in a composite coordination sequence.

    Attributes:
        mode: The coordination runtime to execute.
        plan: The typed plan for this mode.
        label: Descriptive label for events and traceability.
        input_mapper: Optional function that transforms the previous RunResult
                      and current RunContext into a new RunContext for this step.
                      If None, ``RunContext.with_previous_result`` is used.
        output_mapper: Optional function that transforms this step's RunResult
                       before passing it onward. If None, the result passes as-is.
    """

    mode: Any  # CoordinationMode — uses Any to avoid generic variance issues
    plan: CoordinationPlan
    label: str = ""
    input_mapper: Callable[[RunResult, RunContext], RunContext] | None = None
    output_mapper: Callable[[RunResult], RunResult] | None = None


class CompositeRuntime:
    """Composes coordination modes in sequence.

    The composition is explicit: the caller defines the sequence of
    CompositionStep objects. No DSL, no automatic inference.
    """

    kind: CoordinationKind = CoordinationKind.WORKFLOW

    def __init__(self) -> None:
        self._logger = get_logger(__name__)

    async def run(
        self,
        agents: list[Any],
        context: RunContext,
        plan: list[CompositionStep],
    ) -> RunResult:
        """Execute steps in sequence, threading output from one mode to the next.

        For each step:
        1. Apply input_mapper if present (transforms context)
        2. Execute mode.run() with the step's plan
        3. Apply output_mapper if present (transforms result)
        4. If result is failed, stop immediately
        5. Inject result into context for the next step
        """
        logger = self._logger.bind(
            run_id=context.run_id,
            correlation_id=context.correlation_id,
            scope=_SCOPE,
        )

        if not plan:
            return RunResult(
                run_id=context.run_id,
                status="finished",
                output=context.input_payload,
            )

        result: RunResult | None = None
        current_context = context

        for i, step in enumerate(plan):
            step_label = step.label or f"step-{i}"
            logger.info("composition_step_started", step=step_label, index=i)

            # 1. Map input
            if step.input_mapper is not None and result is not None:
                current_context = step.input_mapper(result, current_context)
            elif result is not None:
                current_context = current_context.with_previous_result(result.output)

            # 2. Execute mode
            result = await step.mode.run(
                agents=agents,
                context=current_context,
                plan=step.plan,
            )

            # 3. Map output
            if step.output_mapper is not None:
                result = step.output_mapper(result)

            logger.info(
                "composition_step_finished",
                step=step_label,
                index=i,
                status=result.status,
            )

            # 4. Fail fast
            if result.status == "failed":
                logger.error(
                    "composition_failed",
                    step=step_label,
                    error=result.error,
                )
                return result

        return result  # type: ignore[return-value]
