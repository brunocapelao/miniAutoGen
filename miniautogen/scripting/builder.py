"""ScriptBuilder — imperative builder for multi-agent flows without YAML.

Provides a fluent API for defining agents, tools, and coordination flows
purely in Python code. Internally constructs the same runtime objects
(AgentSpec, EngineProfile, RunContext) that the YAML-based CLI uses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from miniautogen.core.contracts.agent_spec import AgentSpec
from miniautogen.core.contracts.enums import RunStatus
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.run_result import RunResult
from miniautogen.core.events.event_sink import EventSink, InMemoryEventSink, NullEventSink
from miniautogen.policies.approval import ApprovalGate


@dataclass
class _AgentDef:
    """Internal agent definition captured by the builder."""

    name: str
    model: str = "gpt-4o"
    provider: str = "openai"
    role: str = ""
    goal: str = ""
    system_prompt: str | None = None
    temperature: float = 0.2
    max_tokens: int | None = None
    api_key: str | None = None
    endpoint: str | None = None
    timeout_seconds: float = 120.0
    tools: list[Any] = field(default_factory=list)


class ScriptBuilder:
    """Imperative builder for defining and running multi-agent flows.

    Usage::

        builder = ScriptBuilder()
        builder.add_agent("analyst", model="gpt-4o", role="Data analyst")
        builder.add_agent("reviewer", model="gpt-4o", role="Code reviewer")

        # Single agent
        result = await builder.single_run("analyst", input="Analyze this")

        # Workflow (sequential)
        result = await builder.workflow(["analyst", "reviewer"], input="Review this")

        # Deliberation
        result = await builder.deliberation(
            topic="API design",
            participants=["analyst", "reviewer"],
            leader="analyst",
        )
    """

    def __init__(
        self,
        *,
        event_sink: EventSink | None = None,
        approval_gate: ApprovalGate | None = None,
    ) -> None:
        self._agents: dict[str, _AgentDef] = {}
        self._event_sink = event_sink or NullEventSink()
        self._approval_gate = approval_gate

    def add_agent(
        self,
        name: str,
        *,
        model: str = "gpt-4o",
        provider: str = "openai",
        role: str = "",
        goal: str = "",
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        api_key: str | None = None,
        endpoint: str | None = None,
        timeout_seconds: float = 120.0,
    ) -> "ScriptBuilder":
        """Add an agent definition to the builder.

        Args:
            name: Unique agent identifier.
            model: Model identifier (e.g., "gpt-4o", "claude-3-5-sonnet").
            provider: Provider name ("openai", "anthropic", "google").
            role: Agent role description.
            goal: Agent goal description.
            system_prompt: Optional system prompt.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in response.
            api_key: API key (reads from env if not provided).
            endpoint: Custom API endpoint URL.
            timeout_seconds: Request timeout.

        Returns:
            Self for method chaining.
        """
        self._agents[name] = _AgentDef(
            name=name,
            model=model,
            provider=provider,
            role=role,
            goal=goal,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key,
            endpoint=endpoint,
            timeout_seconds=timeout_seconds,
        )
        return self

    def add_tool(self, agent_name: str, tool: Any) -> "ScriptBuilder":
        """Attach a tool to an agent.

        Args:
            agent_name: Name of the agent to attach the tool to.
            tool: Tool instance (must satisfy ToolProtocol).

        Returns:
            Self for method chaining.

        Raises:
            KeyError: If agent_name has not been added yet.
        """
        if agent_name not in self._agents:
            raise KeyError(
                f"Agent '{agent_name}' not found. "
                f"Call add_agent('{agent_name}', ...) first."
            )
        self._agents[agent_name].tools.append(tool)
        return self

    # ------------------------------------------------------------------
    # Execution methods
    # ------------------------------------------------------------------

    async def single_run(
        self,
        agent_name: str,
        *,
        input: str,
    ) -> RunResult:
        """Execute a single agent on the given input.

        Args:
            agent_name: Which agent to run.
            input: Task/prompt for the agent.

        Returns:
            RunResult with the agent's output.
        """
        if agent_name not in self._agents:
            raise KeyError(f"Agent '{agent_name}' not found")

        run_id = str(uuid4())
        runtimes = await self._build_runtimes(run_id)

        try:
            rt = runtimes[agent_name]
            await rt.initialize()
            output = await rt.process(input)
            return RunResult(
                run_id=run_id,
                status=RunStatus.FINISHED,
                output=output,
            )
        except Exception as exc:
            return RunResult(
                run_id=run_id,
                status=RunStatus.FAILED,
                error=str(exc),
            )
        finally:
            for rt in runtimes.values():
                try:
                    await rt.close()
                except Exception:
                    pass

    async def workflow(
        self,
        agents: list[str],
        *,
        input: str,
        fan_out: bool = False,
        synthesis_agent: str | None = None,
    ) -> RunResult:
        """Execute a workflow coordination across multiple agents.

        Args:
            agents: Ordered list of agent names to execute.
            input: Initial input for the workflow.
            fan_out: If True, run agents in parallel instead of sequentially.
            synthesis_agent: Optional agent to synthesize parallel results.

        Returns:
            RunResult from the workflow execution.
        """
        for name in agents:
            if name not in self._agents:
                raise KeyError(f"Agent '{name}' not found")
        if synthesis_agent and synthesis_agent not in self._agents:
            raise KeyError(f"Synthesis agent '{synthesis_agent}' not found")

        from miniautogen.core.contracts.coordination import (
            WorkflowPlan,
            WorkflowStep,
        )
        from miniautogen.core.runtime.pipeline_runner import PipelineRunner
        from miniautogen.core.runtime.workflow_runtime import WorkflowRuntime

        run_id = str(uuid4())
        runtimes = await self._build_runtimes(run_id)

        try:
            for rt in runtimes.values():
                await rt.initialize()

            runner = PipelineRunner(
                event_sink=self._event_sink,
                approval_gate=self._approval_gate,
            )

            steps = [
                WorkflowStep(component_name=name, agent_id=name)
                for name in agents
            ]
            plan = WorkflowPlan(
                steps=steps,
                fan_out=fan_out,
                synthesis_agent=synthesis_agent,
            )

            context = RunContext(
                run_id=run_id,
                started_at=datetime.now(timezone.utc),
                correlation_id=run_id,
                input_payload=input,
            )

            wf_runtime = WorkflowRuntime(
                runner=runner,
                agent_registry=runtimes,
            )
            return await wf_runtime.run(
                list(runtimes.values()), context, plan,
            )
        except Exception as exc:
            return RunResult(
                run_id=run_id,
                status=RunStatus.FAILED,
                error=str(exc),
            )
        finally:
            for rt in runtimes.values():
                try:
                    await rt.close()
                except Exception:
                    pass

    async def deliberation(
        self,
        *,
        topic: str,
        participants: list[str],
        leader: str,
        max_rounds: int = 3,
    ) -> RunResult:
        """Execute a deliberation coordination.

        Args:
            topic: The deliberation topic.
            participants: List of agent names participating.
            leader: Name of the leader agent.
            max_rounds: Maximum deliberation rounds.

        Returns:
            RunResult from the deliberation.
        """
        for name in participants:
            if name not in self._agents:
                raise KeyError(f"Agent '{name}' not found")
        if leader not in self._agents:
            raise KeyError(f"Leader agent '{leader}' not found")

        from miniautogen.core.contracts.coordination import DeliberationPlan
        from miniautogen.core.runtime.deliberation_runtime import (
            DeliberationRuntime,
        )
        from miniautogen.core.runtime.pipeline_runner import PipelineRunner

        run_id = str(uuid4())
        runtimes = await self._build_runtimes(run_id)

        try:
            for rt in runtimes.values():
                await rt.initialize()

            runner = PipelineRunner(
                event_sink=self._event_sink,
                approval_gate=self._approval_gate,
            )

            plan = DeliberationPlan(
                topic=topic,
                participants=participants,
                max_rounds=max_rounds,
                leader_agent=leader,
            )

            context = RunContext(
                run_id=run_id,
                started_at=datetime.now(timezone.utc),
                correlation_id=run_id,
            )

            delib_runtime = DeliberationRuntime(
                runner=runner,
                agent_registry=runtimes,
            )
            return await delib_runtime.run(
                list(runtimes.values()), context, plan,
            )
        except Exception as exc:
            return RunResult(
                run_id=run_id,
                status=RunStatus.FAILED,
                error=str(exc),
            )
        finally:
            for rt in runtimes.values():
                try:
                    await rt.close()
                except Exception:
                    pass

    async def loop(
        self,
        *,
        router: str,
        participants: list[str],
        initial_message: str,
        goal: str = "",
    ) -> RunResult:
        """Execute an agentic loop coordination.

        Args:
            router: Name of the router agent.
            participants: List of agent names in the loop.
            initial_message: Starting message for the conversation.
            goal: Optional goal description.

        Returns:
            RunResult from the agentic loop.
        """
        for name in participants:
            if name not in self._agents:
                raise KeyError(f"Agent '{name}' not found")
        if router not in self._agents:
            raise KeyError(f"Router agent '{router}' not found")

        from miniautogen.core.contracts.coordination import AgenticLoopPlan
        from miniautogen.core.runtime.agentic_loop_runtime import (
            AgenticLoopRuntime,
        )
        from miniautogen.core.runtime.pipeline_runner import PipelineRunner

        run_id = str(uuid4())
        runtimes = await self._build_runtimes(run_id)

        try:
            for rt in runtimes.values():
                await rt.initialize()

            runner = PipelineRunner(
                event_sink=self._event_sink,
                approval_gate=self._approval_gate,
            )

            plan = AgenticLoopPlan(
                router_agent=router,
                participants=participants,
                initial_message=initial_message,
                goal=goal,
            )

            context = RunContext(
                run_id=run_id,
                started_at=datetime.now(timezone.utc),
                correlation_id=run_id,
            )

            loop_runtime = AgenticLoopRuntime(
                runner=runner,
                agent_registry=runtimes,
            )
            return await loop_runtime.run(
                list(runtimes.values()), context, plan,
            )
        except Exception as exc:
            return RunResult(
                run_id=run_id,
                status=RunStatus.FAILED,
                error=str(exc),
            )
        finally:
            for rt in runtimes.values():
                try:
                    await rt.close()
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _build_runtimes(
        self,
        run_id: str,
    ) -> dict[str, Any]:
        """Build AgentRuntime instances from builder definitions.

        Creates the minimal infrastructure (driver, tools, memory) needed
        to run agents without a full workspace/YAML setup.
        """
        from miniautogen.backends.config import AuthConfig, BackendConfig, DriverType
        from miniautogen.backends.resolver import BackendResolver
        from miniautogen.core.runtime.agent_runtime import AgentRuntime
        from miniautogen.core.runtime.builtin_tools import BuiltinToolRegistry
        from miniautogen.core.runtime.tool_registry import InMemoryToolRegistry
        from miniautogen.core.runtime.composite_tool_registry import CompositeToolRegistry

        # Provider -> DriverType mapping
        provider_map: dict[str, DriverType] = {
            "openai": DriverType.OPENAI_SDK,
            "anthropic": DriverType.ANTHROPIC_SDK,
            "google": DriverType.GOOGLE_GENAI,
            "litellm": DriverType.LITELLM,
        }

        resolver = BackendResolver()
        self._register_factories(resolver)

        run_context = RunContext(
            run_id=run_id,
            started_at=datetime.now(timezone.utc),
            correlation_id=run_id,
        )

        runtimes: dict[str, Any] = {}

        for name, agent_def in self._agents.items():
            driver_type = provider_map.get(agent_def.provider)
            if driver_type is None:
                raise ValueError(
                    f"Unknown provider '{agent_def.provider}' for agent '{name}'. "
                    f"Supported: {', '.join(provider_map.keys())}"
                )

            # Build backend config
            import os

            auth: AuthConfig | None = None
            if agent_def.api_key:
                env_key = f"_MINIAUTOGEN_SCRIPT_{name.upper()}_KEY"
                os.environ[env_key] = agent_def.api_key
                auth = AuthConfig(type="bearer", token_env=env_key)

            metadata: dict[str, Any] = {"model": agent_def.model}
            metadata["temperature"] = agent_def.temperature
            if agent_def.max_tokens is not None:
                metadata["max_tokens"] = agent_def.max_tokens
            metadata.setdefault("health_endpoint", None)

            backend_config = BackendConfig(
                backend_id=f"script_{name}_{uuid4().hex[:8]}",
                driver=driver_type,
                endpoint=agent_def.endpoint,
                auth=auth,
                timeout_seconds=agent_def.timeout_seconds,
                metadata=metadata,
            )

            driver = resolver.create_driver(backend_config)

            # Build system prompt
            prompt_parts: list[str] = []
            if agent_def.system_prompt:
                prompt_parts.append(agent_def.system_prompt)
            if agent_def.role:
                prompt_parts.append(f"Role: {agent_def.role}")
            if agent_def.goal:
                prompt_parts.append(f"Goal: {agent_def.goal}")
            system_prompt = "\n".join(prompt_parts) if prompt_parts else None

            # Build tool registry from attached tools
            tool_registries: list[Any] = []
            if agent_def.tools:
                mem_registry = InMemoryToolRegistry()
                for tool in agent_def.tools:
                    mem_registry.register(tool)
                tool_registries.append(mem_registry)

            tool_registry: Any = None
            if tool_registries:
                tool_registry = CompositeToolRegistry(tool_registries)

            rt = AgentRuntime(
                agent_id=name,
                driver=driver,
                run_context=run_context,
                event_sink=self._event_sink,
                system_prompt=system_prompt,
                tool_registry=tool_registry,
            )
            runtimes[name] = rt

        return runtimes

    @staticmethod
    def _register_factories(resolver: BackendResolver) -> None:
        """Register driver factories for all supported provider types."""
        from miniautogen.backends.config import DriverType
        from miniautogen.backends.openai_sdk.factory import openai_sdk_factory
        from miniautogen.backends.anthropic_sdk.factory import anthropic_sdk_factory
        from miniautogen.backends.google_genai.factory import google_genai_factory
        from miniautogen.backends.agentapi.factory import agentapi_factory

        resolver.register_factory(DriverType.OPENAI_SDK, openai_sdk_factory)
        resolver.register_factory(DriverType.ANTHROPIC_SDK, anthropic_sdk_factory)
        resolver.register_factory(DriverType.GOOGLE_GENAI, google_genai_factory)
        resolver.register_factory(DriverType.AGENT_API, agentapi_factory)
