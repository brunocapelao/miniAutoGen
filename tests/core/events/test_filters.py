"""Tests for event filters."""

import pytest

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.filters import (
    CompositeFilter,
    EventFilter,
    RunFilter,
    TypeFilter,
)
from miniautogen.core.events.types import EventType


def _make_event(
    event_type: str = "run_started",
    run_id: str = "run-1",
) -> ExecutionEvent:
    return ExecutionEvent(
        type=event_type,
        run_id=run_id,
        correlation_id="test-corr-id",
    )


# --- EventFilter protocol ---


def test_type_filter_satisfies_protocol() -> None:
    f = TypeFilter({EventType.RUN_STARTED})
    assert isinstance(f, EventFilter)


def test_run_filter_satisfies_protocol() -> None:
    f = RunFilter("run-1")
    assert isinstance(f, EventFilter)


def test_composite_filter_satisfies_protocol() -> None:
    f = CompositeFilter([], mode="all")
    assert isinstance(f, EventFilter)


# --- TypeFilter ---


def test_type_filter_matches_enum() -> None:
    f = TypeFilter({EventType.RUN_STARTED})
    assert f.matches(_make_event("run_started")) is True
    assert f.matches(_make_event("run_failed")) is False


def test_type_filter_matches_string() -> None:
    f = TypeFilter({"run_started"})
    assert f.matches(_make_event("run_started")) is True


def test_type_filter_multiple_types() -> None:
    f = TypeFilter({EventType.RUN_STARTED, EventType.RUN_FAILED})
    assert f.matches(_make_event("run_started")) is True
    assert f.matches(_make_event("run_failed")) is True
    assert f.matches(_make_event("run_finished")) is False


# --- RunFilter ---


def test_run_filter_matches() -> None:
    f = RunFilter("run-1")
    assert f.matches(_make_event(run_id="run-1")) is True
    assert f.matches(_make_event(run_id="run-2")) is False


# --- CompositeFilter ---


def test_composite_all_mode() -> None:
    f = CompositeFilter(
        [TypeFilter({EventType.RUN_STARTED}), RunFilter("run-1")],
        mode="all",
    )
    assert f.matches(_make_event("run_started", "run-1")) is True
    assert f.matches(_make_event("run_started", "run-2")) is False
    assert f.matches(_make_event("run_failed", "run-1")) is False


def test_composite_any_mode() -> None:
    f = CompositeFilter(
        [TypeFilter({EventType.RUN_STARTED}), RunFilter("run-1")],
        mode="any",
    )
    assert f.matches(_make_event("run_started", "run-2")) is True
    assert f.matches(_make_event("run_failed", "run-1")) is True
    assert f.matches(_make_event("run_failed", "run-2")) is False


def test_composite_invalid_mode() -> None:
    with pytest.raises(ValueError, match="mode must be"):
        CompositeFilter([], mode="invalid")
