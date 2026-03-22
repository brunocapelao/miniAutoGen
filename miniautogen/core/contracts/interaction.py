"""InteractionStrategy protocol — pluggable prompt construction and response parsing.

Enables advanced customization of how AgentRuntime interacts with agents.
Part of the cascade resolution: InteractionStrategy -> YAML templates -> defaults.

See docs/superpowers/specs/2026-03-21-agentruntime-agnostic-design.md
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class InteractionStrategy(Protocol):
    """Protocol for customizing prompt construction and response parsing.

    Inject via Python for advanced cases (multi-modal, tool calling, custom parsing).
    First in cascade resolution: InteractionStrategy -> YAML templates -> defaults.
    """

    async def build_prompt(self, action: str, context: dict[str, Any]) -> str:
        """Construct the prompt for a coordination action (contribute, review, etc.).

        Args:
            action: The coordination action name (e.g., "contribute", "review",
                    "consolidate", "produce_final_document", "route").
            context: Action-specific context dict. Keys vary by action:
                - contribute: {"topic": str}
                - review: {"target_id": str, "contribution": Contribution}
                - consolidate: {"topic": str, "contributions": list, "reviews": list}
                - produce_final_document: {"state": DeliberationState, "contributions": list}
                - route: {"conversation_history": list}

        Returns:
            The constructed prompt string.
        """
        ...

    async def parse_response(self, action: str, raw: str) -> Any:
        """Parse the agent's raw response into the expected structure.

        Args:
            action: The coordination action name.
            raw: The raw text response from the agent/driver.

        Returns:
            Parsed response. Type depends on action:
                - contribute: dict with title/content
                - review: dict with strengths/concerns/questions
                - consolidate: dict with accepted_facts/open_conflicts/etc.
                - produce_final_document: dict with executive_summary/etc.
                - route: dict with next_agent/terminate/etc.
        """
        ...
