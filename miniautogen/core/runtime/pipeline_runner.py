from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import anyio

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events import EventSink, EventType
from miniautogen.core.events.event_bus import EventBus
from miniautogen.core.events.event_sink import CompositeEventSink
from miniautogen.observability import get_logger
from miniautogen.policies.approval import ApprovalGate, ApprovalRequest
from miniautogen.policies.approval_channel import ApprovalChannel, ChannelApprovalGate
from miniautogen.policies.chain import PolicyChain, PolicyContext
from miniautogen.policies.execution import ExecutionPolicy
from miniautogen.policies.retry import RetryPolicy, build_retrying_call
from miniautogen.stores.checkpoint_store import CheckpointStore
from miniautogen.stores.run_store import RunStore

if TYPE_CHECKING:
    from miniautogen.backends.engine_resolver import EngineResolver
    from miniautogen.cli.config import FlowConfig, WorkspaceConfig
    from miniautogen.core.contracts.agent_spec import AgentSpec
    from miniautogen.core.contracts.run_result import RunResult
    from miniautogen.core.runtime.agent_runtime import AgentRuntime


class PipelineRunner:
    """Runs an existing pipeline while keeping runtime mechanics centralized."""

    def __init__(
        self,
        event_sink: EventSink | None = None,
        run_store: RunStore | None = None,
        checkpoint_store: CheckpointStore | None = None,
        execution_policy: ExecutionPolicy | None = None,
        approval_gate: ApprovalGate | None = None,
        retry_policy: RetryPolicy | None = None,
        policy_chain: PolicyChain | None = None,
        engine_resolver: EngineResolver | None = None,
        approval_channel: ApprovalChannel | None = None,
    ) -> None:
        self._event_bus = EventBus()

        if event_sink is None:
            self.event_sink: EventSink = self._event_bus
        else:
            self.event_sink = CompositeEventSink([event_sink, self._event_bus])

        self.run_store = run_store
        self.checkpoint_store = checkpoint_store
        self.execution_policy = execution_policy
        # If an ApprovalChannel is provided but no gate, bridge it
        if approval_channel is not None and approval_gate is None:
            self._approval_gate: ApprovalGate | None = ChannelApprovalGate(approval_channel)
        else:
            self._approval_gate = approval_gate
        self._retry_policy = retry_policy
        self._policy_chain = policy_chain
        self._engine_resolver = engine_resolver
        self.last_run_id: str | None = None
        self.logger = get_logger(__name__)

    @property
    def event_bus(self) -> EventBus:
        """EventBus for reactive policy subscriptions."""
        return self._event_bus

    # ------------------------------------------------------------------
    # Agent runtime factory
    # ------------------------------------------------------------------

    async def _build_agent_runtimes(
        self,
        *,
        agent_specs: dict[str, AgentSpec],
        workspace: Path,
        config: WorkspaceConfig,
        run_id: str,
        flow_config: FlowConfig | None = None,
    ) -> dict[str, AgentRuntime]:
        """Build AgentRuntime instances from YAML config.

        This is the SOLE point where AgentRuntime instances are created.
        Each agent gets its own fresh driver, CompositeToolRegistry
        (FileSystem + Builtin), PersistentMemoryProvider, filesystem
        sandbox, and a ConfigDelegationRouter derived from the agent
        specs' delegation configs.

        Args:
            agent_specs: Mapping of agent_name -> AgentSpec.
            workspace: Project workspace root path.
            config: The full workspace/project configuration.
            run_id: The run identifier for the RunContext.

        Returns:
            Mapping of agent_name -> AgentRuntime.
        """
        from miniautogen.backends.engine_resolver import EngineResolver
        from miniautogen.core.contracts.run_context import RunContext
        from miniautogen.core.runtime.agent_runtime import AgentRuntime
        from miniautogen.core.runtime.agent_sandbox import (
            AgentFilesystemSandbox,
        )
        from miniautogen.core.runtime.builtin_tools import BuiltinToolRegistry
        from miniautogen.core.runtime.composite_tool_registry import (
            CompositeToolRegistry,
        )
        from miniautogen.core.runtime.delegation_router import (
            ConfigDelegationRouter,
        )
        from miniautogen.core.runtime.filesystem_tool_registry import (
            FileSystemToolRegistry,
        )
        from miniautogen.core.runtime.persistent_memory import (
            PersistentMemoryProvider,
        )

        resolver = self._engine_resolver or EngineResolver()

        # Build delegation configs for the router
        delegation_configs: dict[str, dict[str, Any]] = {}
        for agent_name, spec in agent_specs.items():
            delegation_configs[agent_name] = {
                "allow_delegation": spec.delegation.allow_delegation,
                "can_delegate_to": list(spec.delegation.can_delegate_to),
                "context_isolation": spec.delegation.context_isolation,
            }
        delegation_router = ConfigDelegationRouter(delegation_configs)

        # Build a real RunContext
        run_context = RunContext(
            run_id=run_id,
            started_at=datetime.now(timezone.utc),
            correlation_id=run_id,
        )

        runtimes: dict[str, AgentRuntime] = {}

        for agent_name, spec in agent_specs.items():
            # 1. Fresh driver per agent
            engine_profile = spec.engine_profile or "default"
            driver = resolver.create_fresh_driver(engine_profile, config)

            # 2. Per-agent config dir
            config_dir = workspace / ".miniautogen" / "agents" / agent_name

            # 3. Per-agent filesystem sandbox
            sandbox = AgentFilesystemSandbox(
                agent_name=agent_name,
                workspace=workspace,
            )

            # 4. CompositeToolRegistry: FileSystem tools first, then builtins
            tools_path = config_dir / "tools.yml"
            fs_registry = FileSystemToolRegistry(
                tools_path=tools_path,
                workspace_root=workspace,
                sandbox=sandbox,
            )
            builtin_registry = BuiltinToolRegistry(
                workspace_root=workspace,
                sandbox=sandbox,
            )
            tool_registry = CompositeToolRegistry(
                [fs_registry, builtin_registry],
            )

            # 5. PersistentMemoryProvider
            memory = PersistentMemoryProvider(config_dir / "memory")

            # 6. Build system prompt from spec + optional prompt.md
            system_prompt = await _build_prompt_from_spec(
                spec, config_dir,
            )

            # 7. Compose AgentRuntime
            rt = AgentRuntime(
                agent_id=agent_name,
                driver=driver,
                run_context=run_context,
                event_sink=self.event_sink,
                system_prompt=system_prompt,
                hooks=[],
                memory=memory,
                tool_registry=tool_registry,
                delegation=delegation_router,
                flow_prompts=flow_config.prompts if flow_config else {},
                response_format=flow_config.response_format if flow_config else "json",
            )
            # Store config_dir for later use
            rt._config_dir = config_dir  # noqa: SLF001

            runtimes[agent_name] = rt

        # Register agents in delegation router for cross-agent delegation
        for agent_name, rt in runtimes.items():
            delegation_router.register_agent(agent_name, rt)

        return runtimes

    async def _execute_pipeline(
        self,
        pipeline: Any,
        state: Any,
    ) -> Any:
        """Run the pipeline, optionally wrapping with retry policy."""
        if self._retry_policy is not None:
            retrying_call = build_retrying_call(self._retry_policy)
            return await retrying_call(lambda: pipeline.run(state))
        return await pipeline.run(state)

    async def _persist_failed_run(
        self,
        run_id: str,
        correlation_id: str,
        error_type: str,
    ) -> None:
        if self.run_store is not None:
            await self.run_store.save_run(
                run_id,
                {
                    "status": "failed",
                    "correlation_id": correlation_id,
                    "error_type": error_type,
                },
            )
        await self.event_sink.publish(
            ExecutionEvent(
                type=EventType.RUN_FAILED.value,
                timestamp=datetime.now(timezone.utc),
                run_id=run_id,
                correlation_id=correlation_id,
                scope="pipeline_runner",
                payload={"error_type": error_type},
            )
        )

    async def run_pipeline(
        self,
        pipeline: Any,
        state: Any,
        *,
        timeout_seconds: float | None = None,
    ) -> Any:
        run_id = getattr(state, "run_id", None) or getattr(state, "id", None) or str(uuid4())
        correlation_id = str(uuid4())
        current_run_id = str(run_id)
        self.last_run_id = current_run_id
        effective_timeout = timeout_seconds
        if effective_timeout is None and self.execution_policy is not None:
            effective_timeout = self.execution_policy.timeout_seconds
        logger = self.logger.bind(
            run_id=current_run_id,
            correlation_id=correlation_id,
            scope="pipeline_runner",
        )

        if self.run_store is not None:
            await self.run_store.save_run(
                current_run_id,
                {
                    "status": "started",
                    "correlation_id": correlation_id,
                },
            )

        # Register reactive policies on EventBus before any events are emitted
        if self._policy_chain is not None:
            self._policy_chain.register_reactive_on_bus(self._event_bus)

        await self.event_sink.publish(
            ExecutionEvent(
                type=EventType.RUN_STARTED.value,
                timestamp=datetime.now(timezone.utc),
                run_id=current_run_id,
                correlation_id=correlation_id,
                scope="pipeline_runner",
            )
        )
        logger.info("run_started")

        # TODO(review): fail-open by design — gate is optional
        # for SDK use (sec-reviewer, 2026-03-16, Low)
        if self._approval_gate is not None:
            approval_req = ApprovalRequest(
                request_id=f"approval_{uuid4().hex[:8]}",
                action="run_pipeline",
                description=f"Execute pipeline run {current_run_id}",
            )
            await self.event_sink.publish(
                ExecutionEvent(
                    type=EventType.APPROVAL_REQUESTED.value,
                    timestamp=datetime.now(timezone.utc),
                    run_id=current_run_id,
                    correlation_id=correlation_id,
                    scope="pipeline_runner",
                    payload={
                        "request_id": approval_req.request_id,
                        "action": approval_req.action,
                    },
                )
            )
            approval_resp = await self._approval_gate.request_approval(
                approval_req,
            )
            if approval_resp.decision == "denied":
                await self.event_sink.publish(
                    ExecutionEvent(
                        type=EventType.APPROVAL_DENIED.value,
                        timestamp=datetime.now(timezone.utc),
                        run_id=current_run_id,
                        correlation_id=correlation_id,
                        scope="pipeline_runner",
                        payload={"reason": approval_resp.reason},
                    )
                )
                if self.run_store is not None:
                    await self.run_store.save_run(
                        current_run_id,
                        {"status": "cancelled", "correlation_id": correlation_id},
                    )
                msg = f"Pipeline run {current_run_id} denied: {approval_resp.reason}"
                raise RuntimeError(msg)
            await self.event_sink.publish(
                ExecutionEvent(
                    type=EventType.APPROVAL_GRANTED.value,
                    timestamp=datetime.now(timezone.utc),
                    run_id=current_run_id,
                    correlation_id=correlation_id,
                    scope="pipeline_runner",
                )
            )

        if self._policy_chain is not None:
            policy_ctx = PolicyContext(
                action="run_pipeline",
                run_id=current_run_id,
                metadata={"correlation_id": correlation_id},
            )
            policy_result = await self._policy_chain.evaluate(policy_ctx)
            if policy_result.decision == "deny":
                reason = policy_result.reason or "denied by policy chain"
                await self._persist_failed_run(
                    current_run_id, correlation_id, "PolicyDenied",
                )
                msg = f"Pipeline run {current_run_id} denied by policy: {reason}"
                raise RuntimeError(msg)
            if policy_result.decision == "retry":
                logger.warning(
                    "policy_chain_retry_advisory",
                    reason=policy_result.reason,
                )

        try:
            if effective_timeout is None:
                result = await self._execute_pipeline(pipeline, state)
            else:
                with anyio.fail_after(effective_timeout):
                    result = await self._execute_pipeline(pipeline, state)
        except TimeoutError:
            if self.run_store is not None:
                await self.run_store.save_run(
                    current_run_id,
                    {
                        "status": "timed_out",
                        "correlation_id": correlation_id,
                    },
                )
            await self.event_sink.publish(
                ExecutionEvent(
                    type=EventType.RUN_TIMED_OUT.value,
                    timestamp=datetime.now(timezone.utc),
                    run_id=current_run_id,
                    correlation_id=correlation_id,
                    scope="pipeline_runner",
                )
            )
            logger.warning("run_timed_out")
            raise
        except Exception as exc:
            await self._persist_failed_run(current_run_id, correlation_id, type(exc).__name__)
            logger.error("run_failed", error_type=type(exc).__name__)
            raise

        try:
            if self.run_store is not None:
                await self.run_store.save_run(
                    current_run_id,
                    {
                        "status": "finished",
                        "correlation_id": correlation_id,
                    },
                )
            if self.checkpoint_store is not None:
                await self.checkpoint_store.save_checkpoint(current_run_id, result)
        except Exception as exc:
            await self._persist_failed_run(current_run_id, correlation_id, type(exc).__name__)
            raise
        await self.event_sink.publish(
            ExecutionEvent(
                type=EventType.RUN_FINISHED.value,
                timestamp=datetime.now(timezone.utc),
                run_id=current_run_id,
                correlation_id=correlation_id,
                scope="pipeline_runner",
            )
        )
        logger.info("run_finished")
        self.last_run_id = current_run_id
        return result

    # ------------------------------------------------------------------
    # Config-driven flow execution
    # ------------------------------------------------------------------

    async def run_from_config(
        self,
        *,
        flow_config: FlowConfig,
        agent_specs: dict[str, AgentSpec],
        workspace: Path,
        config: WorkspaceConfig,
        input_text: str | None = None,
        resume_run_id: str | None = None,
    ) -> RunResult:
        """Execute a config-driven flow (no Python callable needed).

        Orchestrates the full lifecycle:
        1. Validate participants exist in agent_specs
        2. Build agent runtimes (async)
        3. Initialize all runtimes
        4. Build coordination plan + runtime from FlowConfig
        5. Emit RUN_STARTED, run coordination, emit RUN_COMPLETED
        6. Clean up runtimes in finally block

        Args:
            flow_config: The FlowConfig describing the flow mode/participants.
            agent_specs: All available agent specs.
            workspace: Project workspace root.
            config: Full workspace configuration.
            input_text: Optional input text for the flow.

        Returns:
            RunResult from the coordination runtime.

        Raises:
            ValueError: If participants reference unknown agents or mode is
                        unknown.
        """
        from miniautogen.core.contracts.run_context import RunContext

        run_id = resume_run_id or str(uuid4())
        correlation_id = run_id
        self.last_run_id = run_id

        logger = self.logger.bind(
            run_id=run_id,
            correlation_id=correlation_id,
            scope="pipeline_runner.run_from_config",
        )

        # 1. Validate participants exist
        missing = [
            p for p in flow_config.participants if p not in agent_specs
        ]
        if missing:
            msg = (
                f"Flow references unknown agents: {', '.join(missing)}. "
                f"Available: {', '.join(agent_specs.keys())}"
            )
            raise ValueError(msg)

        # 2. Build agent runtimes
        runtimes = await self._build_agent_runtimes(
            agent_specs=agent_specs,
            workspace=workspace,
            config=config,
            run_id=run_id,
            flow_config=flow_config,
        )

        # 3. Initialize all runtimes
        try:
            for rt in runtimes.values():
                await rt.initialize()

            # 4. Build coordination plan + runtime
            plan, coordination_runtime = _build_coordination_from_config(
                flow_config=flow_config,
                runner=self,
                agent_registry=runtimes,
                input_text=input_text,
            )

            # 5. Build RunContext for the coordination run
            run_context = RunContext(
                run_id=run_id,
                started_at=datetime.now(timezone.utc),
                correlation_id=correlation_id,
                input_payload=input_text,
            )

            # Register reactive policies on EventBus before any events are emitted
            if self._policy_chain is not None:
                self._policy_chain.register_reactive_on_bus(self._event_bus)

            # Emit RUN_STARTED
            await self.event_sink.publish(
                ExecutionEvent(
                    type=EventType.RUN_STARTED.value,
                    timestamp=datetime.now(timezone.utc),
                    run_id=run_id,
                    correlation_id=correlation_id,
                    scope="pipeline_runner.run_from_config",
                )
            )
            logger.info("run_from_config_started", mode=flow_config.mode)

            # 6. Execute coordination
            agents_list = [
                runtimes[name] for name in flow_config.participants
            ]
            result = await coordination_runtime.run(
                agents_list, run_context, plan,
            )

            # Emit RUN_FINISHED
            await self.event_sink.publish(
                ExecutionEvent(
                    type=EventType.RUN_FINISHED.value,
                    timestamp=datetime.now(timezone.utc),
                    run_id=run_id,
                    correlation_id=correlation_id,
                    scope="pipeline_runner.run_from_config",
                )
            )
            logger.info("run_from_config_finished", mode=flow_config.mode)

            return result

        except Exception as exc:
            # Emit RUN_FAILED on error
            try:
                await self.event_sink.publish(
                    ExecutionEvent(
                        type=EventType.RUN_FAILED.value,
                        timestamp=datetime.now(timezone.utc),
                        run_id=run_id,
                        correlation_id=correlation_id,
                        scope="pipeline_runner.run_from_config",
                        payload={"error": str(exc)},
                    )
                )
            except Exception:
                logger.warning(
                    "failed_to_emit_run_failed_event",
                    original_error=str(exc),
                )
            logger.error(
                "run_from_config_failed",
                error_type=type(exc).__name__,
            )
            raise

        finally:
            # 7. Close all runtimes
            for rt in runtimes.values():
                try:
                    await rt.close()
                except Exception:
                    logger.warning(
                        "runtime_close_failed",
                        agent_id=rt.agent_id,
                    )


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


async def _build_prompt_from_spec(
    spec: AgentSpec,
    config_dir: Path,
) -> str | None:
    """Build a system prompt from an AgentSpec, optionally loading prompt.md.

    If ``config_dir/prompt.md`` exists, its content is prepended to the
    spec-derived prompt parts. Returns None only if all sources are empty.
    """
    parts: list[str] = []

    # Try loading prompt.md from disk
    prompt_path = anyio.Path(config_dir / "prompt.md")
    if await prompt_path.is_file():
        content = await prompt_path.read_text()
        stripped = content.strip()
        if stripped:
            parts.append(stripped)

    # Append spec-derived fields
    if spec.role:
        parts.append(f"Role: {spec.role}")
    if spec.goal:
        parts.append(f"Goal: {spec.goal}")
    if spec.backstory:
        parts.append(f"Backstory: {spec.backstory}")

    return "\n".join(parts) if parts else None


def _build_coordination_from_config(
    *,
    flow_config: FlowConfig,
    runner: PipelineRunner,
    agent_registry: dict[str, Any],
    input_text: str | None = None,
) -> tuple[Any, Any]:
    """Map a FlowConfig to a (plan, coordination_runtime) tuple.

    Supports three coordination modes:
    - ``workflow``: Sequential/parallel step execution via WorkflowRuntime
    - ``deliberation``: Multi-round deliberation via DeliberationRuntime
    - ``loop``: Router-driven agentic loop via AgenticLoopRuntime

    Args:
        flow_config: The FlowConfig describing mode and participants.
        runner: The PipelineRunner instance for coordination runtimes.
        agent_registry: Mapping of agent_name -> AgentRuntime.
        input_text: Optional input text (used as initial message / topic).

    Returns:
        Tuple of (plan, coordination_runtime).

    Raises:
        ValueError: If the flow mode is unknown.
    """
    from miniautogen.core.contracts.coordination import (
        AgenticLoopPlan,
        DeliberationPlan,
        WorkflowPlan,
        WorkflowStep,
    )
    from miniautogen.core.runtime.agentic_loop_runtime import (
        AgenticLoopRuntime,
    )
    from miniautogen.core.runtime.deliberation_runtime import (
        DeliberationRuntime,
    )
    from miniautogen.core.runtime.workflow_runtime import WorkflowRuntime

    mode = flow_config.mode

    # Build CheckpointManager when runner has a checkpoint_store so that
    # coordination runtimes can persist step-level progress.
    checkpoint_manager = None
    if runner.checkpoint_store is not None:
        from miniautogen.core.runtime.checkpoint_manager import CheckpointManager
        from miniautogen.stores.in_memory_event_store import InMemoryEventStore

        checkpoint_manager = CheckpointManager(
            checkpoint_store=runner.checkpoint_store,
            event_store=InMemoryEventStore(),
            event_sink=runner.event_sink,
        )

    if mode == "workflow":
        steps = [
            WorkflowStep(
                component_name=name,
                agent_id=name,
            )
            for name in flow_config.participants
        ]
        plan = WorkflowPlan(steps=steps)
        coordination_runtime = WorkflowRuntime(
            runner=runner,
            agent_registry=agent_registry,
            checkpoint_manager=checkpoint_manager,
        )
        return plan, coordination_runtime

    if mode == "deliberation":
        plan = DeliberationPlan(
            topic=input_text or "",
            participants=list(flow_config.participants),
            max_rounds=flow_config.max_rounds,
            leader_agent=flow_config.leader,
        )
        coordination_runtime = DeliberationRuntime(
            runner=runner,
            agent_registry=agent_registry,
        )
        return plan, coordination_runtime

    if mode == "loop":
        plan = AgenticLoopPlan(
            router_agent=flow_config.router or flow_config.participants[0],
            participants=list(flow_config.participants),
            initial_message=input_text,
        )
        coordination_runtime = AgenticLoopRuntime(
            runner=runner,
            agent_registry=agent_registry,
        )
        return plan, coordination_runtime

    msg = (
        f"Unknown flow mode: {mode!r}. "
        f"Supported modes: workflow, deliberation, loop"
    )
    raise ValueError(msg)
