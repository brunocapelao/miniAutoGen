"""Tests for the WorkPanel widget -- the right panel of the workspace."""

from __future__ import annotations

from textual.widget import Widget

from miniautogen.tui.widgets.work_panel import WorkPanel
from miniautogen.tui.widgets.interaction_log import InteractionLog


def test_work_panel_is_widget() -> None:
    assert issubclass(WorkPanel, Widget)


def test_work_panel_has_interaction_log() -> None:
    panel = WorkPanel()
    assert hasattr(panel, "interaction_log")
    assert isinstance(panel.interaction_log, InteractionLog)


def test_work_panel_initial_progress_values() -> None:
    panel = WorkPanel()
    assert panel._total_steps == 0
    assert panel._current_step == 0


def test_work_panel_update_progress_stores_values() -> None:
    panel = WorkPanel()
    panel.update_progress(3, 10, "Step 3 of 10")
    assert panel._current_step == 3
    assert panel._total_steps == 10
