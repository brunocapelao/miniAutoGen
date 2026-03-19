"""MemoryProvider protocol for the Agent Runtime layer.

Defines the abstraction for agent memory: session-scoped context
retrieval, turn persistence, and distillation.

MemoryProvider is injectable and optional -- agents operate normally
without it (this is an invariant, see 05-invariantes.md).

See docs/pt/architecture/07-agent-anatomy.md section 6.2.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from miniautogen.core.contracts.run_context import RunContext


@runtime_checkable
class MemoryProvider(Protocol):
    """Abstraction for agent memory.

    All methods are async (AnyIO invariant).
    """

    async def get_context(
        self,
        agent_id: str,
        context: RunContext,
        max_tokens: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return relevant memory messages for the current context.

        If max_tokens is specified, limit the returned messages to
        approximately that token count (implementation-dependent).
        """
        ...

    async def save_turn(
        self,
        messages: list[dict[str, Any]],
        context: RunContext,
    ) -> None:
        """Persist a turn's messages in memory."""
        ...

    async def distill(
        self,
        agent_id: str,
    ) -> None:
        """Distill short-term memory into long-term memory.

        Implementation may be a no-op for simple providers.
        """
        ...


class InMemoryMemoryProvider:
    """Default in-memory implementation of MemoryProvider.

    Dict-based, session-scoped (keyed by run_id). Data is lost
    when the process exits. Suitable for testing and short-lived
    sessions.
    """

    def __init__(self) -> None:
        # Keyed by run_id -> list of messages
        self._store: dict[str, list[dict[str, Any]]] = {}

    async def get_context(
        self,
        agent_id: str,
        context: RunContext,
        max_tokens: int | None = None,
    ) -> list[dict[str, Any]]:
        messages = list(self._store.get(context.run_id, []))
        if max_tokens is not None and max_tokens > 0:
            # Simple token estimate: ~4 chars per token
            result: list[dict[str, Any]] = []
            token_count = 0
            for msg in reversed(messages):
                content = msg.get("content", "")
                estimated_tokens = len(str(content)) // 4 + 1
                if token_count + estimated_tokens > max_tokens:
                    break
                result.insert(0, msg)
                token_count += estimated_tokens
            return result
        return messages

    async def save_turn(
        self,
        messages: list[dict[str, Any]],
        context: RunContext,
    ) -> None:
        if context.run_id not in self._store:
            self._store[context.run_id] = []
        self._store[context.run_id].extend(messages)

    async def distill(self, agent_id: str) -> None:
        # No-op for in-memory provider
        pass
