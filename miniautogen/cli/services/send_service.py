"""Send service -- execute a single agent turn without a full pipeline run.

Creates a temporary AgentRuntime, sends one message, returns the response.
Emits ExecutionEvents for observability.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from miniautogen.cli.config import load_config, CONFIG_FILENAME
from miniautogen.cli.services.agent_ops import load_agent_specs
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.events.event_sink import NullEventSink


async def send_message(
    project_root: Path,
    message: str,
    *,
    agent_name: str | None = None,
    output_format: str = "text",
) -> dict[str, Any]:
    """Send a single message to an agent and return the response.

    Args:
        project_root: Path to the workspace root.
        message: The message to send.
        agent_name: Agent name (defaults to first agent in workspace).
        output_format: "text" or "json".

    Returns:
        Dict with keys: agent, message, response, run_id.

    Raises:
        ValueError: If no agents found or agent not found.
        RuntimeError: If agent execution fails.
    """
    from miniautogen.backends.engine_resolver import EngineResolver
    from miniautogen.core.runtime.agent_runtime import AgentRuntime

    config = load_config(project_root / CONFIG_FILENAME)

    # Resolve agent
    agent_specs = load_agent_specs(project_root)
    if not agent_specs:
        raise ValueError(
            "No agents found in workspace. "
            "Create one first: miniautogen agent create <name>"
        )

    if agent_name is None:
        agent_name = next(iter(agent_specs))
    elif agent_name not in agent_specs:
        available = ", ".join(agent_specs.keys())
        raise ValueError(
            f"Agent '{agent_name}' not found. Available: {available}"
        )

    spec = agent_specs[agent_name]
    run_id = f"send-{uuid.uuid4().hex[:8]}"

    # Resolve engine -> driver
    engine_resolver = EngineResolver()
    engine_name = getattr(spec, "engine_profile", None) or config.defaults.engine
    driver = engine_resolver.create_fresh_driver(engine_name, config)

    # Create temporary AgentRuntime
    run_context = RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id=run_id,
    )

    runtime = AgentRuntime(
        agent_id=agent_name,
        driver=driver,
        run_context=run_context,
        event_sink=NullEventSink(),
        system_prompt=getattr(spec, "goal", None) or "",
    )

    try:
        await runtime.initialize()
        response = await runtime.process(message)
    finally:
        await runtime.close()

    return {
        "agent": agent_name,
        "message": message,
        "response": response,
        "run_id": run_id,
    }
