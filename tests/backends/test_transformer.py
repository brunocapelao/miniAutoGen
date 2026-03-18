"""Tests for MessageTransformer protocol."""

from __future__ import annotations

from typing import Any

from miniautogen.backends.models import AgentEvent
from miniautogen.backends.transformer import MessageTransformer


class FakeTransformer:
    """A concrete implementation to test the protocol."""

    def to_provider(self, messages: list[dict[str, Any]]) -> Any:
        return [{"role": m["role"], "content": m["content"]} for m in messages]

    def from_provider(
        self, response: Any, session_id: str, turn_id: str,
    ) -> list[AgentEvent]:
        return [
            AgentEvent(
                type="message_completed",
                session_id=session_id,
                turn_id=turn_id,
                payload={"text": str(response)},
            ),
        ]


class TestMessageTransformerProtocol:
    def test_fake_satisfies_protocol(self) -> None:
        transformer: MessageTransformer = FakeTransformer()
        result = transformer.to_provider([{"role": "user", "content": "hi"}])
        assert isinstance(result, list)

    def test_from_provider_returns_events(self) -> None:
        transformer: MessageTransformer = FakeTransformer()
        events = transformer.from_provider("Hello!", session_id="s1", turn_id="t1")
        assert len(events) == 1
        assert events[0].type == "message_completed"
        assert events[0].payload["text"] == "Hello!"

    def test_protocol_is_runtime_checkable(self) -> None:
        assert isinstance(FakeTransformer(), MessageTransformer)
