from datetime import datetime, timezone
from typing import Any

from pydantic import AliasChoices, ConfigDict, Field

from miniautogen.core.contracts.base import MiniAutoGenBaseModel


class ExecutionEvent(MiniAutoGenBaseModel):
    """Canonical execution event emitted by the runtime."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    type: str = Field(
        validation_alias=AliasChoices("type", "event_type"),
        serialization_alias="type",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        validation_alias=AliasChoices("timestamp", "created_at"),
        serialization_alias="timestamp",
    )
    run_id: str | None = None
    correlation_id: str | None = None
    scope: str | None = None
    payload: tuple[tuple[str, Any], ...] = ()

    def __init__(self, **data: Any) -> None:
        # Convert dict payload to tuple-of-tuples before freezing
        raw_payload = data.get("payload", {})
        if isinstance(raw_payload, dict):
            data["payload"] = tuple(sorted(raw_payload.items()))
            # Infer run_id from payload before freezing
            if data.get("run_id") is None and "run_id" in raw_payload:
                candidate = raw_payload["run_id"]
                if isinstance(candidate, str):
                    data["run_id"] = candidate
        elif isinstance(raw_payload, list):
            # Handle deserialized form: list of [key, value] pairs
            data["payload"] = tuple(tuple(pair) for pair in raw_payload)
        super().__init__(**data)

    @property
    def event_type(self) -> str:
        """Backward-compatible alias for type."""
        return self.type

    @property
    def created_at(self) -> datetime:
        """Backward-compatible alias for timestamp."""
        return self.timestamp

    def get_payload(self, key: str, default: Any = None) -> Any:
        """Look up a payload key without dict conversion."""
        for k, v in self.payload:
            if k == key:
                return v
        return default

    def payload_dict(self) -> dict[str, Any]:
        """Return payload as a plain dict for code that needs dict operations."""
        return dict(self.payload)
