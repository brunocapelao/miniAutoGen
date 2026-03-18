"""Tests for MiniAutoGenBaseModel orjson integration."""

from __future__ import annotations

from datetime import datetime, timezone

from miniautogen.core.contracts.base import MiniAutoGenBaseModel


class SampleModel(MiniAutoGenBaseModel):
    name: str
    value: int
    ts: datetime


class TestBaseModelOrjson:
    """Verify orjson is used for model serialization."""

    def test_model_dump_json_returns_str(self) -> None:
        m = SampleModel(name="test", value=42, ts=datetime(2026, 1, 1, tzinfo=timezone.utc))
        result = m.model_dump_json()
        assert isinstance(result, str)

    def test_model_validate_json_round_trip(self) -> None:
        original = SampleModel(name="test", value=42, ts=datetime(2026, 1, 1, tzinfo=timezone.utc))
        json_str = original.model_dump_json()
        restored = SampleModel.model_validate_json(json_str)
        assert restored.name == original.name
        assert restored.value == original.value
        assert restored.ts == original.ts

    def test_model_json_loads_classmethod(self) -> None:
        result = SampleModel.model_json_loads('{"name": "x", "value": 1, "ts": "2026-01-01T00:00:00+00:00"}')
        assert isinstance(result, dict)
        assert result["name"] == "x"

    def test_model_json_dumps_classmethod(self) -> None:
        result = SampleModel.model_json_dumps({"name": "x", "value": 1})
        assert isinstance(result, str)
        assert '"name"' in result
