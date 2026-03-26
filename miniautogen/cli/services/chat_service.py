"""Chat service -- interactive multi-turn conversation with an agent.

Maintains conversation history across turns, reusing a single AgentRuntime.
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


def list_available_agents(project_root: Path) -> list[str]:
    """Return a list of agent names available in the workspace.

    Raises:
        ValueError: If no agents are found.
    """
    agent_specs = load_agent_specs(project_root)
    if not agent_specs:
        raise ValueError(
            "No agents found in workspace. "
            "Create one first: miniautogen agent create <name>"
        )
    return list(agent_specs.keys())


class ChatSession:
    """Interactive multi-turn chat session with an agent.

    Use the async ``create`` factory method to instantiate.
    """

    def __init__(
        self,
        *,
        agent_name: str,
        runtime: Any,
        run_id: str,
    ) -> None:
        self._agent_name = agent_name
        self._runtime = runtime
        self._run_id = run_id
        self._history: list[dict[str, str]] = []
        self._is_closed = False

    @classmethod
    async def create(
        cls,
        project_root: Path,
        agent_name: str | None = None,
    ) -> ChatSession:
        """Create a new chat session.

        Args:
            project_root: Path to the workspace root.
            agent_name: Agent name (defaults to first agent in workspace).

        Returns:
            An initialized ChatSession.

        Raises:
            ValueError: If no agents found or agent not found.
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
        run_id = f"chat-{uuid.uuid4().hex[:8]}"

        # Resolve engine -> driver
        engine_resolver = EngineResolver()
        engine_name = getattr(spec, "engine_profile", None) or config.defaults.engine
        driver = engine_resolver.create_fresh_driver(engine_name, config)

        # Create AgentRuntime
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

        await runtime.initialize()

        return cls(
            agent_name=agent_name,
            runtime=runtime,
            run_id=run_id,
        )

    async def send(self, message: str) -> str:
        """Send a message and return the agent response.

        Args:
            message: The user message to send.

        Returns:
            The agent's response text.

        Raises:
            RuntimeError: If the session is closed.
        """
        if self._is_closed:
            raise RuntimeError("Cannot send message: session is closed.")

        self._history.append({"role": "user", "content": message})

        response = await self._runtime.process(message)

        self._history.append({"role": "assistant", "content": response})

        return response

    def clear_history(self) -> None:
        """Clear the conversation history."""
        self._history.clear()

    async def close(self) -> None:
        """Close the session and release resources."""
        if not self._is_closed:
            self._is_closed = True
            await self._runtime.close()

    @property
    def history(self) -> list[dict[str, str]]:
        """Return the conversation history."""
        return list(self._history)

    @property
    def agent_name(self) -> str:
        """Return the agent name."""
        return self._agent_name

    @property
    def run_id(self) -> str:
        """Return the run ID."""
        return self._run_id

    @property
    def is_closed(self) -> bool:
        """Return whether the session is closed."""
        return self._is_closed
