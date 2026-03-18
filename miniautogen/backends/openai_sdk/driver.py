"""OpenAISDKDriver — direct OpenAI SDK integration.

Uses the official `openai` Python package with AsyncOpenAI for
non-streaming chat completions. Lighter than httpx-based AgentAPIDriver
and supports all OpenAI features natively.
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


class OpenAISDKDriver(AgentDriver):
    """Driver using the official OpenAI Python SDK (AsyncOpenAI).

    Supports: chat completions, tool calling, streaming (future).
    Does NOT manage sessions (stateless per-call).

    Args:
        client: An AsyncOpenAI instance (or mock for testing).
        model: Model identifier (e.g., "gpt-4o", "gpt-4o-mini").
        temperature: Sampling temperature.
        max_tokens: Maximum tokens in response.
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
            create_kwargs: dict[str, Any] = {
                "model": self._model,
                "messages": request.messages,
                "temperature": self._temperature,
            }
            if self._max_tokens is not None:
                create_kwargs["max_tokens"] = self._max_tokens

            response = await self._client.chat.completions.create(**create_kwargs)

            choice = response.choices[0]
            content = choice.message.content or ""
            role = choice.message.role or "assistant"

            yield AgentEvent(
                type="message_completed",
                session_id=request.session_id,
                turn_id=turn_id,
                payload={"text": content, "role": role},
            )

            # Build turn_completed payload with usage info
            completed_payload: dict[str, Any] = {}
            if hasattr(response, "model") and response.model:
                completed_payload["model"] = response.model
            if hasattr(response, "usage") and response.usage:
                completed_payload["usage"] = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }

            yield AgentEvent(
                type="turn_completed",
                session_id=request.session_id,
                turn_id=turn_id,
                payload=completed_payload,
            )

        except Exception as exc:
            logger.error("openai_sdk_error", error=str(exc), model=self._model)
            msg = f"OpenAI SDK error: {exc}"
            raise TurnExecutionError(msg) from exc

    async def cancel_turn(
        self,
        request: CancelTurnRequest,
    ) -> None:
        raise CancelNotSupportedError(
            "OpenAISDKDriver does not support cancellation",
        )

    async def list_artifacts(self, session_id: str) -> list[ArtifactRef]:
        return []

    async def close_session(self, session_id: str) -> None:
        pass

    async def capabilities(self) -> BackendCapabilities:
        return self._caps
