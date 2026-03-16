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

    def with_previous_result(self, result: Any) -> "RunContext":
        """Create a new RunContext with the previous result injected.

        The previous result is set as ``input_payload`` and a reference
        is stored in ``metadata["previous_result"]`` for traceability.
        """
        new_metadata = {**self.metadata, "previous_result": result}
        return self.model_copy(
            update={"input_payload": result, "metadata": new_metadata},
        )
