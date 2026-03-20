from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import anyio

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events import EventSink, EventType, NullEventSink
from miniautogen.observability import get_logger
from miniautogen.policies.approval import ApprovalGate, ApprovalRequest
from miniautogen.policies.chain import PolicyChain, PolicyContext
from miniautogen.policies.execution import ExecutionPolicy
from miniautogen.policies.retry import RetryPolicy, build_retrying_call
from miniautogen.stores.checkpoint_store import CheckpointStore
from miniautogen.stores.run_store import RunStore

if TYPE_CHECKING:
    from miniautogen.backends.engine_resolver import EngineResolver
    from miniautogen.cli.config import WorkspaceConfig
    from miniautogen.core.contracts.agent_spec import AgentSpec
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
    ) -> None:
        self.event_sink = event_sink or NullEventSink()
        self.run_store = run_store
        self.checkpoint_store = checkpoint_store
        self.execution_policy = execution_policy
        self._approval_gate = approval_gate
        self._retry_policy = retry_policy
        self._policy_chain = policy_chain
        self._engine_resolver = engine_resolver
        self.last_run_id: str | None = None
        self.logger = get_logger(__name__)

    # ------------------------------------------------------------------
    # Agent runtime factory
    # ------------------------------------------------------------------

    def _build_agent_runtimes(
        self,
        *,
        agent_specs: dict[str, AgentSpec],
        workspace: Path,
        config: WorkspaceConfig,
    ) -> dict[str, AgentRuntime]:
        """Build AgentRuntime instances from YAML config.

        This is the SOLE point where AgentRuntime instances are created.
        Each agent gets its own fresh driver, InMemory tool registry,
        InMemory memory provider, and a ConfigDelegationRouter derived
        from the agent specs' delegation configs.

        Args:
            agent_specs: Mapping of agent_name -> AgentSpec.
            workspace: Project workspace root path.
            config: The full workspace/project configuration.

        Returns:
            Mapping of agent_name -> AgentRuntime.
        """
        from miniautogen.backends.engine_resolver import EngineResolver
        from miniautogen.core.contracts.memory_provider import (
            InMemoryMemoryProvider,
        )
        from miniautogen.core.contracts.run_context import RunContext
        from miniautogen.core.runtime.agent_runtime import AgentRuntime
        from miniautogen.core.runtime.delegation_router import (
            ConfigDelegationRouter,
        )
        from miniautogen.core.runtime.tool_registry import InMemoryToolRegistry

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

        # Build a placeholder RunContext (will be replaced at run time)
        run_context = RunContext(
            run_id="pending",
            started_at=datetime.now(timezone.utc),
            correlation_id="pending",
        )

        runtimes: dict[str, AgentRuntime] = {}

        for agent_name, spec in agent_specs.items():
            # 1. Fresh driver per agent
            engine_profile = spec.engine_profile or "default"
            driver = resolver.create_fresh_driver(engine_profile, config)

            # 2. Per-agent config dir
            config_dir = workspace / ".miniautogen" / "agents" / agent_name

            # 3-4. InMemory implementations (FileSystem impls in Tasks 8-9)
            tool_registry = InMemoryToolRegistry()
            memory = InMemoryMemoryProvider()

            # 5. Build system prompt from spec fields
            system_prompt_parts: list[str] = []
            if spec.role:
                system_prompt_parts.append(f"Role: {spec.role}")
            if spec.goal:
                system_prompt_parts.append(f"Goal: {spec.goal}")
            if spec.backstory:
                system_prompt_parts.append(f"Backstory: {spec.backstory}")
            system_prompt = "\n".join(system_prompt_parts) or None

            # 6. Compose AgentRuntime
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
            )
            # Store config_dir for later use by filesystem-backed providers
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
