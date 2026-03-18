"""Tests for DiffViewScreen."""

from __future__ import annotations

from textual.screen import Screen

from miniautogen.tui.screens.diff_view import DiffViewScreen


def test_diff_view_is_screen() -> None:
    assert issubclass(DiffViewScreen, Screen)


def test_diff_view_empty() -> None:
    view = DiffViewScreen()
    assert view._diffs == []


def test_diff_view_with_diffs() -> None:
    diffs = [
        {"file": "test.py", "content": "+added line", "action": "modified"},
    ]
    view = DiffViewScreen(diffs=diffs)
    assert len(view._diffs) == 1
    assert view._diffs[0]["file"] == "test.py"


def test_add_diff() -> None:
    view = DiffViewScreen()
    view.add_diff("hello.py", "+new code", "created")
    assert len(view._diffs) == 1
    assert view._diffs[0]["file"] == "hello.py"
    assert view._diffs[0]["action"] == "created"
