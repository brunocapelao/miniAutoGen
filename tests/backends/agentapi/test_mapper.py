"""Tests for OpenAI response -> AgentEvent mapper."""

from __future__ import annotations

import pytest

from miniautogen.backends.agentapi.mapper import (
    map_completion_response,
    extract_error_message,
)
from miniautogen.backends.errors import EventMappingError
from miniautogen.backends.models import AgentEvent


class TestMapCompletionResponse:
    def test_standard_response(self) -> None:
        data = {
            "choices": [
                {"message": {"role": "assistant", "content": "Hello world"}}
            ],
        }
        events = map_completion_response(data, session_id="s1", turn_id="t1")
        assert len(events) == 3
        assert events[0].type == "turn_started"
        assert events[0].session_id == "s1"
        assert events[0].turn_id == "t1"
        assert events[1].type == "message_completed"
        assert events[1].payload["text"] == "Hello world"
        assert events[1].payload["role"] == "assistant"
        assert events[2].type == "turn_completed"

    def test_response_with_model_and_usage(self) -> None:
        data = {
            "choices": [
                {"message": {"role": "assistant", "content": "Hi"}}
            ],
            "model": "gemini-2.5-pro",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        events = map_completion_response(data, session_id="s1", turn_id="t1")
        completed = events[2]  # turn_completed
        assert completed.payload.get("model") == "gemini-2.5-pro"
        assert completed.payload.get("usage") == {
            "prompt_tokens": 10, "completion_tokens": 5,
        }

    def test_missing_choices_raises(self) -> None:
        with pytest.raises(EventMappingError, match="choices"):
            map_completion_response({}, session_id="s1", turn_id="t1")

    def test_empty_choices_raises(self) -> None:
        with pytest.raises(EventMappingError, match="choices"):
            map_completion_response(
                {"choices": []}, session_id="s1", turn_id="t1",
            )

    def test_missing_message_content_raises(self) -> None:
        data = {"choices": [{"message": {"role": "assistant"}}]}
        with pytest.raises(EventMappingError, match="content"):
            map_completion_response(data, session_id="s1", turn_id="t1")

    def test_all_events_have_timestamps(self) -> None:
        data = {
            "choices": [
                {"message": {"role": "assistant", "content": "ok"}}
            ],
        }
        events = map_completion_response(data, session_id="s1", turn_id="t1")
        for ev in events:
            assert ev.timestamp is not None


class TestExtractErrorMessage:
    def test_openai_error_format(self) -> None:
        body = {"error": {"message": "Rate limit exceeded"}}
        assert extract_error_message(body) == "Rate limit exceeded"

    def test_detail_format(self) -> None:
        body = {"detail": "Not found"}
        assert extract_error_message(body) == "Not found"

    def test_message_format(self) -> None:
        body = {"message": "Internal error"}
        assert extract_error_message(body) == "Internal error"

    def test_fallback_to_str(self) -> None:
        body = {"unknown": "format"}
        result = extract_error_message(body)
        assert "unknown" in result

    def test_non_dict_body(self) -> None:
        result = extract_error_message("plain text error")
        assert result == "plain text error"
