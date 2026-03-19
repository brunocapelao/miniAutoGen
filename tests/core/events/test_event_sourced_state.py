"""Tests for EventSourcedState: deterministic event replay via left-fold."""

from __future__ import annotations

import pytest

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.contracts.run_context import FrozenState
from miniautogen.core.events.types import EventType


class TestFold:
    """Tests for fold(events) -> FrozenState."""

    def test_import(self) -> None:
        from miniautogen.core.events.event_sourced_state import fold  # noqa: F401

    def test_empty_events_returns_empty_state(self) -> None:
        from miniautogen.core.events.event_sourced_state import fold

        result = fold([])
        assert isinstance(result, FrozenState)
        assert result.to_dict() == {}

    def test_run_started_sets_status(self) -> None:
        from miniautogen.core.events.event_sourced_state import fold

        events = [
            ExecutionEvent(
                type=EventType.RUN_STARTED.value,
                run_id="run-1",
                payload={"run_id": "run-1"},
            ),
        ]
        state = fold(events)
        assert state.get("status") == "started"
        assert state.get("run_id") == "run-1"

    def test_run_finished_sets_status(self) -> None:
        from miniautogen.core.events.event_sourced_state import fold

        events = [
            ExecutionEvent(
                type=EventType.RUN_STARTED.value,
                run_id="run-1",
                payload={"run_id": "run-1"},
            ),
            ExecutionEvent(
                type=EventType.RUN_FINISHED.value,
                run_id="run-1",
            ),
        ]
        state = fold(events)
        assert state.get("status") == "finished"

    def test_run_failed_sets_status_and_error(self) -> None:
        from miniautogen.core.events.event_sourced_state import fold

        events = [
            ExecutionEvent(
                type=EventType.RUN_STARTED.value,
                run_id="run-1",
            ),
            ExecutionEvent(
                type=EventType.RUN_FAILED.value,
                run_id="run-1",
                payload={"error": "boom"},
            ),
        ]
        state = fold(events)
        assert state.get("status") == "failed"
        assert state.get("error") == "boom"

    def test_component_finished_tracks_step_index(self) -> None:
        from miniautogen.core.events.event_sourced_state import fold

        events = [
            ExecutionEvent(
                type=EventType.RUN_STARTED.value,
                run_id="run-1",
            ),
            ExecutionEvent(
                type=EventType.COMPONENT_FINISHED.value,
                run_id="run-1",
                payload={"component": "step-a", "result": "ok"},
            ),
            ExecutionEvent(
                type=EventType.COMPONENT_FINISHED.value,
                run_id="run-1",
                payload={"component": "step-b", "result": "done"},
            ),
        ]
        state = fold(events)
        assert state.get("step_index") == 2

    def test_checkpoint_saved_records_index(self) -> None:
        from miniautogen.core.events.event_sourced_state import fold

        events = [
            ExecutionEvent(
                type=EventType.CHECKPOINT_SAVED.value,
                run_id="run-1",
                payload={"step_index": 5},
            ),
        ]
        state = fold(events)
        assert state.get("last_checkpoint_index") == 5

    def test_fold_is_deterministic(self) -> None:
        from miniautogen.core.events.event_sourced_state import fold

        events = [
            ExecutionEvent(type=EventType.RUN_STARTED.value, run_id="r1"),
            ExecutionEvent(
                type=EventType.COMPONENT_FINISHED.value,
                run_id="r1",
                payload={"component": "x", "result": "y"},
            ),
            ExecutionEvent(type=EventType.RUN_FINISHED.value, run_id="r1"),
        ]
        state1 = fold(events)
        state2 = fold(events)
        assert state1 == state2

    def test_fold_returns_frozen_state(self) -> None:
        from miniautogen.core.events.event_sourced_state import fold

        events = [
            ExecutionEvent(type=EventType.RUN_STARTED.value, run_id="r1"),
        ]
        state = fold(events)
        assert isinstance(state, FrozenState)
        with pytest.raises(AttributeError):
            state.status = "mutated"  # type: ignore[attr-defined]

    def test_unknown_event_type_is_ignored(self) -> None:
        from miniautogen.core.events.event_sourced_state import fold

        events = [
            ExecutionEvent(type="some_future_event", run_id="r1"),
        ]
        state = fold(events)
        # Should not crash, just ignore unknown events
        assert isinstance(state, FrozenState)


class TestFork:
    """Tests for fork(events, from_checkpoint_index) -> list[ExecutionEvent]."""

    def test_import(self) -> None:
        from miniautogen.core.events.event_sourced_state import fork  # noqa: F401

    def test_fork_from_zero_returns_all(self) -> None:
        from miniautogen.core.events.event_sourced_state import fork

        events = [
            ExecutionEvent(type=EventType.RUN_STARTED.value, run_id="r1"),
            ExecutionEvent(type=EventType.COMPONENT_FINISHED.value, run_id="r1"),
        ]
        result = fork(events, from_checkpoint_index=0)
        assert len(result) == 2

    def test_fork_from_midpoint(self) -> None:
        from miniautogen.core.events.event_sourced_state import fork

        events = [
            ExecutionEvent(type=EventType.RUN_STARTED.value, run_id="r1"),
            ExecutionEvent(type=EventType.COMPONENT_FINISHED.value, run_id="r1"),
            ExecutionEvent(type=EventType.COMPONENT_FINISHED.value, run_id="r1"),
            ExecutionEvent(type=EventType.RUN_FINISHED.value, run_id="r1"),
        ]
        result = fork(events, from_checkpoint_index=2)
        assert len(result) == 2
        assert result[0].type == EventType.COMPONENT_FINISHED.value
        assert result[1].type == EventType.RUN_FINISHED.value

    def test_fork_beyond_length_returns_empty(self) -> None:
        from miniautogen.core.events.event_sourced_state import fork

        events = [
            ExecutionEvent(type=EventType.RUN_STARTED.value, run_id="r1"),
        ]
        result = fork(events, from_checkpoint_index=10)
        assert result == []

    def test_fork_returns_new_list(self) -> None:
        from miniautogen.core.events.event_sourced_state import fork

        events = [
            ExecutionEvent(type=EventType.RUN_STARTED.value, run_id="r1"),
        ]
        result = fork(events, from_checkpoint_index=0)
        assert result is not events
