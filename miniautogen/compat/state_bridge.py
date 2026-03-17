from __future__ import annotations

from datetime import datetime
from typing import Any

from miniautogen.core.contracts.run_context import RunContext

RUNTIME_RUNNER_CUTOVER_READY = True


def bridge_chat_pipeline_state(state: Any) -> dict[str, Any]:
    """Convert legacy pipeline state into a mutable mapping."""
    if hasattr(state, "get_state"):
        return dict(state.get_state())
    return dict(state)


def bridge_chat_pipeline_state_to_run_context(
    state: Any,
    *,
    run_id: str,
    started_at: datetime,
    correlation_id: str,
) -> RunContext:
    """Lift legacy chat pipeline state into the typed run context."""
    return RunContext(
        run_id=run_id,
        started_at=started_at,
        correlation_id=correlation_id,
        execution_state=bridge_chat_pipeline_state(state),
    )
