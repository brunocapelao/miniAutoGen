"""Message transformation protocol for backend drivers.

Each SDK driver implements its own transformer to convert between
MiniAutoGen's internal message format and the provider's native format.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from miniautogen.backends.models import AgentEvent


@runtime_checkable
class MessageTransformer(Protocol):
    """Converts between internal message format and provider-specific format.

    Drivers that need message transformation implement this protocol.
    The BaseDriver wrapper uses it for pre/post processing.
    """

    def to_provider(self, messages: list[dict[str, Any]]) -> Any:
        """Convert internal messages to provider-native format.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.

        Returns:
            Provider-specific message format (varies by provider).
        """
        ...

    def from_provider(
        self, response: Any, session_id: str, turn_id: str,
    ) -> list[AgentEvent]:
        """Convert provider response to canonical AgentEvents.

        Args:
            response: Raw response from the provider SDK.
            session_id: Current session identifier.
            turn_id: Current turn identifier.

        Returns:
            List of AgentEvent objects in canonical format.
        """
        ...
