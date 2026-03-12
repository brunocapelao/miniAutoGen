from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RunContext(BaseModel):
    """Typed execution context for a single framework run."""

    run_id: str
    started_at: datetime
    correlation_id: str
    execution_state: dict[str, Any] = Field(default_factory=dict)
    input_payload: Any = None
    timeout_seconds: float | None = None
    namespace: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
