"""Integration tests for AgentRuntime agnostic design.

Validates the three cascade resolution levels and backward compatibility.
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
from miniautogen.core.contracts.deliberation import Contribution, Review
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.runtime.agent_runtime import AgentRuntime


def _make_run_context() -> RunContext:
    from datetime import datetime, timezone

    return RunContext(
        run_id="integration-test",
        started_at=datetime.now(timezone.utc),
        correlation_id="int-corr",
    )


class EchoDriver(AgentDriver):
    """Driver that echoes the user prompt back — useful for testing prompt construction."""

    async def start_session(self, request: StartSessionRequest) -> StartSessionResponse:
        return StartSessionResponse(
            session_id="echo-session",
            capabilities=BackendCapabilities(sessions=True, streaming=True),
        )

    async def send_turn(self, request: SendTurnRequest) -> AsyncIterator[AgentEvent]:
        # Return the last user message content as response
        user_msg = ""
        for msg in reversed(request.messages):
            if msg.get("role") == "user":
                user_msg = msg.get("content", "")
                break
        yield AgentEvent(
            type="message_completed",
            session_id=request.session_id,
            turn_id="echo-turn",
            payload={"text": user_msg},
        )

    async def cancel_turn(self, request: Any) -> None:
        pass

    async def list_artifacts(self, session_id: str) -> list:
        return []

    async def close_session(self, session_id: str) -> None:
        pass

    async def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(sessions=True, streaming=True)


class TestCascadeResolutionIntegration:
    """End-to-end tests for cascade prompt resolution in AgentRuntime."""

    @pytest.mark.anyio()
    async def test_execute_returns_raw_string(self) -> None:
        """execute() should pass prompt to driver and return raw response."""
        rt = AgentRuntime(
            agent_id="test",
            driver=EchoDriver(),
            run_context=_make_run_context(),
        )
        await rt.initialize()
        result = await rt.execute("Hello world")
        assert result == "Hello world"
        await rt.close()

    @pytest.mark.anyio()
    async def test_contribute_with_yaml_prompt(self) -> None:
        """YAML template should replace the default prompt."""
        rt = AgentRuntime(
            agent_id="test",
            driver=EchoDriver(),
            run_context=_make_run_context(),
            flow_prompts={"contribute": "Custom: discuss {topic} now."},
        )
        await rt.initialize()
        contrib = await rt.contribute("AI safety")
        # EchoDriver echoes the prompt back as response text
        # Since it's not JSON, it wraps as free text
        assert contrib.content["text"] == "Custom: discuss AI safety now."
        await rt.close()

    @pytest.mark.anyio()
    async def test_contribute_with_strategy(self) -> None:
        """InteractionStrategy should take priority over YAML and default.

        When an InteractionStrategy is provided, both build_prompt() and
        parse_response() are used — the strategy controls the full cycle.
        """

        class PriorityStrategy:
            async def build_prompt(self, action: str, context: dict) -> str:
                return f"STRATEGY:{action}:{context.get('topic', '')}"

            async def parse_response(self, action: str, raw: str) -> Any:
                return {"title": f"Parsed:{action}", "content": {"raw": raw}}

        rt = AgentRuntime(
            agent_id="test",
            driver=EchoDriver(),
            run_context=_make_run_context(),
            interaction_strategy=PriorityStrategy(),
            flow_prompts={"contribute": "YAML {topic}"},
        )
        await rt.initialize()
        contrib = await rt.contribute("ML")
        # Strategy's parse_response was used — verify parsed structure
        assert contrib.title == "Parsed:contribute"
        assert "STRATEGY:contribute:ML" in contrib.content.get("raw", "")
        await rt.close()

    @pytest.mark.anyio()
    async def test_contribute_default_backward_compat(self) -> None:
        """Without strategy or YAML, default prompt is used (backward compat)."""
        rt = AgentRuntime(
            agent_id="test",
            driver=EchoDriver(),
            run_context=_make_run_context(),
        )
        await rt.initialize()
        contrib = await rt.contribute("testing")
        # Default prompt contains "Contribute to the topic: testing"
        assert "testing" in contrib.content.get("text", "")
        await rt.close()

    @pytest.mark.anyio()
    async def test_review_with_yaml_prompt(self) -> None:
        """YAML template for review should be used."""
        c = Contribution(participant_id="other", title="Title", content={"x": 1})
        rt = AgentRuntime(
            agent_id="test",
            driver=EchoDriver(),
            run_context=_make_run_context(),
            flow_prompts={"review": "Evaluate {target}'s work."},
        )
        await rt.initialize()
        review = await rt.review("other", c)
        # Echo returns the YAML prompt, not JSON -> fallback
        assert review.reviewer_id == "test"
        assert review.target_id == "other"
        await rt.close()

    @pytest.mark.anyio()
    async def test_response_format_field_accepted(self) -> None:
        """AgentRuntime should accept response_format parameter."""
        rt = AgentRuntime(
            agent_id="test",
            driver=EchoDriver(),
            run_context=_make_run_context(),
            response_format="free_text",
        )
        assert rt._response_format == "free_text"
        await rt.initialize()
        await rt.close()
