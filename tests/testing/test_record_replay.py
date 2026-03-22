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
