"""AgenticLoopRuntime — coordination mode for agentic loop conversations.

Implements a router-driven conversation loop where a router agent selects
which participant speaks next, until termination, stagnation, or max turns.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import anyio

from miniautogen.core.contracts.agentic_loop import (
    AgenticLoopState,
    RouterDecision,
)
from miniautogen.core.contracts.conversation import Conversation
from miniautogen.core.contracts.coordination import (
    AgenticLoopPlan,
    CoordinationKind,
)
from miniautogen.core.contracts.enums import (
    LoopStopReason,
    RunStatus,
    SupervisionStrategy,
)
from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.contracts.message import Message
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.run_result import RunResult
from miniautogen.core.events.types import EventType
from miniautogen.core.runtime.agentic_loop import detect_stagnation, should_stop_loop
from miniautogen.core.runtime.classifier import classify_error
from miniautogen.core.runtime.flow_supervisor import FlowSupervisor
from miniautogen.core.runtime.pipeline_runner import PipelineRunner
from miniautogen.observability import get_logger

_SCOPE = "agentic_loop_runtime"


class AgenticLoopRuntime:
    """Coordination mode that executes an AgenticLoopPlan.

    Manages a router-driven conversation loop where a router agent decides
    which participant speaks next. The loop runs until the router terminates,
    stagnation is detected, or max turns is reached.
    """

    kind: CoordinationKind = CoordinationKind.AGENTIC_LOOP

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
        plan: AgenticLoopPlan,
    ) -> RunResult:
        """Execute an agentic loop plan and return a RunResult.

        Note: ``agents`` is part of the CoordinationMode protocol signature
        for composability. Actual agent resolution uses the ``agent_registry``
        injected at construction time.
        """
        run_id = context.run_id
        correlation_id = context.correlation_id
        logger = self._logger.bind(
            run_id=run_id,
            correlation_id=correlation_id,
            scope=_SCOPE,
        )

        # --- Validate plan ---
        validation_error = self._validate_plan(plan)
        if validation_error is not None:
            logger.error("agentic_loop_validation_failed", error=validation_error)
            return RunResult(run_id=run_id, status=RunStatus.FAILED, error=validation_error)

        # --- Emit AGENTIC_LOOP_STARTED ---
        await self._emit(
            event_type=EventType.AGENTIC_LOOP_STARTED.value,
            run_id=run_id,
            correlation_id=correlation_id,
            payload={"router": plan.router_agent, "participants": plan.participants},
        )
        logger.info(
            "agentic_loop_started",
            router=plan.router_agent,
            participants=plan.participants,
        )

        # --- Initialize conversation ---
        conversation = Conversation(id=run_id)
        if plan.initial_message is not None:
            conversation = conversation.add_message(
                Message(sender_id="system", content=plan.initial_message)
            )

        supervisor = FlowSupervisor(event_sink=self._runner.event_sink)
        routing_history: list[RouterDecision] = []
        state = AgenticLoopState()
        stop_reason: str = LoopStopReason.MAX_TURNS
        router_agent = self._registry[plan.router_agent]

        try:
            with anyio.fail_after(plan.policy.timeout_seconds):
                for _turn in range(plan.policy.max_turns):
                    # Check should_stop_loop
                    should_stop, reason = should_stop_loop(state, plan.policy)
                    if should_stop:
                        stop_reason = reason or LoopStopReason.MAX_TURNS
                        break

                    # Call router — NOT supervised (routing failures = PERMANENT)
                    history_for_router = [
                        {"sender": m.sender_id, "content": m.content}
                        for m in conversation.messages
                    ]
                    decision: RouterDecision = await router_agent.route(
                        history_for_router
                    )
                    routing_history.append(decision)

                    # Emit ROUTER_DECISION
                    await self._emit(
                        event_type=EventType.ROUTER_DECISION.value,
                        run_id=run_id,
                        correlation_id=correlation_id,
                        payload={
                            "next_agent": decision.next_agent,
                            "terminate": decision.terminate,
                        },
                    )

                    # Check termination
                    if decision.terminate:
                        stop_reason = LoopStopReason.ROUTER_TERMINATED
                        break

                    # Check stagnation
                    if detect_stagnation(
                        routing_history, plan.policy.stagnation_window
                    ):
                        await self._emit(
                            event_type=EventType.STAGNATION_DETECTED.value,
                            run_id=run_id,
                            correlation_id=correlation_id,
                        )
                        stop_reason = LoopStopReason.STAGNATION
                        break

                    # Validate and get selected agent
                    agent_id = decision.next_agent
                    if agent_id not in plan.participants:
                        logger.error(
                            "router_selected_invalid_participant",
                            selected=agent_id,
                            valid=plan.participants,
                        )
                        return RunResult(
                            run_id=run_id,
                            status=RunStatus.FAILED,
                            error=(
                                f"Router selected agent '{agent_id}' "
                                f"which is not a declared participant. "
                                f"Valid participants: {plan.participants}"
                            ),
                        )
                    agent = self._registry[agent_id]
                    last_message = (
                        conversation.messages[-1].content
                        if conversation.messages
                        else ""
                    )

                    # --- Supervised agent.reply() call ---
                    step_id = f"reply:{agent_id}:turn-{state.turn_count}"
                    restart_count = 0
                    error_categories: list[str] = []

                    while True:
                        try:
                            reply = await agent.reply(
                                last_message,
                                {"run_id": run_id, "turn": state.turn_count},
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
                                raise

                            category = classify_error(exc)
                            error_categories.append(category.value)
                            sv_decision = await supervisor.handle_step_failure(
                                step_id=step_id,
                                error=exc,
                                error_category=category,
                                supervision=supervision,
                                restart_count=restart_count,
                            )

                            if sv_decision.action == SupervisionStrategy.RESTART:
                                restart_count += 1
                                continue

                            # STOP or ESCALATE -> re-raise
                            raise

                    # Append to conversation history
                    conversation = conversation.add_message(
                        Message(sender_id=agent_id, content=reply)
                    )

                    # Emit AGENT_REPLIED
                    await self._emit(
                        event_type=EventType.AGENT_REPLIED.value,
                        run_id=run_id,
                        correlation_id=correlation_id,
                        payload={"agent": agent_id, "reply_length": len(reply)},
                    )

                    # Update state
                    state = AgenticLoopState(
                        active_agent=agent_id,
                        turn_count=state.turn_count + 1,
                        accepted_output=reply,
                    )

        except TimeoutError:
            logger.warning(
                "agentic_loop_timed_out",
                timeout=plan.policy.timeout_seconds,
            )
            stop_reason = LoopStopReason.TIMEOUT
            try:
                await self._emit(
                    event_type=EventType.RUN_TIMED_OUT.value,
                    run_id=run_id,
                    correlation_id=correlation_id,
                    payload={
                        "timeout_seconds": plan.policy.timeout_seconds,
                    },
                )
            except Exception:
                logger.warning(
                    "failed_to_emit_timeout_event",
                    timeout=plan.policy.timeout_seconds,
                )
        except Exception as exc:
            logger.error("agentic_loop_failed", error=str(exc))
            return RunResult(
                run_id=run_id,
                status=RunStatus.FAILED,
                error=str(exc),
            )

        # --- Emit AGENTIC_LOOP_STOPPED ---
        await self._emit(
            event_type=EventType.AGENTIC_LOOP_STOPPED.value,
            run_id=run_id,
            correlation_id=correlation_id,
            payload={
                "stop_reason": stop_reason,
                "turns": state.turn_count,
            },
        )
        logger.info(
            "agentic_loop_stopped",
            stop_reason=stop_reason,
            turns=state.turn_count,
        )

        return RunResult(
            run_id=run_id,
            status=RunStatus.FINISHED,
            output=[
                {"sender": m.sender_id, "content": m.content}
                for m in conversation.messages
            ],
            metadata={"stop_reason": stop_reason, "turns": state.turn_count},
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_plan(self, plan: AgenticLoopPlan) -> str | None:
        """Return an error message if the plan references unknown agents."""
        if plan.router_agent not in self._registry:
            return f"Router agent '{plan.router_agent}' not found in registry"
        for participant in plan.participants:
            if participant not in self._registry:
                return f"Participant '{participant}' not found in registry"
        return None

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
            scope=_SCOPE,
            payload=payload or {},
        )
        await self._runner.event_sink.publish(event)
