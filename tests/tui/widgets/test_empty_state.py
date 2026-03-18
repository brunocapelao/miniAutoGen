"""Tests for the EmptyState widget."""

from __future__ import annotations

from textual.widget import Widget

from miniautogen.tui.widgets.empty_state import EmptyState


def test_empty_state_is_widget() -> None:
    assert issubclass(EmptyState, Widget)


def test_empty_state_default_display() -> None:
    state = EmptyState()
    text = state.get_display_text()
    assert "Your team is ready" in text
    assert "miniautogen run" in text


def test_empty_state_shows_pipelines() -> None:
    state = EmptyState(pipelines=["summarize", "code-review"])
    text = state.get_display_text()
    assert "summarize" in text
    assert "code-review" in text
    assert "Available pipelines" in text


def test_empty_state_no_pipelines_by_default() -> None:
    state = EmptyState()
    assert state.pipelines == []


def test_empty_state_pipelines_list_is_copy() -> None:
    original = ["p1", "p2"]
    state = EmptyState(pipelines=original)
    result = state.pipelines
    result.append("p3")
    assert len(state.pipelines) == 2  # Original not mutated


def test_empty_state_shows_run_instructions() -> None:
    state = EmptyState()
    text = state.get_display_text()
    assert "miniautogen run <pipeline>" in text
