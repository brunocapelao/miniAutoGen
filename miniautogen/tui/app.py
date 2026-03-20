"""MiniAutoGen Dash -- main Textual application.

The app shell provides:
- Header with title
- Footer with key hints
- Two-panel workspace (Team sidebar + Work panel)
- Global key bindings
- Command palette (built-in)
- SVG export (built-in via Ctrl+P)
- Theme support
- Data provider for CRUD operations
- Server status display
- Init wizard when no project found
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header

from miniautogen.tui.data_provider import DashDataProvider
from miniautogen.tui.event_sink import TuiEventSink
from miniautogen.tui.messages import RunCompleted, SidebarRefresh, TuiEvent
from miniautogen.tui.workers import EventBridgeWorker
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

    def __init__(self, project_root=None) -> None:
        super().__init__()
        self._provider: DashDataProvider | None = None
        self._project_root = project_root
        self._event_sink: TuiEventSink | None = None
        self._bridge: EventBridgeWorker | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield TeamSidebar()
        yield WorkPanel()
        yield Footer()

    def on_mount(self) -> None:
        """Handle initial mount -- load provider, apply responsive, check project."""
        self._apply_responsive()
        self._init_provider()
        self._update_server_status()
        self._populate_sidebar()
        self._start_event_bridge()

    def _start_event_bridge(self) -> None:
        """Create TuiEventSink and start the EventBridgeWorker."""
        self._event_sink = TuiEventSink()
        self._bridge = EventBridgeWorker(self._event_sink)
        self.run_worker(self._bridge.run(self), exclusive=True)

    def _init_provider(self) -> None:
        """Initialize the data provider."""
        if self._project_root is not None:
            from pathlib import Path
            self._provider = DashDataProvider(Path(self._project_root))
        else:
            self._provider = DashDataProvider.from_cwd()

        if self._provider is None or not self._provider.has_project():
            # Show init wizard
            from miniautogen.tui.screens.init_wizard import InitWizardScreen
            self.push_screen(InitWizardScreen(), callback=self._on_init_result)

    def _on_init_result(self, created: bool) -> None:
        """Callback from init wizard."""
        if created:
            self._provider = DashDataProvider.from_cwd()
            self.notify("Project initialized!")
        else:
            self.notify("No project -- some features unavailable", severity="warning")

    def _populate_sidebar(self) -> None:
        """Populate the TeamSidebar with agents from the data provider."""
        if self._provider is None:
            return
        try:
            sidebar = self.query_one(TeamSidebar)
            sidebar.clear_agents()
            for agent in self._provider.get_agents():
                sidebar.add_agent(
                    agent_id=agent.get("name", "unknown"),
                    name=agent.get("name", "Unknown"),
                    role=agent.get("role", "agent"),
                )
        except Exception:
            pass  # Provider or sidebar not ready

    def _update_server_status(self) -> None:
        """Update subtitle with server status."""
        if self._provider is None:
            return
        try:
            status = self._provider.server_status()
            server_state = status.get("status", "stopped")
            if server_state == "running":
                port = status.get("port", "?")
                self.sub_title = f"Your AI Team at Work | Server: running (:{port})"
            elif server_state == "stopped":
                self.sub_title = "Your AI Team at Work | Server: stopped"
            else:
                self.sub_title = f"Your AI Team at Work | Server: {server_state}"
        except Exception:
            pass

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

    def on_sidebar_refresh(self, message: SidebarRefresh) -> None:
        """Handle sidebar refresh request (agent created/deleted)."""
        self._populate_sidebar()

    def on_run_completed(self, message: RunCompleted) -> None:
        """Handle pipeline run completion -- log result to interaction log."""
        try:
            work_panel = self.query_one(WorkPanel)
            if message.status == "completed":
                work_panel.interaction_log.add_step_header(
                    step_number=0,
                    step_label=f"Pipeline '{message.pipeline_name}' completed",
                )
            else:
                work_panel.interaction_log.add_step_header(
                    step_number=0,
                    step_label=f"Pipeline '{message.pipeline_name}' {message.status}",
                )
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
        from miniautogen.tui.screens.diff_view import DiffViewScreen
        self.push_screen(DiffViewScreen())

    def action_next_pipeline(self) -> None:
        """Switch to next pipeline tab."""
        pass

    def action_server_start(self) -> None:
        """Start the gateway server."""
        if self._provider is None:
            self.notify("No project found", severity="error")
            return
        result = self._provider.start_server(daemon=True)
        self.notify(result.get("message", "Server started"))
        self._update_server_status()

    def action_server_stop(self) -> None:
        """Stop the gateway server."""
        if self._provider is None:
            self.notify("No project found", severity="error")
            return
        result = self._provider.stop_server()
        self.notify(result.get("message", "Server stopped"))
        self._update_server_status()
