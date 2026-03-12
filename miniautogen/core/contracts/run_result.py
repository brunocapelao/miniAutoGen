from typing import Any

from pydantic import BaseModel, Field


class RunResult(BaseModel):
    """Terminal or partially terminal result of a run."""

    run_id: str
    status: str
    output: Any = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
