"""WorkPanel widget -- the right panel showing pipeline conversation.

Contains the InteractionLog and a progress bar at the bottom.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import ProgressBar, Static

from miniautogen.tui.widgets.interaction_log import InteractionLog


class WorkPanel(Widget):
    """The main work area showing the pipeline conversation."""

    DEFAULT_CSS = """
    WorkPanel {
        height: 1fr;
    }

    WorkPanel #progress-section {
        dock: bottom;
        height: 3;
        padding: 0 1;
        background: $surface;
    }

    WorkPanel #step-progress {
        width: 1fr;
    }

    WorkPanel #step-label {
        text-align: center;
        color: $text-muted;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.interaction_log = InteractionLog()
        self._total_steps = 0
        self._current_step = 0

    def compose(self) -> ComposeResult:
        yield self.interaction_log
        with Vertical(id="progress-section"):
            yield ProgressBar(total=100, show_eta=False, id="step-progress")
            yield Static("Ready", id="step-label")

    def update_progress(self, current: int, total: int, label: str = "") -> None:
        """Update the step progress bar."""
        self._current_step = current
        self._total_steps = total
        try:
            bar = self.query_one("#step-progress", ProgressBar)
            bar.total = total
            bar.progress = current
            lbl = self.query_one("#step-label", Static)
            lbl.update(label or f"Step {current} of {total}")
        except Exception:
            pass
