"""Persistent right sidebar: idle panel or live execution log."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from miniautogen.tui.widgets.idle_panel import IdlePanel
from miniautogen.tui.widgets.interaction_log import InteractionLog


class ExecutionSidebar(Widget):
    """Right sidebar that shows idle state or live execution log.

    Toggles between IdlePanel (team status + recent runs) and
    InteractionLog (live execution transcript) based on is_executing state.
    """

    DEFAULT_CSS = """
    ExecutionSidebar {
        dock: right;
        width: 35;
        background: $surface;
        border-left: tall $primary-background;
    }
    ExecutionSidebar #sidebar-header {
        height: 1;
        padding: 0 1;
        background: $primary 15%;
        layout: horizontal;
    }
    ExecutionSidebar #sidebar-title {
        width: 1fr;
        color: $primary;
        text-style: bold;
    }
    ExecutionSidebar #sidebar-status {
        width: auto;
        color: $text-muted;
    }
    """

    is_executing: reactive[bool] = reactive(False)

    def __init__(self) -> None:
        super().__init__()
        self.interaction_log = InteractionLog()

    def compose(self) -> ComposeResult:
        """Compose sidebar with header and content panels."""
        with Horizontal(id="sidebar-header"):
            yield Static("Execution", id="sidebar-title")
            yield Static("idle", id="sidebar-status")
        yield IdlePanel()
        yield self.interaction_log

    def on_mount(self) -> None:
        """Hide interaction log by default when mounted."""
        self.interaction_log.display = False

    def watch_is_executing(self, value: bool) -> None:
        """Toggle panel visibility based on is_executing state.

        Args:
            value: True to show execution log, False to show idle panel.
        """
        try:
            idle = self.query_one(IdlePanel)
            idle.display = not value
            self.interaction_log.display = value
            title = self.query_one("#sidebar-title", Static)
            title.update("Execution Log" if value else "Execution")
            status = self.query_one("#sidebar-status", Static)
            status.update("[green]● live[/green]" if value else "idle")
        except Exception:
            # Widgets may not be mounted yet during initialization
            pass

    def start_execution(self) -> None:
        """Start execution mode, showing the interaction log."""
        self.is_executing = True

    def stop_execution(self) -> None:
        """Stop execution mode, returning to idle panel."""
        self.is_executing = False

    def set_agents(self, agents: list[dict]) -> None:
        """Set the agents list in the idle panel.

        Args:
            agents: List of agent dictionaries with name and status.
        """
        try:
            idle = self.query_one(IdlePanel)
            idle.set_agents(agents)
        except Exception:
            pass

    def set_recent_runs(self, runs: list[dict]) -> None:
        """Set the recent runs list in the idle panel.

        Args:
            runs: List of run dictionaries with flow_name, status, and ago.
        """
        try:
            idle = self.query_one(IdlePanel)
            idle.set_recent_runs(runs)
        except Exception:
            pass
