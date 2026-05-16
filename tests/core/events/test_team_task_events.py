"""Tests for team task list EventTypes and canonical event ordering."""

from __future__ import annotations

from miniautogen.core.events.types import TEAM_TASK_EVENT_TYPES, EventType


def test_task_event_types_exist() -> None:
    assert EventType.TASK_ADDED
    assert EventType.TASK_CLAIMED
    assert EventType.TASK_COMPLETED
    assert EventType.TASK_FAILED
    assert EventType.TASK_RELEASED
    assert EventType.TASK_BLOCKED_BY_DEPENDENCY


def test_task_event_types_values() -> None:
    assert EventType.TASK_ADDED.value == "task_added"
    assert EventType.TASK_CLAIMED.value == "task_claimed"
    assert EventType.TASK_COMPLETED.value == "task_completed"
    assert EventType.TASK_FAILED.value == "task_failed"
    assert EventType.TASK_RELEASED.value == "task_released"
    assert EventType.TASK_BLOCKED_BY_DEPENDENCY.value == "task_blocked_by_dependency"


def test_team_task_event_types_set() -> None:
    assert len(TEAM_TASK_EVENT_TYPES) == 6
    assert EventType.TASK_ADDED in TEAM_TASK_EVENT_TYPES
    assert EventType.TASK_CLAIMED in TEAM_TASK_EVENT_TYPES
    assert EventType.TASK_COMPLETED in TEAM_TASK_EVENT_TYPES
    assert EventType.TASK_FAILED in TEAM_TASK_EVENT_TYPES
    assert EventType.TASK_RELEASED in TEAM_TASK_EVENT_TYPES
    assert EventType.TASK_BLOCKED_BY_DEPENDENCY in TEAM_TASK_EVENT_TYPES


def test_task_events_separate_from_team_events() -> None:
    from miniautogen.core.events.types import TEAM_EVENT_TYPES

    for ev in TEAM_TASK_EVENT_TYPES:
        assert ev not in TEAM_EVENT_TYPES
