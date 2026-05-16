"""Tests for TeamRuntime event types and canonical event ordering."""

from __future__ import annotations

from miniautogen.core.events.types import TEAM_EVENT_TYPES, EventType


def test_team_event_types_exist() -> None:
    """All 6 TEAM_* EventTypes must be defined."""
    assert EventType.TEAM_STARTED
    assert EventType.TEAMMATE_SPAWNED
    assert EventType.TEAMMATE_FINISHED
    assert EventType.TEAMMATE_FAILED
    assert EventType.TEAM_FINISHED
    assert EventType.TEAM_FAILED


def test_team_event_types_values() -> None:
    """Event values must be canonical strings."""
    assert EventType.TEAM_STARTED.value == "team_started"
    assert EventType.TEAMMATE_SPAWNED.value == "teammate_spawned"
    assert EventType.TEAMMATE_FINISHED.value == "teammate_finished"
    assert EventType.TEAMMATE_FAILED.value == "teammate_failed"
    assert EventType.TEAM_FINISHED.value == "team_finished"
    assert EventType.TEAM_FAILED.value == "team_failed"


def test_team_event_types_set_exists() -> None:
    """TEAM_EVENT_TYPES set must define all 6 team events."""
    assert len(TEAM_EVENT_TYPES) == 6
    assert EventType.TEAM_STARTED in TEAM_EVENT_TYPES
    assert EventType.TEAMMATE_SPAWNED in TEAM_EVENT_TYPES
    assert EventType.TEAMMATE_FINISHED in TEAM_EVENT_TYPES
    assert EventType.TEAMMATE_FAILED in TEAM_EVENT_TYPES
    assert EventType.TEAM_FINISHED in TEAM_EVENT_TYPES
    assert EventType.TEAM_FAILED in TEAM_EVENT_TYPES
