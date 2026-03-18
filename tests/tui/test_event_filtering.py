"""Tests for EventsView filtering logic."""

from __future__ import annotations

from miniautogen.tui.views.events import EventsView


def test_matches_filter_empty() -> None:
    """Empty filter matches everything."""
    view = EventsView()
    event = {"type": "run_started", "agent": "planner", "payload": "data"}
    assert view._matches_filter(event, "") is True


def test_matches_filter_type_slash() -> None:
    """Filter by type with / prefix."""
    view = EventsView()
    event = {"type": "run_started", "agent": "planner"}
    assert view._matches_filter(event, "/run") is True
    assert view._matches_filter(event, "/error") is False


def test_matches_filter_agent_at() -> None:
    """Filter by agent with @ prefix."""
    view = EventsView()
    event = {"type": "run_started", "agent": "planner"}
    assert view._matches_filter(event, "@planner") is True
    assert view._matches_filter(event, "@writer") is False


def test_matches_filter_keyword() -> None:
    """Filter by keyword across all fields."""
    view = EventsView()
    event = {"type": "tool_invoked", "agent": "researcher", "payload": "web_search"}
    assert view._matches_filter(event, "web_search") is True
    assert view._matches_filter(event, "database") is False


def test_matches_filter_case_insensitive() -> None:
    """Filters are case insensitive."""
    view = EventsView()
    event = {"type": "RUN_STARTED", "agent": "Planner"}
    assert view._matches_filter(event, "/run_started") is True
    assert view._matches_filter(event, "@planner") is True
    assert view._matches_filter(event, "PLANNER") is True
