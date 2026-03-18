"""Tests for the :agents secondary view."""

from __future__ import annotations

from miniautogen.tui.views.agents import AgentsView
from miniautogen.tui.views.base import SecondaryView


def test_agents_view_is_secondary_view() -> None:
    assert issubclass(AgentsView, SecondaryView)


def test_agents_view_title() -> None:
    view = AgentsView()
    assert view.VIEW_TITLE == "Agents"
