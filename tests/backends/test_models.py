"""Tests for backend driver domain models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from miniautogen.backends.models import (
    AgentEvent,
    ArtifactRef,
    BackendCapabilities,
    CancelTurnRequest,
    SendTurnRequest,
    StartSessionRequest,
    StartSessionResponse,
)


class TestBackendCapabilities:
    def test_defaults_all_false(self) -> None:
        caps = BackendCapabilities()
        assert caps.sessions is False
        assert caps.streaming is False
        assert caps.cancel is False
        assert caps.resume is False
        assert caps.tools is False
        assert caps.artifacts is False
        assert caps.multimodal is False

    def test_partial_override(self) -> None:
        caps = BackendCapabilities(sessions=True, streaming=True)
        assert caps.sessions is True
        assert caps.streaming is True
        assert caps.cancel is False

    def test_serialization_roundtrip(self) -> None:
        caps = BackendCapabilities(sessions=True, tools=True)
        data = caps.model_dump()
        restored = BackendCapabilities.model_validate(data)
        assert restored == caps

    def test_supported_returns_true_names(self) -> None:
        caps = BackendCapabilities(sessions=True, cancel=True)
        assert caps.supported() == {"sessions", "cancel"}

    def test_supported_empty_when_none_set(self) -> None:
        caps = BackendCapabilities()
        assert caps.supported() == set()


class TestStartSessionRequest:
    def test_minimal(self) -> None:
        req = StartSessionRequest(backend_id="claude_code")
        assert req.backend_id == "claude_code"
        assert req.system_prompt is None
        assert req.metadata == {}

    def test_with_all_fields(self) -> None:
        req = StartSessionRequest(
            backend_id="claude_code",
            system_prompt="You are helpful.",
            metadata={"user": "test"},
        )
        assert req.system_prompt == "You are helpful."

    def test_backend_id_required(self) -> None:
        with pytest.raises(ValidationError):
            StartSessionRequest()  # type: ignore[call-arg]


class TestStartSessionResponse:
    def test_minimal(self) -> None:
        resp = StartSessionResponse(
            session_id="sess_1",
            capabilities=BackendCapabilities(),
        )
        assert resp.session_id == "sess_1"
        assert resp.external_session_ref is None

    def test_with_external_ref(self) -> None:
        resp = StartSessionResponse(
            session_id="sess_1",
            external_session_ref="ext_abc",
            capabilities=BackendCapabilities(sessions=True),
        )
        assert resp.external_session_ref == "ext_abc"
        assert resp.capabilities.sessions is True


class TestSendTurnRequest:
    def test_minimal(self) -> None:
        req = SendTurnRequest(
            session_id="sess_1",
            messages=[{"role": "user", "content": "Hello"}],
        )
        assert req.session_id == "sess_1"
        assert len(req.messages) == 1

    def test_session_id_required(self) -> None:
        with pytest.raises(ValidationError):
            SendTurnRequest(messages=[])  # type: ignore[call-arg]


class TestCancelTurnRequest:
    def test_minimal(self) -> None:
        req = CancelTurnRequest(session_id="sess_1")
        assert req.reason is None

    def test_with_reason(self) -> None:
        req = CancelTurnRequest(session_id="sess_1", reason="user cancelled")
        assert req.reason == "user cancelled"


class TestArtifactRef:
    def test_minimal(self) -> None:
        ref = ArtifactRef(artifact_id="art_1", kind="file")
        assert ref.name is None
        assert ref.uri is None

    def test_full(self) -> None:
        ref = ArtifactRef(
            artifact_id="art_1",
            kind="diff",
            name="patch.diff",
            uri="file:///tmp/patch.diff",
            metadata={"lines": 42},
        )
        assert ref.kind == "diff"
        assert ref.metadata["lines"] == 42

    def test_serialization_roundtrip(self) -> None:
        ref = ArtifactRef(artifact_id="a", kind="json", name="data.json")
        assert ArtifactRef.model_validate(ref.model_dump()) == ref


class TestAgentEvent:
    def test_minimal(self) -> None:
        ev = AgentEvent(type="message_delta", session_id="sess_1")
        assert ev.turn_id is None
        assert ev.payload == {}
        assert ev.timestamp is not None

    def test_full(self) -> None:
        ev = AgentEvent(
            type="tool_call_requested",
            session_id="sess_1",
            turn_id="turn_1",
            payload={"tool": "read_file", "args": {"path": "/tmp/x"}},
        )
        assert ev.type == "tool_call_requested"
        assert ev.payload["tool"] == "read_file"

    def test_serialization_roundtrip(self) -> None:
        ev = AgentEvent(
            type="message_completed",
            session_id="s",
            turn_id="t",
            payload={"text": "done"},
        )
        assert AgentEvent.model_validate(ev.model_dump()) == ev
