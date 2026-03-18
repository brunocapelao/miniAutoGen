"""Workspace screen -- the main screen assembling the two-panel layout.

Composes TeamSidebar (left) + WorkPanel (right) with PipelineTabs
and HintBar. Handles TuiEvent messages and routes to children.
Responsive: hides sidebar at narrow terminals.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.binding import Binding

from miniautogen.tui.messages import TuiEvent
from miniautogen.tui.event_mapper import EventMapper
from miniautogen.tui.widgets.team_sidebar import TeamSidebar
from miniautogen.tui.widgets.work_panel import WorkPanel
from miniautogen.tui.widgets.pipeline_tabs import PipelineTabs
from miniautogen.tui.widgets.hint_bar import HintBar
from miniautogen.tui.widgets.empty_state import EmptyState

_NARROW_BREAKPOINT = 100


class WorkspaceScreen(Screen):
    """Main workspace screen with two-panel layout."""

    DEFAULT_CSS = """
    WorkspaceScreen {
        layout: horizontal;
    }

    WorkspaceScreen #main-area {
        width: 1fr;
    }
    """

    BINDINGS = [
        Binding("t", "toggle_sidebar", "Team", show=True),
        Binding("tab", "next_pipeline", "Next Tab", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._has_pipeline = False

    def compose(self) -> ComposeResult:
        yield TeamSidebar()
        yield WorkPanel()

    def on_mount(self) -> None:
        """Apply responsive breakpoints on mount."""
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
        """Route incoming TUI events to child widgets."""
        event = message.event

        # Update agent status in sidebar
        agent_id = EventMapper.extract_agent_id(event)
        if agent_id:
            agent_status = EventMapper.map_agent_status(event)
            if agent_status:
                try:
                    sidebar = self.query_one(TeamSidebar)
                    sidebar.update_agent_status(agent_id, agent_status)
                    sidebar.highlight_agent(agent_id)
                except Exception:
                    pass

        # Forward to work panel
        try:
            work_panel = self.query_one(WorkPanel)
            work_panel.interaction_log.handle_event(event)
        except Exception:
            pass

    def action_toggle_sidebar(self) -> None:
        """Toggle team sidebar visibility."""
        try:
            sidebar = self.query_one(TeamSidebar)
            sidebar.display = not sidebar.display
        except Exception:
            pass

    def action_next_pipeline(self) -> None:
        """Switch to next pipeline tab."""
        try:
            tabs = self.query_one(PipelineTabs)
            tabs.next_tab()
        except Exception:
            pass
