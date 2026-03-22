"""One-liner convenience function for quick agent execution.

Abstracts the full MiniAutoGen setup into a single async call,
ideal for notebooks and rapid prototyping.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.run_result import RunResult
from miniautogen.core.contracts.enums import RunStatus


async def quick_run(
    *,
    agent: str = "gpt-4o",
    task: str,
    tools: list[Any] | None = None,
    system_prompt: str | None = None,
    temperature: float = 0.2,
    max_tokens: int | None = None,
    api_key: str | None = None,
    provider: str = "openai",
    endpoint: str | None = None,
    timeout_seconds: float = 120.0,
) -> RunResult:
    """Execute a single agent task with minimal configuration.

    This is the simplest entry point to MiniAutoGen. No YAML, no workspace,
    no engine profiles — just specify the model, the task, and go.

    Args:
        agent: Model identifier (e.g., "gpt-4o", "claude-3-5-sonnet").
        task: The task/prompt to send to the agent.
        tools: Optional list of tool instances to make available.
        system_prompt: Optional system prompt for the agent.
        temperature: Sampling temperature.
        max_tokens: Maximum tokens in response.
        api_key: API key (reads from env if not provided).
        provider: Provider name ("openai", "anthropic", "google").
        endpoint: Custom API endpoint URL.
        timeout_seconds: Request timeout.

    Returns:
        RunResult with the agent's output.

    Example::

        result = await quick_run(agent="gpt-4o", task="Explain quantum computing")
        print(result.output)
    """
    from miniautogen.scripting.builder import ScriptBuilder

    builder = ScriptBuilder()
    builder.add_agent(
        "default",
        model=agent,
        role="assistant",
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=api_key,
        provider=provider,
        endpoint=endpoint,
        timeout_seconds=timeout_seconds,
    )

    if tools:
        for tool in tools:
            builder.add_tool("default", tool)

    return await builder.single_run("default", input=task)
