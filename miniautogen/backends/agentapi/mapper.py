"""Convert OpenAI-compatible JSON responses to canonical AgentEvent sequences.

This module handles data transformation only — no HTTP logic.
Structured with separate functions to support future streaming (SSE).
"""

from __future__ import annotations

from typing import Any

from miniautogen.backends.errors import EventMappingError
from miniautogen.backends.models import AgentEvent


def map_completion_response(
    response_data: dict[str, Any],
    session_id: str,
    turn_id: str,
) -> list[AgentEvent]:
    """Convert a non-streaming chat completion response to canonical events.

    Returns: [turn_started, message_completed, turn_completed]

    Raises EventMappingError if the response is malformed.
    """
    choices = response_data.get("choices")
    if not choices:
        msg = "Response missing 'choices' or choices is empty"
        raise EventMappingError(msg)

    first_choice = choices[0]
    message = first_choice.get("message", {})
    content = message.get("content")
    if content is None:
        msg = "Response missing 'content' in first choice message"
        raise EventMappingError(msg)

    role = message.get("role", "assistant")
    model = response_data.get("model")
    usage = response_data.get("usage")

    turn_completed_payload: dict[str, Any] = {}
    if model:
        turn_completed_payload["model"] = model
    if usage:
        turn_completed_payload["usage"] = usage

    return [
        AgentEvent(
            type="turn_started",
            session_id=session_id,
            turn_id=turn_id,
        ),
        AgentEvent(
            type="message_completed",
            session_id=session_id,
            turn_id=turn_id,
            payload={"text": content, "role": role},
        ),
        AgentEvent(
            type="turn_completed",
            session_id=session_id,
            turn_id=turn_id,
            payload=turn_completed_payload,
        ),
    ]


def extract_error_message(body: Any) -> str:
    """Extract a human-readable error message from an HTTP error response body.

    Tries common formats: OpenAI (error.message), FastAPI (detail), generic (message).
    Falls back to str(body).
    """
    if not isinstance(body, dict):
        return str(body)

    error = body.get("error")
    if isinstance(error, dict) and "message" in error:
        return error["message"]

    if "detail" in body:
        return str(body["detail"])

    if "message" in body:
        return str(body["message"])

    return str(body)
