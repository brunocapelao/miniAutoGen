"""MiniAutoGen Dash -- main Textual application.

The app shell provides:
- Header with title
- Footer with key hints
- Two-panel workspace (Team sidebar + Work panel)
- Global key bindings
- Command palette (built-in)
- SVG export (built-in via Ctrl+P)
- Theme support
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header

from miniautogen.tui.messages import TuiEvent
from miniautogen.tui.views.agents import AgentsView
from miniautogen.tui.views.events import EventsView
from miniautogen.tui.views.pipelines import PipelinesView
from miniautogen.tui.views.runs import RunsView
from miniautogen.tui.views.engines import EnginesView
from miniautogen.tui.views.config import ConfigView
from miniautogen.tui.widgets.team_sidebar import TeamSidebar
from miniautogen.tui.widgets.work_panel import WorkPanel

_NARROW_BREAKPOINT = 100


class MiniAutoGenDash(App):
    """Your AI Team at Work -- TUI dashboard for MiniAutoGen."""

    TITLE = "MiniAutoGen Dash"
    SUB_TITLE = "Your AI Team at Work"

    ENABLE_COMMAND_PALETTE = True

    CSS_PATH = "dash.tcss"

    SCREENS = {
        "agents": AgentsView,
        "events": EventsView,
        "pipelines": PipelinesView,
        "runs": RunsView,
        "engines": EnginesView,
        "config": ConfigView,
    }

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("question_mark", "help", "Help", show=True),
        Binding("escape", "back", "Back", show=True),
        Binding("f", "fullscreen", "Fullscreen", show=True),
        Binding("t", "toggle_sidebar", "Team", show=True),
        Binding("d", "diff_view", "Diff", show=False),
        Binding("slash", "search", "Search", show=True),
        Binding("tab", "next_pipeline", "Next Tab", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield TeamSidebar()
        yield WorkPanel()
        yield Footer()

    def on_mount(self) -> None:
        """Handle initial mount -- apply responsive breakpoints."""
        self._apply_responsive()

    def on_resize(self, event: object) -> None:
        """Handle terminal resize for responsive breakpoints."""
        self._apply_responsive()

    def _apply_responsive(self) -> None:
        """Show/hide sidebar based on terminal width."""
        width = self.size.width
        try:
            sidebar = self.query_one(TeamSidebar)
            if width < _NARROW_BREAKPOINT:
                sidebar.display = False
            else:
                sidebar.display = True
                if width < 120:
                    sidebar.styles.width = "6"
                else:
                    sidebar.styles.width = "28"
        except Exception:
            pass

    def on_tui_event(self, message: TuiEvent) -> None:
        """Handle incoming TUI events from the event bridge."""
        event = message.event
        # Forward to work panel
        try:
            work_panel = self.query_one(WorkPanel)
            work_panel.interaction_log.handle_event(event)
        except Exception:
            pass

    def action_help(self) -> None:
        """Show help overlay."""
        self.notify("Help: Press [b]:[/b] for commands, [b]/[/b] to search")

    def action_back(self) -> None:
        """Navigate back or close panel."""
        pass

    def action_fullscreen(self) -> None:
        """Toggle fullscreen for work panel."""
        try:
            sidebar = self.query_one(TeamSidebar)
            sidebar.display = False
        except Exception:
            pass

    def action_toggle_sidebar(self) -> None:
        """Toggle team sidebar visibility."""
        try:
            sidebar = self.query_one(TeamSidebar)
            sidebar.display = not sidebar.display
        except Exception:
            pass

    def action_search(self) -> None:
        """Open search/filter in current view."""
        pass

    def action_diff_view(self) -> None:
        """Open diff view."""
        pass

    def action_next_pipeline(self) -> None:
        """Switch to next pipeline tab."""
        pass
