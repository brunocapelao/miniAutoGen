"""Tests for JSON resilience in AgentRuntime.review().

Validates that review() handles non-JSON and markdown-wrapped JSON responses
from backends without crashing, matching the behaviour of contribute().
"""

from __future__ import annotations

from typing import Any, AsyncIterator

import pytest

from miniautogen.backends.driver import AgentDriver
from miniautogen.backends.models import (
    AgentEvent,
    BackendCapabilities,
    SendTurnRequest,
    StartSessionRequest,
    StartSessionResponse,
)
from miniautogen.core.contracts.deliberation import Contribution
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.runtime.agent_runtime import AgentRuntime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run_context(run_id: str = "test-run") -> RunContext:
    from datetime import datetime, timezone

    return RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id="test-corr",
    )


class FakeDriver(AgentDriver):
    """Minimal fake driver that returns configurable text."""

    def __init__(self, response_text: str = "Hello from driver") -> None:
        self._response_text = response_text
        self._session_id = "fake-session-1"

    async def start_session(
        self, request: StartSessionRequest
    ) -> StartSessionResponse:
        return StartSessionResponse(
            session_id=self._session_id,
            capabilities=BackendCapabilities(sessions=True, streaming=True),
        )

    async def send_turn(  # type: ignore[override]
        self, request: SendTurnRequest
    ) -> AsyncIterator[AgentEvent]:
        yield AgentEvent(
            type="message_completed",
            session_id=request.session_id,
            turn_id="turn-1",
            payload={"text": self._response_text},
        )

    async def cancel_turn(self, request: Any) -> None:
        pass

    async def list_artifacts(self, session_id: str) -> list:
        return []

    async def close_session(self, session_id: str) -> None:
        pass

    async def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(sessions=True, streaming=True)


def _make_runtime(response_text: str) -> AgentRuntime:
    return AgentRuntime(
        agent_id="test-agent",
        driver=FakeDriver(response_text=response_text),
        event_sink=InMemoryEventSink(),
        run_context=_make_run_context(),
        system_prompt="You are a test agent.",
    )


def _make_contribution() -> Contribution:
    return Contribution(
        participant_id="other-agent",
        title="Test Contribution",
        content={"text": "Some content"},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestReviewJsonResilience:
    """review() must handle non-JSON backend responses gracefully."""

    @pytest.mark.anyio()
    async def test_review_handles_non_json_response(self) -> None:
        """Free text response should return a valid Review, not raise JSONDecodeError."""
        rt = _make_runtime("This looks good to me, no concerns.")
        await rt.initialize()
        contribution = _make_contribution()
        review = await rt.review(target_id="other-agent", contribution=contribution)
        await rt.close()

        assert review.reviewer_id == "test-agent"
        assert review.target_id == "other-agent"
        assert review.target_title == "Test Contribution"
        # free text should land in concerns
        assert isinstance(review.concerns, list)
        assert len(review.concerns) == 1
        assert "This looks good to me, no concerns." in review.concerns[0]

    @pytest.mark.anyio()
    async def test_review_handles_markdown_wrapped_json(self) -> None:
        """Markdown-fenced JSON should be extracted and parsed correctly."""
        response = (
            "```json\n"
            '{"strengths": ["clear logic"], "concerns": [], "questions": ["ETA?"]}\n'
            "```"
        )
        rt = _make_runtime(response)
        await rt.initialize()
        contribution = _make_contribution()
        review = await rt.review(target_id="other-agent", contribution=contribution)
        await rt.close()

        assert review.strengths == ["clear logic"]
        assert review.concerns == []
        assert review.questions == ["ETA?"]

    @pytest.mark.anyio()
    async def test_review_still_works_with_valid_json(self) -> None:
        """Regression: plain valid JSON should still be parsed correctly."""
        response = '{"strengths": ["well structured"], "concerns": ["too long"], "questions": []}'
        rt = _make_runtime(response)
        await rt.initialize()
        contribution = _make_contribution()
        review = await rt.review(target_id="other-agent", contribution=contribution)
        await rt.close()

        assert review.strengths == ["well structured"]
        assert review.concerns == ["too long"]
        assert review.questions == []
