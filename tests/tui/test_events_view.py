"""Tests for the :events secondary view."""

from __future__ import annotations

from miniautogen.tui.views.events import EventsView
from miniautogen.tui.views.base import SecondaryView


def test_events_view_is_secondary_view() -> None:
    assert issubclass(EventsView, SecondaryView)


def test_events_view_title() -> None:
    view = EventsView()
    assert view.VIEW_TITLE == "Events"
