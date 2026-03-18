"""Tests for all secondary views."""

from __future__ import annotations

import pytest

from miniautogen.tui.views.base import SecondaryView
from miniautogen.tui.views.pipelines import PipelinesView
from miniautogen.tui.views.runs import RunsView
from miniautogen.tui.views.engines import EnginesView
from miniautogen.tui.views.config import ConfigView


@pytest.mark.parametrize(
    "view_cls,expected_title",
    [
        (PipelinesView, "Pipelines"),
        (RunsView, "Runs"),
        (EnginesView, "Engines"),
        (ConfigView, "Config"),
    ],
)
def test_secondary_view_inherits_base(view_cls: type, expected_title: str) -> None:
    assert issubclass(view_cls, SecondaryView)
    view = view_cls()
    assert view.VIEW_TITLE == expected_title
