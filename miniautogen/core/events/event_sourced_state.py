"""EventSourcedState: deterministic event replay via left-fold.

Reconstructs FrozenState from a sequence of ExecutionEvents.
Fulfills OS Invariant 5 (Event Sourcing) -- state is derivable
from the event log at any point.

fold(events) applies each event's reducer in order (left-fold),
producing a single FrozenState snapshot.

fork(events, from_checkpoint_index) slices the event list for
replay from a checkpoint, enabling event bifurcation.
"""

from __future__ import annotations

from typing import Any

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.contracts.run_context import FrozenState
from miniautogen.core.events.types import EventType

# -- Reducer registry: event_type_value -> (state_dict, event) -> state_dict

def _reduce_run_started(state: dict[str, Any], event: ExecutionEvent) -> dict[str, Any]:
    state["status"] = "started"
    run_id = event.get_payload("run_id") or event.run_id
    if run_id:
        state["run_id"] = run_id
    return state


def _reduce_run_finished(state: dict[str, Any], event: ExecutionEvent) -> dict[str, Any]:
    state["status"] = "finished"
    return state


def _reduce_run_failed(state: dict[str, Any], event: ExecutionEvent) -> dict[str, Any]:
    state["status"] = "failed"
    error = event.get_payload("error")
    if error is not None:
        state["error"] = error
    return state


def _reduce_run_cancelled(state: dict[str, Any], event: ExecutionEvent) -> dict[str, Any]:
    state["status"] = "cancelled"
    return state


def _reduce_run_timed_out(state: dict[str, Any], event: ExecutionEvent) -> dict[str, Any]:
    state["status"] = "timed_out"
    return state


def _reduce_component_started(state: dict[str, Any], event: ExecutionEvent) -> dict[str, Any]:
    component = event.get_payload("component")
    if component:
        state["active_component"] = component
    return state


def _reduce_component_finished(state: dict[str, Any], event: ExecutionEvent) -> dict[str, Any]:
    step_index = state.get("step_index", 0)
    state["step_index"] = step_index + 1
    result = event.get_payload("result")
    if result is not None:
        state["last_result"] = result
    state.pop("active_component", None)
    return state


def _reduce_component_skipped(state: dict[str, Any], event: ExecutionEvent) -> dict[str, Any]:
    step_index = state.get("step_index", 0)
    state["step_index"] = step_index + 1
    return state


def _reduce_checkpoint_saved(state: dict[str, Any], event: ExecutionEvent) -> dict[str, Any]:
    idx = event.get_payload("step_index")
    if idx is not None:
        state["last_checkpoint_index"] = idx
    return state


def _reduce_checkpoint_restored(state: dict[str, Any], event: ExecutionEvent) -> dict[str, Any]:
    idx = event.get_payload("step_index")
    if idx is not None:
        state["step_index"] = idx
    return state


_REDUCERS: dict[str, Any] = {
    EventType.RUN_STARTED.value: _reduce_run_started,
    EventType.RUN_FINISHED.value: _reduce_run_finished,
    EventType.RUN_FAILED.value: _reduce_run_failed,
    EventType.RUN_CANCELLED.value: _reduce_run_cancelled,
    EventType.RUN_TIMED_OUT.value: _reduce_run_timed_out,
    EventType.COMPONENT_STARTED.value: _reduce_component_started,
    EventType.COMPONENT_FINISHED.value: _reduce_component_finished,
    EventType.COMPONENT_SKIPPED.value: _reduce_component_skipped,
    EventType.CHECKPOINT_SAVED.value: _reduce_checkpoint_saved,
    EventType.CHECKPOINT_RESTORED.value: _reduce_checkpoint_restored,
}


def fold(events: list[ExecutionEvent]) -> FrozenState:
    """Reconstruct state from an event sequence via left-fold.

    Applies each event's reducer in order. Unknown event types
    are silently ignored (forward-compatible with future events).

    Args:
        events: Ordered list of ExecutionEvents to replay.

    Returns:
        A FrozenState snapshot representing the accumulated state.
    """
    state: dict[str, Any] = {}
    for event in events:
        reducer = _REDUCERS.get(event.type)
        if reducer is not None:
            state = reducer(state, event)
    return FrozenState(**state)


def fork(
    events: list[ExecutionEvent],
    from_checkpoint_index: int,
) -> list[ExecutionEvent]:
    """Slice an event list for replay from a checkpoint.

    Returns a new list containing events from ``from_checkpoint_index``
    onward, enabling event bifurcation for checkpoint-based resume.

    Args:
        events: The full ordered event list.
        from_checkpoint_index: Start index for the slice (inclusive).

    Returns:
        A new list of events from the given index onward.
        Returns an empty list if the index exceeds the event count.
    """
    return list(events[from_checkpoint_index:])
