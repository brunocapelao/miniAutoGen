"""Tests for the secondary view base class."""

from __future__ import annotations

from textual.screen import Screen

from miniautogen.tui.views.base import SecondaryView


def test_secondary_view_is_screen() -> None:
    assert issubclass(SecondaryView, Screen)


def test_secondary_view_has_title() -> None:
    class TestView(SecondaryView):
        VIEW_TITLE = "Test"

    view = TestView()
    assert view.VIEW_TITLE == "Test"
