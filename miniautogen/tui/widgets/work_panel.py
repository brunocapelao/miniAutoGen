"""WorkPanel widget -- the right panel showing pipeline conversation.

Contains the InteractionLog and a progress bar at the bottom.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import ProgressBar, Static

from miniautogen.core.events.types import EventType
from miniautogen.tui.messages import TuiEvent
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

    WorkPanel #step-progress.failed {
        color: $error;
    }

    WorkPanel #onboarding-guide {
        height: auto;
        padding: 2 4;
        margin: 1 2;
        background: $surface;
        border: round $primary;
        color: $text;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.interaction_log = InteractionLog()
        self._total_steps = 0
        self._current_step = 0

    @property
    def _provider(self):
        """Access the DashDataProvider from the app."""
        return getattr(self.app, "_provider", None)

    def _get_onboarding_message(self) -> str:
        """Determine the contextual onboarding message based on workspace state."""
        provider = self._provider
        if provider is None or not provider.has_project():
            return "Crie um workspace para começar."

        try:
            engines = provider.get_engines()
        except Exception:
            engines = []
        if not engines:
            return (
                "Configure um engine. "
                "Pressione [bold]:[/bold] e digite [bold]engines[/bold]."
            )

        try:
            agents = provider.get_agents()
        except Exception:
            agents = []
        if not agents:
            return (
                "Crie seu primeiro agente. "
                "Pressione [bold]:[/bold] e digite [bold]agents[/bold]."
            )

        try:
            pipelines = provider.get_pipelines()
        except Exception:
            pipelines = []
        if not pipelines:
            return (
                "Defina um flow. "
                "Pressione [bold]:[/bold] e digite [bold]pipelines[/bold]."
            )

        return (
            "Equipe pronta! "
            "Vá em [bold]:[/bold] > [bold]pipelines[/bold] "
            "e pressione [bold]x[/bold] para executar."
        )

    def compose(self) -> ComposeResult:
        yield Static("", id="onboarding-guide")
        yield self.interaction_log
        with Vertical(id="progress-section"):
            yield ProgressBar(total=100, show_eta=False, id="step-progress")
            yield Static("Ready", id="step-label")

    def on_mount(self) -> None:
        """Populate onboarding guide on mount and wire onboarding hide."""
        self._refresh_onboarding()
        self._patch_interaction_log()

    def _patch_interaction_log(self) -> None:
        """Wrap InteractionLog entry methods to hide onboarding on first entry."""
        log = self.interaction_log
        original_add_agent = log.add_agent_message
        original_add_tool = log.add_tool_call
        original_add_step = log.add_step_header
        original_add_streaming = log.add_streaming_indicator

        def _wrap(original):
            def wrapper(*args, **kwargs):
                result = original(*args, **kwargs)
                self.hide_onboarding()
                return result
            return wrapper

        log.add_agent_message = _wrap(original_add_agent)
        log.add_tool_call = _wrap(original_add_tool)
        log.add_step_header = _wrap(original_add_step)
        log.add_streaming_indicator = _wrap(original_add_streaming)

    def _refresh_onboarding(self) -> None:
        """Update onboarding visibility based on log state and workspace."""
        try:
            guide = self.query_one("#onboarding-guide", Static)
            if self.interaction_log.entry_count == 0:
                msg = self._get_onboarding_message()
                guide.update(msg)
                guide.display = True
            else:
                guide.display = False
        except Exception:
            pass

    def hide_onboarding(self) -> None:
        """Hide the onboarding guide (called when log receives entries)."""
        try:
            guide = self.query_one("#onboarding-guide", Static)
            guide.display = False
        except Exception:
            pass

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

    def on_tui_event(self, message: TuiEvent) -> None:
        """Handle TuiEvent messages to update the progress bar.

        - RUN_STARTED  → "Running..." + indeterminate progress
        - RUN_FINISHED → "Completed" + 100%
        - RUN_FAILED   → "Failed" + red styling
        """
        event_type = message.event.type
        try:
            bar = self.query_one("#step-progress", ProgressBar)
            lbl = self.query_one("#step-label", Static)

            if event_type == EventType.RUN_STARTED.value:
                bar.total = None  # indeterminate
                lbl.update("Running...")
                bar.remove_class("failed")

            elif event_type == EventType.RUN_FINISHED.value:
                bar.total = 100
                bar.progress = 100
                lbl.update("Completed")
                bar.remove_class("failed")

            elif event_type in (
                EventType.RUN_FAILED.value,
                EventType.RUN_TIMED_OUT.value,
                EventType.RUN_CANCELLED.value,
            ):
                bar.total = 100
                bar.progress = 0
                lbl.update("Failed")
                bar.add_class("failed")

        except Exception:
            pass
