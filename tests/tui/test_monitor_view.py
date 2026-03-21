"""Tests for the MonitorView secondary screen."""

from __future__ import annotations

from miniautogen.tui.views.base import SecondaryView
from miniautogen.tui.views.monitor import MonitorView


def test_monitor_view_is_secondary_view() -> None:
    """MonitorView should extend SecondaryView."""
    assert issubclass(MonitorView, SecondaryView)


def test_monitor_view_title() -> None:
    """MonitorView should have correct VIEW_TITLE."""
    view = MonitorView()
    assert view.VIEW_TITLE == "Monitor"
