"""Tests for MiniAutoGenBaseModel orjson integration."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import miniautogen._json as _json_mod
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

    def test_model_dump_json_actually_calls_shim_dumps(self) -> None:
        """Prove that model_dump_json routes through miniautogen._json.dumps (orjson path)."""
        m = SampleModel(name="x", value=1, ts=datetime(2026, 1, 1, tzinfo=timezone.utc))
        with patch.object(_json_mod, "dumps", wraps=_json_mod.dumps) as mock_dumps:
            result = m.model_dump_json()
            mock_dumps.assert_called_once()
        assert isinstance(result, str)

    def test_model_validate_json_actually_calls_shim_loads(self) -> None:
        """Prove that model_validate_json routes through miniautogen._json.loads."""
        original = SampleModel(name="y", value=2, ts=datetime(2026, 1, 1, tzinfo=timezone.utc))
        json_str = original.model_dump_json()
        with patch.object(_json_mod, "loads", wraps=_json_mod.loads) as mock_loads:
            restored = SampleModel.model_validate_json(json_str)
            mock_loads.assert_called_once_with(json_str)
        assert restored.name == original.name

    def test_model_validate_json_accepts_bytes(self) -> None:
        """model_validate_json must accept bytes as well as str."""
        json_bytes = b'{"name": "z", "value": 3, "ts": "2026-01-01T00:00:00+00:00"}'
        restored = SampleModel.model_validate_json(json_bytes)
        assert restored.name == "z"
        assert restored.value == 3
