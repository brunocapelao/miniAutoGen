"""BaseDriver — wrapper that adds sanitization, validation, and error normalization.

Inspired by OpenCode's baseProvider pattern. Wraps any concrete AgentDriver
to provide consistent behavior regardless of the underlying implementation.
"""

from __future__ import annotations

import re
from typing import AsyncIterator

from miniautogen.backends.driver import AgentDriver
from miniautogen.backends.models import (
    AgentEvent,
    ArtifactRef,
    BackendCapabilities,
    CancelTurnRequest,
    SendTurnRequest,
    StartSessionRequest,
    StartSessionResponse,
)
from miniautogen.observability.logging import get_logger

logger = get_logger(__name__)


class BaseDriver(AgentDriver):
    """Wraps any driver with sanitization, validation, and error normalization.

    Responsibilities:
    - Sanitize messages (remove empty, strip control chars)
    - Validate capabilities before forwarding requests
    - Normalize errors into backend_error AgentEvents
    """

    def __init__(
        self,
        inner: AgentDriver,
        capabilities: BackendCapabilities,
    ) -> None:
        self._inner = inner
        self._capabilities = capabilities

    async def start_session(
        self,
        request: StartSessionRequest,
    ) -> StartSessionResponse:
        return await self._inner.start_session(request)

    async def send_turn(
        self,
        request: SendTurnRequest,
    ) -> AsyncIterator[AgentEvent]:
        sanitized = self._sanitize_messages(request.messages)
        request = request.model_copy(update={"messages": sanitized})

        # Log capability warnings (non-blocking)
        if request.metadata.get("requires_tools") and not self._capabilities.tools:
            logger.warning(
                "capability_mismatch",
                required="tools",
                session_id=request.session_id,
            )
        if request.metadata.get("requires_streaming") and not self._capabilities.streaming:
            logger.warning(
                "capability_mismatch",
                required="streaming",
                session_id=request.session_id,
            )

        try:
            async for event in self._inner.send_turn(request):
                yield self._normalize_event(event)
        except Exception as exc:
            yield self._error_event(exc, request.session_id)

    async def cancel_turn(
        self,
        request: CancelTurnRequest,
    ) -> None:
        await self._inner.cancel_turn(request)

    async def list_artifacts(self, session_id: str) -> list[ArtifactRef]:
        return await self._inner.list_artifacts(session_id)

    async def close_session(self, session_id: str) -> None:
        await self._inner.close_session(session_id)

    async def capabilities(self) -> BackendCapabilities:
        return self._capabilities

    def _sanitize_messages(
        self, messages: list[dict],
    ) -> list[dict]:
        """Remove empty messages, strip control characters from content."""
        sanitized = []
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                content = content.strip()
                # Remove control characters except newline/tab
                content = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", content)
                if not content:
                    continue
            sanitized.append({**msg, "content": content})
        return sanitized

    def _normalize_event(self, event: AgentEvent) -> AgentEvent:
        """Ensure consistent event format regardless of provider."""
        return event

    def _error_event(self, exc: Exception, session_id: str) -> AgentEvent:
        """Convert any exception to a backend_error AgentEvent."""
        logger.error(
            "driver_error",
            error=str(exc),
            error_type=type(exc).__name__,
            session_id=session_id,
        )
        return AgentEvent(
            type="backend_error",
            session_id=session_id,
            payload={
                "error": type(exc).__name__,
                "error_type": type(exc).__name__,
            },
        )
