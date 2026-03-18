"""AnthropicSDKDriver — direct Anthropic SDK integration.

Uses the official `anthropic` Python package with AsyncAnthropic.
Handles Anthropic's unique message format (system as separate param,
content as list of blocks).
"""

from __future__ import annotations

import uuid
from typing import Any, AsyncIterator

from miniautogen.backends.driver import AgentDriver
from miniautogen.backends.errors import CancelNotSupportedError, TurnExecutionError
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


class AnthropicSDKDriver(AgentDriver):
    """Driver using the official Anthropic Python SDK (AsyncAnthropic).

    Handles the Anthropic-specific message format:
    - System messages are extracted to a separate `system` parameter
    - Content blocks are normalized to text

    Args:
        client: An AsyncAnthropic instance (or mock for testing).
        model: Model identifier (e.g., "claude-sonnet-4-20250514").
        temperature: Sampling temperature.
        max_tokens: Maximum tokens in response (Anthropic requires this).
        timeout_seconds: Request timeout.
    """

    def __init__(
        self,
        client: Any,
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        timeout_seconds: float = 120.0,
    ) -> None:
        self._client = client
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout_seconds = timeout_seconds
        self._caps = BackendCapabilities(
            sessions=False,
            streaming=True,
            cancel=False,
            resume=False,
            tools=True,
            artifacts=False,
            multimodal=True,
        )

    async def start_session(
        self,
        request: StartSessionRequest,
    ) -> StartSessionResponse:
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        logger.info(
            "session_started",
            session_id=session_id,
            backend_id=request.backend_id,
            model=self._model,
        )
        return StartSessionResponse(
            session_id=session_id,
            capabilities=self._caps,
        )

    async def send_turn(
        self,
        request: SendTurnRequest,
    ) -> AsyncIterator[AgentEvent]:
        turn_id = f"turn_{uuid.uuid4().hex[:12]}"
        logger.debug("send_turn", session_id=request.session_id, turn_id=turn_id)

        yield AgentEvent(
            type="turn_started",
            session_id=request.session_id,
            turn_id=turn_id,
        )

        try:
            # Extract system message (Anthropic requires it as separate param)
            system_prompt, messages = self._transform_messages(request.messages)

            create_kwargs: dict[str, Any] = {
                "model": self._model,
                "messages": messages,
                "max_tokens": self._max_tokens,
                "temperature": self._temperature,
            }
            if system_prompt:
                create_kwargs["system"] = system_prompt

            response = await self._client.messages.create(**create_kwargs)

            # Extract text from content blocks
            text_parts = []
            for block in response.content:
                if hasattr(block, "text"):
                    text_parts.append(block.text)
            content = "\n".join(text_parts) if text_parts else ""

            yield AgentEvent(
                type="message_completed",
                session_id=request.session_id,
                turn_id=turn_id,
                payload={"text": content, "role": response.role},
            )

            completed_payload: dict[str, Any] = {}
            if hasattr(response, "model") and response.model:
                completed_payload["model"] = response.model
            if hasattr(response, "usage") and response.usage:
                completed_payload["usage"] = {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                }

            yield AgentEvent(
                type="turn_completed",
                session_id=request.session_id,
                turn_id=turn_id,
                payload=completed_payload,
            )

        except Exception as exc:
            logger.error("anthropic_sdk_error", error=str(exc), model=self._model)
            msg = f"Anthropic SDK error: {exc}"
            raise TurnExecutionError(msg) from exc

    def _transform_messages(
        self, messages: list[dict[str, Any]],
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """Extract system message and format for Anthropic API.

        Anthropic requires:
        - System message as a separate `system` parameter
        - No "system" role in the messages list

        Returns:
            Tuple of (system_prompt, filtered_messages).
        """
        system_parts: list[str] = []
        filtered: list[dict[str, Any]] = []

        for msg in messages:
            if msg.get("role") == "system":
                system_parts.append(msg.get("content", ""))
            else:
                filtered.append(msg)

        system_prompt = "\n".join(system_parts) if system_parts else None
        return system_prompt, filtered

    async def cancel_turn(
        self,
        request: CancelTurnRequest,
    ) -> None:
        raise CancelNotSupportedError(
            "AnthropicSDKDriver does not support cancellation",
        )

    async def list_artifacts(self, session_id: str) -> list[ArtifactRef]:
        return []

    async def close_session(self, session_id: str) -> None:
        pass

    async def capabilities(self) -> BackendCapabilities:
        return self._caps
