"""Send service -- execute a single agent turn without a full pipeline run.

Creates a temporary AgentRuntime, sends one message, returns the response.
Emits ExecutionEvents for observability.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from miniautogen.cli.services.agent_ops import load_agent_specs
from miniautogen.cli.services.runtime_factory import create_runtime


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
    if agent_name is None:
        agent_specs = load_agent_specs(project_root)
        if not agent_specs:
            raise ValueError(
                "No agents found in workspace. "
                "Create one first: miniautogen agent create <name>"
            )
        agent_name = next(iter(agent_specs))

    runtime, run_id = await create_runtime(
        project_root, agent_name, "send",
    )
    try:
        response = await runtime.process(message)
    finally:
        await runtime.close()

    return {
        "agent": agent_name,
        "message": message,
        "response": response,
        "run_id": run_id,
    }
