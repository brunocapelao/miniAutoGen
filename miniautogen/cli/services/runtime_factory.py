"""Runtime factory helpers for CLI entrypoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from miniautogen.api import (
    AgentRuntime,
    EngineResolver,
    EventSink,
    NullEventSink,
    RunContext,
)
from miniautogen.cli.config import CONFIG_FILENAME, load_config
from miniautogen.cli.services.agent_ops import load_agent_specs


async def create_runtime(
    project_root: Path,
    agent_name: str,
    run_id_prefix: str = "run",
    system_prompt: str = "",
    *,
    event_sink: EventSink | None = None,
) -> tuple[AgentRuntime, str]:
    """Load agent config, create driver, build and initialize AgentRuntime.

    Args:
        project_root: Path to the workspace root.
        agent_name: Name of the agent to use.
        run_id_prefix: Prefix for the auto-generated run ID.
        system_prompt: Optional override. Falls back to agent spec goal.
        event_sink: Optional event sink for observability. Defaults to NullEventSink.

    Returns:
        Tuple of (initialized AgentRuntime, run_id).

    Raises:
        ValueError: If agent not found.
    """
    config = load_config(project_root / CONFIG_FILENAME)
    agent_specs = load_agent_specs(project_root)
    if agent_name not in agent_specs:
        available = ", ".join(agent_specs.keys())
        raise ValueError(f"Agent '{agent_name}' not found. Available: {available}")

    spec = agent_specs[agent_name]
    run_id = f"{run_id_prefix}-{uuid.uuid4().hex[:8]}"

    engine_resolver = EngineResolver()
    engine_name = getattr(spec, "engine_profile", None) or config.defaults.engine
    driver = engine_resolver.create_fresh_driver(engine_name, config)

    run_context = RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id=run_id,
    )

    runtime = AgentRuntime(
        agent_id=agent_name,
        driver=driver,
        run_context=run_context,
        event_sink=event_sink or NullEventSink(),
        system_prompt=system_prompt or getattr(spec, "goal", None) or "",
    )
    await runtime.initialize()
    return runtime, run_id
