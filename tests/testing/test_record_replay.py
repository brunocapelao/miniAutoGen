"""Tests for RecordReplayEngine."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from miniautogen.testing.record_replay import RecordReplayEngine, _serialize


class TestSerialize:
    def test_primitives(self) -> None:
        assert _serialize("hello") == "hello"
        assert _serialize(42) == 42
        assert _serialize(3.14) == 3.14
        assert _serialize(True) is True
        assert _serialize(None) is None

    def test_list(self) -> None:
        assert _serialize([1, "a", None]) == [1, "a", None]

    def test_dict(self) -> None:
        assert _serialize({"key": "val"}) == {"key": "val"}

    def test_pydantic_model(self) -> None:
        from miniautogen.core.contracts.deliberation import Contribution

        c = Contribution(participant_id="test", title="t", content={"k": "v"})
        result = _serialize(c)
        assert isinstance(result, dict)
        assert result["participant_id"] == "test"

    def test_fallback_to_str(self) -> None:
        result = _serialize(object())
        assert isinstance(result, str)


class TestRecordReplayEngine:
    @pytest.mark.anyio
    async def test_wrap_records_calls(self) -> None:
        real_agent = AsyncMock()
        real_agent.process = AsyncMock(return_value="real output")

        engine = RecordReplayEngine()
        proxy = engine.wrap("test", real_agent)
        result = await proxy.process("input")

        assert result == "real output"
        assert len(proxy._records) == 1
        assert proxy._records[0]["action"] == "process"

    @pytest.mark.anyio
    async def test_save_and_load(self, tmp_path: Path) -> None:
        real_agent = AsyncMock()
        real_agent.process = AsyncMock(return_value="output1")
        real_agent.reply = AsyncMock(return_value="reply1")

        # Record
        engine = RecordReplayEngine()
        proxy = engine.wrap("agent_a", real_agent)
        await proxy.process("input1")
        await proxy.reply("msg", {})

        path = tmp_path / "recording.json"
        engine.save(path)

        # Verify file
        data = json.loads(path.read_text())
        assert data["version"] == "1.0"
        assert "agent_a" in data["agents"]
        assert len(data["agents"]["agent_a"]) == 2

        # Replay
        replayer = RecordReplayEngine.from_recording(path)
        agent = replayer.agent("agent_a")
        r1 = await agent.process("input1")
        r2 = await agent.reply("msg", {})
        assert r1 == "output1"
        assert r2 == "reply1"

    def test_from_recording_missing_agent(self, tmp_path: Path) -> None:
        path = tmp_path / "recording.json"
        path.write_text(json.dumps({"version": "1.0", "agents": {}}))

        replayer = RecordReplayEngine.from_recording(path)
        with pytest.raises(KeyError, match="No recording found"):
            replayer.agent("nonexistent")

    def test_registry(self, tmp_path: Path) -> None:
        path = tmp_path / "recording.json"
        path.write_text(json.dumps({
            "version": "1.0",
            "agents": {
                "a": [{"action": "process", "response": "r"}],
                "b": [{"action": "process", "response": "r"}],
            },
        }))

        replayer = RecordReplayEngine.from_recording(path)
        reg = replayer.registry()
        assert "a" in reg
        assert "b" in reg

    def test_recorded_agents(self, tmp_path: Path) -> None:
        path = tmp_path / "recording.json"
        path.write_text(json.dumps({
            "version": "1.0",
            "agents": {"x": [], "y": []},
        }))

        replayer = RecordReplayEngine.from_recording(path)
        assert set(replayer.recorded_agents()) == {"x", "y"}

    @pytest.mark.anyio
    async def test_proxy_lifecycle(self) -> None:
        real_agent = AsyncMock()
        real_agent.initialize = AsyncMock()
        real_agent.close = AsyncMock()

        engine = RecordReplayEngine()
        proxy = engine.wrap("test", real_agent)
        await proxy.initialize()
        await proxy.close()
        real_agent.initialize.assert_called_once()
        real_agent.close.assert_called_once()

    @pytest.mark.anyio
    async def test_save_creates_directories(self, tmp_path: Path) -> None:
        engine = RecordReplayEngine()
        engine.wrap("test", AsyncMock())
        path = tmp_path / "sub" / "dir" / "recording.json"
        engine.save(path)
        assert path.exists()

    # -- Schema validation tests --

    def test_invalid_schema_not_dict(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text(json.dumps([1, 2, 3]))
        with pytest.raises(ValueError, match="expected a JSON object"):
            RecordReplayEngine.from_recording(path)

    def test_unsupported_version(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text(json.dumps({"version": "2.0", "agents": {}}))
        with pytest.raises(ValueError, match="Unsupported recording version"):
            RecordReplayEngine.from_recording(path)

    def test_missing_version(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text(json.dumps({"agents": {}}))
        with pytest.raises(ValueError, match="Unsupported recording version"):
            RecordReplayEngine.from_recording(path)

    def test_agents_not_dict(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text(json.dumps({"version": "1.0", "agents": "bad"}))
        with pytest.raises(ValueError, match="'agents' must be a dict"):
            RecordReplayEngine.from_recording(path)

    def test_records_not_list(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text(json.dumps({
            "version": "1.0",
            "agents": {"a": "not_a_list"},
        }))
        with pytest.raises(ValueError, match="records for 'a' must be a list"):
            RecordReplayEngine.from_recording(path)

    # -- Record full inputs tests --

    @pytest.mark.anyio
    async def test_consolidate_records_full_input(self) -> None:
        real_agent = AsyncMock()
        from miniautogen.core.contracts.deliberation import (
            Contribution,
            DeliberationState,
        )
        real_agent.consolidate = AsyncMock(
            return_value=DeliberationState(is_sufficient=True),
        )

        engine = RecordReplayEngine()
        proxy = engine.wrap("test", real_agent)
        contribs = [
            Contribution(participant_id="a", title="t", content={}),
        ]
        await proxy.consolidate("topic", contribs, [])

        record = proxy._records[0]
        assert record["action"] == "consolidate"
        assert isinstance(record["input"], dict)
        assert record["input"]["topic"] == "topic"
        assert record["input"]["contributions_count"] == 1
        assert record["input"]["reviews_count"] == 0

    @pytest.mark.anyio
    async def test_produce_final_document_records_full_input(self) -> None:
        real_agent = AsyncMock()
        from miniautogen.core.contracts.deliberation import (
            DeliberationState,
            FinalDocument,
        )
        real_agent.produce_final_document = AsyncMock(
            return_value=FinalDocument(
                executive_summary="sum",
                decision_summary="dec",
                body_markdown="body",
            ),
        )

        engine = RecordReplayEngine()
        proxy = engine.wrap("test", real_agent)
        state = DeliberationState(is_sufficient=True)
        await proxy.produce_final_document(state, [])

        record = proxy._records[0]
        assert record["action"] == "produce_final_document"
        assert isinstance(record["input"], dict)
        assert record["input"]["contributions_count"] == 0
