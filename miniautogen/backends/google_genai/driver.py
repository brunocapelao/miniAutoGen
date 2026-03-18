"""GoogleGenAIDriver — direct Google GenAI SDK integration.

Uses the official `google-genai` Python package for Gemini models.
Handles Google's unique content format (parts-based).
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


class GoogleGenAIDriver(AgentDriver):
    """Driver using the official Google GenAI Python SDK.

    Args:
        client: A google.genai.Client instance (or mock for testing).
        model: Model identifier (e.g., "gemini-2.5-pro").
        temperature: Sampling temperature.
        max_tokens: Maximum output tokens.
        timeout_seconds: Request timeout.
    """

    def __init__(
        self,
        client: Any,
        model: str,
        temperature: float = 0.2,
        max_tokens: int | None = None,
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
            # Transform messages to Google format
            contents = self._transform_messages(request.messages)

            config_kwargs: dict[str, Any] = {
                "temperature": self._temperature,
            }
            if self._max_tokens is not None:
                config_kwargs["max_output_tokens"] = self._max_tokens

            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=contents,
                config=config_kwargs,
            )

            content = response.text or ""

            yield AgentEvent(
                type="message_completed",
                session_id=request.session_id,
                turn_id=turn_id,
                payload={"text": content, "role": "assistant"},
            )

            completed_payload: dict[str, Any] = {"model": self._model}
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                usage = response.usage_metadata
                completed_payload["usage"] = {
                    "prompt_tokens": getattr(usage, "prompt_token_count", 0),
                    "completion_tokens": getattr(usage, "candidates_token_count", 0),
                    "total_tokens": getattr(usage, "total_token_count", 0),
                }

            yield AgentEvent(
                type="turn_completed",
                session_id=request.session_id,
                turn_id=turn_id,
                payload=completed_payload,
            )

        except Exception as exc:
            logger.error("google_genai_error", error=str(exc), model=self._model)
            msg = f"Google GenAI SDK error: {exc}"
            raise TurnExecutionError(msg) from exc

    def _transform_messages(
        self, messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Transform internal messages to Google GenAI format.

        Google uses 'user' and 'model' roles (not 'assistant').
        System messages are prepended to the first user message.
        """
        system_parts: list[str] = []
        transformed: list[dict[str, Any]] = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                system_parts.append(content)
                continue

            # Map OpenAI roles to Google roles
            google_role = "model" if role == "assistant" else "user"

            # Prepend system prompt to first user message
            if google_role == "user" and system_parts:
                content = "\n".join(system_parts) + "\n\n" + content
                system_parts = []

            transformed.append({
                "role": google_role,
                "parts": [{"text": content}],
            })

        return transformed

    async def cancel_turn(
        self,
        request: CancelTurnRequest,
    ) -> None:
        raise CancelNotSupportedError(
            "GoogleGenAIDriver does not support cancellation",
        )

    async def list_artifacts(self, session_id: str) -> list[ArtifactRef]:
        return []

    async def close_session(self, session_id: str) -> None:
        pass

    async def capabilities(self) -> BackendCapabilities:
        return self._caps
