"""Run detail view: step-by-step execution visualization."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static, ProgressBar


class RunDetailView(Widget):
    """Shows execution progress with step blocks during flow run."""

    DEFAULT_CSS = """
    RunDetailView { height: 1fr; padding: 1 2; }
    RunDetailView .flow-header { text-style: bold; margin-bottom: 1; }
    RunDetailView .flow-meta { color: $text-muted; margin-bottom: 1; }
    RunDetailView #run-progress { height: 1; margin: 0 0 1 0; }
    RunDetailView #step-container { height: 1fr; }
    RunDetailView .step-item { height: auto; margin-bottom: 1; padding: 1; }
    RunDetailView .step-item.--done { border-left: solid green; }
    RunDetailView .step-item.--active { border-left: solid yellow; }
    RunDetailView .step-item.--pending { border-left: solid gray; opacity: 0.6; }
    """

    def __init__(self, flow_name: str, flow_mode: str = "workflow") -> None:
        """Initialize RunDetailView.

        Args:
            flow_name: Name of the flow being executed.
            flow_mode: Type of flow (e.g., 'workflow', 'agent').
        """
        super().__init__()
        self.flow_name = flow_name
        self.flow_mode = flow_mode
        self.current_step = 0
        self.total_steps = 0
        self._final_status: str | None = None

    def compose(self) -> ComposeResult:
        """Compose the run detail view sections."""
        yield Static(self.flow_name, classes="flow-header", id="flow-title")
        yield Static(
            f"{self.flow_mode} · step 0/0", classes="flow-meta", id="flow-meta"
        )
        yield ProgressBar(total=100, show_eta=False, id="run-progress")
        yield Static("Waiting for execution events...", id="step-container")

    def update_progress(self, current: int, total: int, label: str = "") -> None:
        """Update progress bar and metadata.

        Args:
            current: Current step number.
            total: Total number of steps.
            label: Optional label for the current step.
        """
        self.current_step = current
        self.total_steps = total
        try:
            meta = self.query_one("#flow-meta", Static)
            meta_text = f"{self.flow_mode} · step {current}/{total}"
            if label:
                meta_text += f" · {label}"
            meta.update(meta_text)
            progress = self.query_one("#run-progress", ProgressBar)
            if total > 0:
                progress.update(total=total, progress=current)
        except Exception:
            pass

    def set_completed(self, status: str, duration: str = "") -> None:
        """Mark execution as completed.

        Args:
            status: Final status ('completed', 'failed', etc.).
            duration: Optional execution duration.
        """
        self._final_status = status
        try:
            meta = self.query_one("#flow-meta", Static)
            status_symbol = "✓" if status == "completed" else "✕"
            meta_text = f"{status_symbol} {status}"
            if duration:
                meta_text += f" · {duration}"
            meta.update(meta_text)
            progress = self.query_one("#run-progress", ProgressBar)
            progress.update(total=self.total_steps, progress=self.total_steps)
        except Exception:
            pass
