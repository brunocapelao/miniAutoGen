"""Shared Pydantic base model for all MiniAutoGen contracts.

All framework models MUST inherit from MiniAutoGenBaseModel
to ensure consistent orjson-backed serialization.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class MiniAutoGenBaseModel(BaseModel):
    """Base model with orjson-backed JSON serialization.

    Overrides Pydantic v2's ``model_dump_json()`` and
    ``model_validate_json()`` instance/class methods so that all
    serialization goes through the centralized ``miniautogen._json``
    shim (orjson when available, stdlib as fallback).
    """

    def model_dump_json(self, **kwargs: Any) -> str:  # type: ignore[override]
        """Serialize the model to a JSON string via the miniautogen._json shim."""
        from miniautogen._json import dumps

        return dumps(self.model_dump(mode="json"))

    @classmethod
    def model_validate_json(  # type: ignore[override]
        cls,
        json_data: str | bytes,
        **kwargs: Any,
    ) -> "MiniAutoGenBaseModel":
        """Deserialize a JSON string or bytes via the miniautogen._json shim."""
        from miniautogen._json import loads

        data = loads(json_data) if isinstance(json_data, (str, bytes)) else json_data
        return cls.model_validate(data)
