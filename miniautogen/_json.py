"""Centralized JSON serialization shim.

All internal modules MUST import dumps/loads from here:

    from miniautogen._json import dumps, loads

This guarantees a single fallback path and consistent behavior.
"""

from __future__ import annotations

try:
    import orjson

    def dumps(obj: object, *, indent: bool = False) -> str:
        """Serialize *obj* to a JSON string (always returns str, not bytes)."""
        option = orjson.OPT_INDENT_2 if indent else 0
        return orjson.dumps(obj, option=option).decode()

    def loads(data: str | bytes) -> object:
        """Deserialize a JSON string or bytes to a Python object."""
        return orjson.loads(data)

    HAS_ORJSON = True

except ImportError:  # pragma: no cover -- fallback for exotic platforms
    import json as _json

    def dumps(obj: object, *, indent: bool = False) -> str:  # type: ignore[misc]
        """Serialize *obj* to a JSON string (stdlib fallback)."""
        return _json.dumps(obj, indent=2 if indent else None, default=str)

    def loads(data: str | bytes) -> object:  # type: ignore[misc]
        """Deserialize a JSON string or bytes to a Python object."""
        return _json.loads(data)

    HAS_ORJSON = False
