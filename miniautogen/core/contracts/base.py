"""Shared Pydantic base model for all MiniAutoGen contracts.

All framework models MUST inherit from MiniAutoGenBaseModel
to ensure consistent orjson-backed serialization.
"""

from __future__ import annotations

from typing import Any

import orjson
from pydantic import BaseModel


class MiniAutoGenBaseModel(BaseModel):
    """Base model with orjson-backed JSON serialization.

    Overrides Pydantic v2's default JSON encoder/decoder so that
    all ``model_dump_json()`` and ``model_validate_json()`` calls
    use orjson transparently.
    """

    @classmethod
    def model_json_loads(cls, data: str | bytes) -> Any:
        """Deserialize JSON using orjson."""
        return orjson.loads(data)

    @classmethod
    def model_json_dumps(cls, data: Any, **kwargs: Any) -> str:
        """Serialize to JSON using orjson (returns str, not bytes)."""
        return orjson.dumps(data).decode()
