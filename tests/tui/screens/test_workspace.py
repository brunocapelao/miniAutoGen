"""Tests for the WorkspaceScreen."""

from __future__ import annotations

import pytest

from textual.screen import Screen

from miniautogen.tui.screens.workspace import WorkspaceScreen
from miniautogen.tui.widgets.team_sidebar import TeamSidebar
from miniautogen.tui.widgets.work_panel import WorkPanel


def test_workspace_screen_is_screen() -> None:
    assert issubclass(WorkspaceScreen, Screen)


def test_workspace_screen_instantiates() -> None:
    screen = WorkspaceScreen()
    assert screen is not None
