"""Tests for RunStateMachine — formal state machine for pipeline run lifecycle."""

from __future__ import annotations

import pytest

from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.runtime.run_state_machine import (
    TERMINAL_STATES,
    VALID_TRANSITIONS,
    InvalidTransitionError,
    RunState,
    RunStateMachine,
)

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sink() -> InMemoryEventSink:
    return InMemoryEventSink()


@pytest.fixture
def sm(sink: InMemoryEventSink) -> RunStateMachine:
    return RunStateMachine(run_id="run-1", event_sink=sink)


@pytest.fixture
def sm_no_sink() -> RunStateMachine:
    return RunStateMachine(run_id="run-2", event_sink=None)


# ---------------------------------------------------------------------------
# 1. Valid transitions
# ---------------------------------------------------------------------------


class TestValidTransitions:
    async def test_pending_to_running(self, sm: RunStateMachine) -> None:
        assert sm.state == RunState.PENDING
        await sm.transition(RunState.RUNNING)
        assert sm.state == RunState.RUNNING

    async def test_running_to_finished(self, sm: RunStateMachine) -> None:
        await sm.transition(RunState.RUNNING)
        await sm.transition(RunState.FINISHED)
        assert sm.state == RunState.FINISHED

    async def test_running_to_failed(self, sm: RunStateMachine) -> None:
        await sm.transition(RunState.RUNNING)
        await sm.transition(RunState.FAILED)
        assert sm.state == RunState.FAILED

    async def test_running_to_cancelled(self, sm: RunStateMachine) -> None:
        await sm.transition(RunState.RUNNING)
        await sm.transition(RunState.CANCELLED)
        assert sm.state == RunState.CANCELLED

    async def test_running_to_timed_out(self, sm: RunStateMachine) -> None:
        await sm.transition(RunState.RUNNING)
        await sm.transition(RunState.TIMED_OUT)
        assert sm.state == RunState.TIMED_OUT

    async def test_running_to_paused(self, sm: RunStateMachine) -> None:
        await sm.transition(RunState.RUNNING)
        await sm.transition(RunState.PAUSED)
        assert sm.state == RunState.PAUSED

    async def test_paused_to_running(self, sm: RunStateMachine) -> None:
        await sm.transition(RunState.RUNNING)
        await sm.transition(RunState.PAUSED)
        await sm.transition(RunState.RUNNING)
        assert sm.state == RunState.RUNNING

    async def test_paused_to_cancelled(self, sm: RunStateMachine) -> None:
        await sm.transition(RunState.RUNNING)
        await sm.transition(RunState.PAUSED)
        await sm.transition(RunState.CANCELLED)
        assert sm.state == RunState.CANCELLED

    async def test_pending_to_cancelled(self, sm: RunStateMachine) -> None:
        await sm.transition(RunState.CANCELLED)
        assert sm.state == RunState.CANCELLED


# ---------------------------------------------------------------------------
# 2. Invalid transitions
# ---------------------------------------------------------------------------


class TestInvalidTransitions:
    async def test_pending_to_finished(self, sm: RunStateMachine) -> None:
        with pytest.raises(InvalidTransitionError) as exc_info:
            await sm.transition(RunState.FINISHED)
        assert exc_info.value.from_state == RunState.PENDING
        assert exc_info.value.to_state == RunState.FINISHED

    async def test_pending_to_failed(self, sm: RunStateMachine) -> None:
        with pytest.raises(InvalidTransitionError):
            await sm.transition(RunState.FAILED)

    async def test_finished_to_running(self, sm: RunStateMachine) -> None:
        await sm.transition(RunState.RUNNING)
        await sm.transition(RunState.FINISHED)
        with pytest.raises(InvalidTransitionError):
            await sm.transition(RunState.RUNNING)

    async def test_failed_to_running(self, sm: RunStateMachine) -> None:
        await sm.transition(RunState.RUNNING)
        await sm.transition(RunState.FAILED)
        with pytest.raises(InvalidTransitionError):
            await sm.transition(RunState.RUNNING)

    async def test_paused_to_finished(self, sm: RunStateMachine) -> None:
        await sm.transition(RunState.RUNNING)
        await sm.transition(RunState.PAUSED)
        with pytest.raises(InvalidTransitionError):
            await sm.transition(RunState.FINISHED)

    async def test_pending_to_paused(self, sm: RunStateMachine) -> None:
        with pytest.raises(InvalidTransitionError):
            await sm.transition(RunState.PAUSED)

    async def test_invalid_transition_does_not_change_state(
        self, sm: RunStateMachine
    ) -> None:
        with pytest.raises(InvalidTransitionError):
            await sm.transition(RunState.FINISHED)
        assert sm.state == RunState.PENDING


# ---------------------------------------------------------------------------
# 3. Terminal states
# ---------------------------------------------------------------------------


class TestTerminalStates:
    def test_terminal_states_set(self) -> None:
        assert TERMINAL_STATES == {
            RunState.FINISHED,
            RunState.FAILED,
            RunState.CANCELLED,
            RunState.TIMED_OUT,
        }

    async def test_is_terminal_true_for_finished(self, sm: RunStateMachine) -> None:
        await sm.transition(RunState.RUNNING)
        await sm.transition(RunState.FINISHED)
        assert sm.is_terminal is True

    async def test_is_terminal_true_for_failed(self, sm: RunStateMachine) -> None:
        await sm.transition(RunState.RUNNING)
        await sm.transition(RunState.FAILED)
        assert sm.is_terminal is True

    async def test_is_terminal_true_for_cancelled(self, sm: RunStateMachine) -> None:
        await sm.transition(RunState.CANCELLED)
        assert sm.is_terminal is True

    async def test_is_terminal_true_for_timed_out(self, sm: RunStateMachine) -> None:
        await sm.transition(RunState.RUNNING)
        await sm.transition(RunState.TIMED_OUT)
        assert sm.is_terminal is True

    def test_is_terminal_false_for_pending(self, sm: RunStateMachine) -> None:
        assert sm.is_terminal is False

    async def test_is_terminal_false_for_running(self, sm: RunStateMachine) -> None:
        await sm.transition(RunState.RUNNING)
        assert sm.is_terminal is False

    async def test_is_terminal_false_for_paused(self, sm: RunStateMachine) -> None:
        await sm.transition(RunState.RUNNING)
        await sm.transition(RunState.PAUSED)
        assert sm.is_terminal is False

    def test_terminal_states_have_no_transitions(self) -> None:
        for state in TERMINAL_STATES:
            assert VALID_TRANSITIONS[state] == set()


# ---------------------------------------------------------------------------
# 4. History tracking
# ---------------------------------------------------------------------------


class TestHistory:
    async def test_history_records_transitions(self, sm: RunStateMachine) -> None:
        await sm.transition(RunState.RUNNING)
        await sm.transition(RunState.FINISHED)
        assert len(sm.history) == 2
        assert sm.history[0][0] == RunState.PENDING
        assert sm.history[0][1] == RunState.RUNNING
        assert sm.history[1][0] == RunState.RUNNING
        assert sm.history[1][1] == RunState.FINISHED

    async def test_history_timestamps_are_present(self, sm: RunStateMachine) -> None:
        await sm.transition(RunState.RUNNING)
        from datetime import datetime

        assert isinstance(sm.history[0][2], datetime)

    def test_history_is_empty_initially(self, sm: RunStateMachine) -> None:
        assert sm.history == []

    async def test_history_returns_copy(self, sm: RunStateMachine) -> None:
        await sm.transition(RunState.RUNNING)
        h = sm.history
        h.clear()
        assert len(sm.history) == 1  # original unaffected


# ---------------------------------------------------------------------------
# 5. Event emission
# ---------------------------------------------------------------------------


class TestEventEmission:
    async def test_event_published_on_transition(
        self, sm: RunStateMachine, sink: InMemoryEventSink
    ) -> None:
        await sm.transition(RunState.RUNNING)
        assert len(sink.events) == 1
        event = sink.events[0]
        assert event.type == "run_state_changed"
        assert event.run_id == "run-1"
        assert event.get_payload("from_state") == "pending"
        assert event.get_payload("to_state") == "running"

    async def test_multiple_events_on_multiple_transitions(
        self, sm: RunStateMachine, sink: InMemoryEventSink
    ) -> None:
        await sm.transition(RunState.RUNNING)
        await sm.transition(RunState.PAUSED)
        await sm.transition(RunState.RUNNING)
        await sm.transition(RunState.FINISHED)
        assert len(sink.events) == 4

    async def test_no_event_on_invalid_transition(
        self, sm: RunStateMachine, sink: InMemoryEventSink
    ) -> None:
        with pytest.raises(InvalidTransitionError):
            await sm.transition(RunState.FINISHED)
        assert len(sink.events) == 0


# ---------------------------------------------------------------------------
# 6. Convenience methods
# ---------------------------------------------------------------------------


class TestConvenienceMethods:
    async def test_start(self, sm: RunStateMachine) -> None:
        await sm.start()
        assert sm.state == RunState.RUNNING

    async def test_finish(self, sm: RunStateMachine) -> None:
        await sm.start()
        await sm.finish()
        assert sm.state == RunState.FINISHED

    async def test_fail(self, sm: RunStateMachine) -> None:
        await sm.start()
        await sm.fail()
        assert sm.state == RunState.FAILED

    async def test_cancel_from_pending(self, sm: RunStateMachine) -> None:
        await sm.cancel()
        assert sm.state == RunState.CANCELLED

    async def test_cancel_from_running(self, sm: RunStateMachine) -> None:
        await sm.start()
        await sm.cancel()
        assert sm.state == RunState.CANCELLED

    async def test_timeout(self, sm: RunStateMachine) -> None:
        await sm.start()
        await sm.timeout()
        assert sm.state == RunState.TIMED_OUT

    async def test_pause(self, sm: RunStateMachine) -> None:
        await sm.start()
        await sm.pause()
        assert sm.state == RunState.PAUSED

    async def test_resume(self, sm: RunStateMachine) -> None:
        await sm.start()
        await sm.pause()
        await sm.resume()
        assert sm.state == RunState.RUNNING


# ---------------------------------------------------------------------------
# 7. No event sink
# ---------------------------------------------------------------------------


class TestNoEventSink:
    async def test_transition_works_without_sink(
        self, sm_no_sink: RunStateMachine
    ) -> None:
        await sm_no_sink.start()
        await sm_no_sink.finish()
        assert sm_no_sink.state == RunState.FINISHED
        assert len(sm_no_sink.history) == 2

    async def test_convenience_methods_without_sink(
        self, sm_no_sink: RunStateMachine
    ) -> None:
        await sm_no_sink.start()
        await sm_no_sink.pause()
        await sm_no_sink.resume()
        await sm_no_sink.fail()
        assert sm_no_sink.state == RunState.FAILED
