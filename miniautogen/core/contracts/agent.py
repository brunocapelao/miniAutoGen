"""Agent capability protocols for the Side C architecture.

Defines the structural contracts (Protocols) that agents must satisfy
to participate in each coordination mode.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from miniautogen.core.contracts.agentic_loop import RouterDecision
from miniautogen.core.contracts.deliberation import Contribution, Review


@runtime_checkable
class WorkflowAgent(Protocol):
    """Agent that can participate in workflow coordination."""

    async def process(self, input: Any) -> Any: ...


@runtime_checkable
class DeliberationAgent(Protocol):
    """Agent that can participate in deliberation coordination."""

    async def contribute(self, topic: str) -> Contribution: ...
    async def review(self, target_id: str, contribution: Contribution) -> Review: ...


@runtime_checkable
class ConversationalAgent(Protocol):
    """Agent that can participate in agentic loop coordination."""

    async def reply(self, message: str, context: dict[str, Any]) -> str: ...
    async def route(self, conversation_history: list[Any]) -> RouterDecision: ...
