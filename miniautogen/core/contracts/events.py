from datetime import datetime, timezone
from typing import Any

from pydantic import AliasChoices, ConfigDict, Field, model_validator

from miniautogen.core.contracts.base import MiniAutoGenBaseModel


class ExecutionEvent(MiniAutoGenBaseModel):
    """Canonical execution event emitted by the runtime."""

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
    payload: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def infer_run_id_from_payload(self) -> "ExecutionEvent":
        if self.run_id is None and "run_id" in self.payload:
            payload_run_id = self.payload["run_id"]
            if isinstance(payload_run_id, str):
                self.run_id = payload_run_id
        return self

    @property
    def event_type(self) -> str:
        return self.type

    @property
    def created_at(self) -> datetime:
        return self.timestamp
