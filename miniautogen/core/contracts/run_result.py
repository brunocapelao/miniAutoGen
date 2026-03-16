from typing import Any

from pydantic import BaseModel, Field

from miniautogen.core.contracts.enums import RunStatus


class RunResult(BaseModel):
    """Terminal or partially terminal result of a run."""

    run_id: str
    status: RunStatus
    output: Any = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
