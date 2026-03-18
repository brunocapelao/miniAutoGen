"""Tests for miniautogen._json shim module."""

from __future__ import annotations

import base64
from decimal import Decimal

import pytest

from miniautogen._json import HAS_ORJSON, _default, dumps, loads


class TestDumps:
    """Tests for the dumps() function."""

    def test_dumps_returns_str(self) -> None:
        result = dumps({"key": "value"})
        assert isinstance(result, str)

    def test_dumps_simple_dict(self) -> None:
        result = dumps({"a": 1, "b": "two"})
        restored = loads(result)
        assert restored == {"a": 1, "b": "two"}

    def test_dumps_nested_structure(self) -> None:
        data = {"outer": {"inner": [1, 2, 3]}}
        result = dumps(data)
        assert loads(result) == data

    def test_dumps_with_indent(self) -> None:
        result = dumps({"a": 1}, indent=True)
        assert isinstance(result, str)
        # Indented output has newlines
        assert "\n" in result

    def test_dumps_without_indent_is_compact(self) -> None:
        result = dumps({"a": 1}, indent=False)
        assert "\n" not in result


class TestLoads:
    """Tests for the loads() function."""

    def test_loads_from_str(self) -> None:
        result = loads('{"key": "value"}')
        assert result == {"key": "value"}

    def test_loads_from_bytes(self) -> None:
        result = loads(b'{"key": "value"}')
        assert result == {"key": "value"}

    def test_loads_array(self) -> None:
        result = loads("[1, 2, 3]")
        assert result == [1, 2, 3]


class TestRoundTrip:
    """Round-trip fidelity tests."""

    def test_round_trip_dict(self) -> None:
        original = {"run_id": "abc", "state": {"step": 3, "data": [1, 2, 3]}}
        assert loads(dumps(original)) == original

    def test_round_trip_preserves_types(self) -> None:
        original = {"int": 42, "float": 3.14, "bool": True, "null": None, "str": "hello"}
        assert loads(dumps(original)) == original

    def test_round_trip_empty_structures(self) -> None:
        for obj in ({}, [], ""):
            assert loads(dumps(obj)) == obj


class TestDefaultHandler:
    """Tests for the _default fallback serializer."""

    def test_bytes_serialized_as_base64(self) -> None:
        raw = b"\x00\xff\xfe"
        result = _default(raw)
        assert result == base64.b64encode(raw).decode()

    def test_decimal_serialized_as_str(self) -> None:
        d = Decimal("3.14159")
        result = _default(d)
        assert result == "3.14159"

    def test_unknown_type_raises_type_error(self) -> None:
        with pytest.raises(TypeError, match="not JSON serializable"):
            _default(object())

    def test_dumps_with_bytes_value(self) -> None:
        raw = b"\xde\xad\xbe\xef"
        result = dumps({"data": raw})
        restored = loads(result)
        assert restored["data"] == base64.b64encode(raw).decode()

    def test_dumps_with_decimal_value(self) -> None:
        d = Decimal("99.99")
        result = dumps({"price": d})
        restored = loads(result)
        assert restored["price"] == "99.99"


class TestOrjsonDetection:
    """Verify orjson is detected when installed."""

    def test_has_orjson_is_true(self) -> None:
        # orjson is a required dependency, so this should always be True
        assert HAS_ORJSON is True
