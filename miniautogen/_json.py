"""Centralized JSON serialization shim.

All internal modules MUST import dumps/loads from here:

    from miniautogen._json import dumps, loads

This guarantees a single fallback path and consistent behavior.
"""

from __future__ import annotations

import base64
from decimal import Decimal


def _default(obj: object) -> object:
    """Fallback serializer for types not natively supported by orjson/stdlib.

    Handles bytes (base64-encoded) and Decimal (converted to str).
    Raises TypeError for all other unknown types.
    """
    if isinstance(obj, bytes):
        return base64.b64encode(obj).decode()
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f"Type is not JSON serializable: {type(obj).__name__}")


try:
    import orjson

    def dumps(obj: object, *, indent: bool = False) -> str:
        """Serialize *obj* to a JSON string (always returns str, not bytes)."""
        option = orjson.OPT_INDENT_2 if indent else 0
        return orjson.dumps(obj, option=option, default=_default).decode()

    def loads(data: str | bytes) -> object:
        """Deserialize a JSON string or bytes to a Python object."""
        return orjson.loads(data)

    HAS_ORJSON = True

except ImportError:  # pragma: no cover -- fallback for exotic platforms
    import json as _json

    def dumps(obj: object, *, indent: bool = False) -> str:  # type: ignore[misc]
        """Serialize *obj* to a JSON string (stdlib fallback)."""
        return _json.dumps(obj, indent=2 if indent else None, default=_default)

    def loads(data: str | bytes) -> object:  # type: ignore[misc]
        """Deserialize a JSON string or bytes to a Python object."""
        return _json.loads(data)

    HAS_ORJSON = False
