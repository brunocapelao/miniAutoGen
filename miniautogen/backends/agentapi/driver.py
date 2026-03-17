"""AgentAPIDriver — HTTP bridge implementing the AgentDriver contract.

Connects to any OpenAI-compatible endpoint (/v1/chat/completions).
Uses AgentAPIClient for HTTP and ResponseMapper for event conversion.
"""

from __future__ import annotations

import uuid
from typing import AsyncIterator

from miniautogen.backends.agentapi.client import AgentAPIClient
from miniautogen.observability.logging import get_logger

logger = get_logger(__name__)
from miniautogen.backends.agentapi.mapper import map_completion_response
from miniautogen.backends.driver import AgentDriver
from miniautogen.backends.errors import CancelNotSupportedError
from miniautogen.backends.models import (
    AgentEvent,
    ArtifactRef,
    BackendCapabilities,
    CancelTurnRequest,
    SendTurnRequest,
    StartSessionRequest,
    StartSessionResponse,
)


class AgentAPIDriver(AgentDriver):
    """Driver for OpenAI-compatible HTTP endpoints.

    Works with any /v1/chat/completions backend: gemini_cli_gateway,
    LiteLLM proxy, vLLM, Ollama, etc.

    send_turn uses ``async def`` + ``yield`` (async generator),
    satisfying the ABC's ``def -> AsyncIterator`` contract (D1).
    """

    def __init__(
        self,
        client: AgentAPIClient,
        model: str | None = None,
        timeout_seconds: float = 120.0,
    ) -> None:
        self._client = client
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._caps = BackendCapabilities(
            sessions=False,
            streaming=False,
            cancel=False,
            resume=False,
            tools=False,
            artifacts=False,
            multimodal=False,
        )

    async def start_session(
        self,
        request: StartSessionRequest,
    ) -> StartSessionResponse:
        await self._client.health_check()
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        logger.info("session_started", session_id=session_id, backend_id=request.backend_id)
        return StartSessionResponse(
            session_id=session_id,
            capabilities=self._caps,
        )

    async def send_turn(
        self,
        request: SendTurnRequest,
    ) -> AsyncIterator[AgentEvent]:
        import anyio

        turn_id = f"turn_{uuid.uuid4().hex[:12]}"
        logger.debug("send_turn", session_id=request.session_id, turn_id=turn_id)
        with anyio.fail_after(self._timeout_seconds):
            response_data = await self._client.chat_completion(
                messages=request.messages,
                model=self._model,
            )
            events = map_completion_response(
                response_data,
                session_id=request.session_id,
                turn_id=turn_id,
            )
            for event in events:
                yield event

    async def cancel_turn(
        self,
        request: CancelTurnRequest,
    ) -> None:
        raise CancelNotSupportedError(
            "AgentAPIDriver does not support cancellation"
        )

    async def list_artifacts(self, session_id: str) -> list[ArtifactRef]:
        return []

    async def close_session(self, session_id: str) -> None:
        pass

    async def capabilities(self) -> BackendCapabilities:
        return self._caps
