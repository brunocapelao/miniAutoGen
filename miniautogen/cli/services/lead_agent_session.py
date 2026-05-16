"""LeadAgentSession — unified session for the lead agent.

Combines:
1. Multi-turn chat (from ChatSession)
2. Workspace management tools (agents, flows, engines)
3. Event awareness (InMemoryEventSink + query tool)

The lead agent can inspect and modify the workspace, run flows,
and receive events — all through a single chat session.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from miniautogen.api import (
    AgentRuntime,
    CompositeToolRegistry,
    EventType,
    ExecutionEvent,
    InMemoryEventSink,
    InMemoryToolRegistry,
    ToolDefinition,
    ToolResult,
    build_workspace_tools,
)
from miniautogen.cli.services.runtime_factory import create_runtime


class LeadAgentSession:
    """Unified lead agent session with workspace tools and event awareness.

    Usage::

        session = await LeadAgentSession.create(project_root, "tech_lead")
        response = await session.send("List all agents")
        events = session.recent_events
        await session.close()
    """

    def __init__(
        self,
        *,
        agent_name: str,
        runtime: AgentRuntime,
        run_id: str,
        event_sink: InMemoryEventSink,
    ) -> None:
        self._agent_name = agent_name
        self._runtime = runtime
        self._run_id = run_id
        self._event_sink = event_sink
        self._history: list[dict[str, str]] = []
        self._is_closed = False

    @classmethod
    async def create(
        cls,
        project_root: Path,
        agent_name: str | None = None,
        *,
        run_id_prefix: str = "lead",
    ) -> LeadAgentSession:
        """Create a new lead agent session.

        Args:
            project_root: Path to the workspace root.
            agent_name: Agent name (defaults to first agent in workspace).
            run_id_prefix: Prefix for the auto-generated run ID.

        Returns:
            An initialized LeadAgentSession with workspace tools
            and event awareness injected.
        """
        from miniautogen.cli.services.agent_ops import load_agent_specs

        if agent_name is None:
            agent_specs = load_agent_specs(project_root)
            if not agent_specs:
                raise ValueError("No agents found in workspace")
            agent_name = next(iter(agent_specs))

        event_sink = InMemoryEventSink()

        runtime, run_id = await create_runtime(
            project_root, agent_name, run_id_prefix,
            event_sink=event_sink,
        )

        _inject_workspace_tools(runtime, project_root)
        _inject_event_tools(runtime, event_sink)

        return cls(
            agent_name=agent_name,
            runtime=runtime,
            run_id=run_id,
            event_sink=event_sink,
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

        event = ExecutionEvent(
            type=EventType.COMPONENT_STARTED.value,
            run_id=self._run_id,
            payload={"agent_id": self._agent_name, "message": message},
        )
        await self._event_sink.publish(event)

        self._history.append({"role": "user", "content": message})

        response = await self._runtime.process(message)

        self._history.append({"role": "assistant", "content": response})

        event = ExecutionEvent(
            type=EventType.COMPONENT_FINISHED.value,
            run_id=self._run_id,
            payload={"agent_id": self._agent_name},
        )
        await self._event_sink.publish(event)

        return response

    def clear_history(self) -> None:
        self._history.clear()

    async def close(self) -> None:
        if not self._is_closed:
            self._is_closed = True
            await self._runtime.close()

    @property
    def history(self) -> list[dict[str, str]]:
        return list(self._history)

    @property
    def agent_name(self) -> str:
        return self._agent_name

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def is_closed(self) -> bool:
        return self._is_closed

    @property
    def recent_events(self) -> list[ExecutionEvent]:
        """Return all events captured during this session."""
        return list(self._event_sink.events)


# ---------------------------------------------------------------------------
# Tool injection helpers
# ---------------------------------------------------------------------------


def _inject_workspace_tools(runtime: AgentRuntime, project_root: Path) -> None:
    """Inject workspace management tools into the agent's tool registry."""
    registry = InMemoryToolRegistry()
    for definition, handler in build_workspace_tools(project_root):
        registry.register(definition, handler)

    existing = getattr(runtime, "tool_registry", None)
    if existing is not None:
        if isinstance(existing, CompositeToolRegistry):
            existing._registries = list(existing._registries) + [registry]
        else:
            runtime.tool_registry = CompositeToolRegistry([existing, registry])
    else:
        runtime.tool_registry = registry


def _inject_event_tools(runtime: AgentRuntime, event_sink: InMemoryEventSink) -> None:
    """Inject event awareness tools into the agent's tool registry."""
    registry = InMemoryToolRegistry()
    registry.register(
        ToolDefinition(
            name="get_events",
            description="Get recent execution events for awareness. "
                        "Filter by event_type (e.g. 'run_started', 'run_finished', "
                        "'run_failed', 'component_finished', 'tool_invoked'). "
                        "Returns events sorted newest-first.",
            parameters={
                "type": "object",
                "properties": {
                    "event_type": {
                        "type": "string",
                        "description": "Optional event type filter",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max events to return (default 20)",
                    },
                },
            },
        ),
        _make_get_events_handler(event_sink),
    )

    existing = getattr(runtime, "tool_registry", None)
    if existing is not None:
        if isinstance(existing, CompositeToolRegistry):
            existing._registries = list(existing._registries) + [registry]
        else:
            runtime.tool_registry = CompositeToolRegistry([existing, registry])
    else:
        runtime.tool_registry = registry


def _make_get_events_handler(event_sink: InMemoryEventSink) -> Any:
    async def handler(params: dict[str, Any]) -> ToolResult:
        event_type_filter = params.get("event_type")
        limit = int(params.get("limit", 20))

        events = list(event_sink.events)
        if event_type_filter:
            events = [e for e in events if e.type == event_type_filter]

        events.reverse()
        events = events[:limit]

        return ToolResult(
            success=True,
            output={
                "events": [
                    {
                        "type": e.type,
                        "timestamp": e.timestamp.isoformat(),
                        "run_id": e.run_id,
                        "payload": e.payload_dict(),
                    }
                    for e in events
                ],
                "total": len(events),
            },
        )

    return handler
