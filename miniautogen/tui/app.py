"""MiniAutoGen Dash -- main Textual application.

The app shell provides:
- Header with title
- TabBar for primary navigation (Workspace / Flows / Agents / Config)
- Horizontal layout: MainContent (1fr) + ExecutionSidebar (dock right)
- Footer with key hints
- Global key bindings (number keys 1-4 switch tabs)
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
from textual.containers import Horizontal
from textual.widgets import Footer, Header

from miniautogen.tui.data_provider import DashDataProvider
from miniautogen.tui.event_sink import TuiEventSink
from miniautogen.tui.messages import RunStarted, RunStopped, SidebarRefresh, TabChanged, TuiEvent
from miniautogen.tui.themes import DEFAULT_THEME, THEMES, register_dash_themes
from miniautogen.tui.workers import EventBridgeWorker
from miniautogen.tui.views.check import CheckView
from miniautogen.tui.views.events import EventsView
from miniautogen.tui.views.monitor import MonitorView
from miniautogen.tui.widgets.execution_sidebar import ExecutionSidebar
from miniautogen.tui.widgets.main_content import MainContent
from miniautogen.tui.widgets.tab_bar import TabBar
from miniautogen.tui.content.workspace import WorkspaceContent
from miniautogen.tui.content.flows import FlowsContent
from miniautogen.tui.content.agents import AgentsContent
from miniautogen.tui.content.config import ConfigContent

_NARROW_BREAKPOINT = 100
_MEDIUM_BREAKPOINT = 130


class MiniAutoGenDash(App):
    """Your AI Team at Work -- TUI dashboard for MiniAutoGen."""

    TITLE = "MiniAutoGen Dash"
    SUB_TITLE = "Your AI Team at Work"

    ENABLE_COMMAND_PALETTE = True

    CSS_PATH = "dash.tcss"

    SCREENS = {
        "monitor": MonitorView,
        "check": CheckView,
        "events": EventsView,
    }

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("question_mark", "help", "Help", show=True),
        Binding("escape", "back", "Back", show=True),
        Binding("t", "toggle_sidebar", "Sidebar", show=True),
        Binding("f", "fullscreen", "Fullscreen", show=False),
        Binding("s", "stop_run", "Stop", show=False),
        Binding("1", "switch_tab('Workspace')", "1", show=False),
        Binding("2", "switch_tab('Flows')", "2", show=False),
        Binding("3", "switch_tab('Agents')", "3", show=False),
        Binding("4", "switch_tab('Config')", "4", show=False),
    ]

    def __init__(self, project_root=None) -> None:
        super().__init__()
        self._provider: DashDataProvider | None = None
        self._project_root = project_root
        self._event_sink: TuiEventSink | None = None
        self._bridge: EventBridgeWorker | None = None
        self._current_theme: str = DEFAULT_THEME
        register_dash_themes(self)

    def compose(self) -> ComposeResult:
        yield Header()
        yield TabBar()
        main = MainContent()
        main.register_tab("Workspace", WorkspaceContent())
        main.register_tab("Flows", FlowsContent())
        main.register_tab("Agents", AgentsContent())
        main.register_tab("Config", ConfigContent())
        with Horizontal(id="app-grid"):
            yield main
            yield ExecutionSidebar()
        yield Footer()

    def on_mount(self) -> None:
        """Handle initial mount -- load provider, apply responsive, check project."""
        self.apply_theme(self._current_theme)
        self._apply_responsive()
        self._init_provider()
        self._auto_start_server()
        self._update_server_status()
        self._populate_sidebar()
        self._refresh_workspace()
        self._start_event_bridge()

    def _start_event_bridge(self) -> None:
        """Create TuiEventSink, wire it to the provider, and start the EventBridgeWorker."""
        self._event_sink = TuiEventSink()
        if self._provider is not None:
            self._provider.set_event_sink(self._event_sink)
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
            if self._provider is not None and self._event_sink is not None:
                self._provider.set_event_sink(self._event_sink)
            self.notify("Project initialized!")
        else:
            self.notify("No project -- some features unavailable", severity="warning")

    def _populate_sidebar(self) -> None:
        """Populate the ExecutionSidebar with agents and recent runs from data provider."""
        try:
            sidebar = self.query_one(ExecutionSidebar)
            if self._provider:
                agents = self._provider.get_agents()
                agent_list = [{"name": a.get("name", ""), "status": "idle"} for a in agents]
                sidebar.set_agents(agent_list)
                runs = self._provider.get_runs()
                sidebar.set_recent_runs(runs)
        except Exception:
            pass

    def _refresh_workspace(self) -> None:
        """Refresh workspace tab stats from data provider."""
        try:
            ws = self.query_one(WorkspaceContent)
            if self._provider:
                agents = self._provider.get_agents()
                flows = self._provider.get_pipelines()
                engines = self._provider.get_engines()

                # Build health check items
                health_items: list[tuple[str, str]] = []
                if self._provider.has_project():
                    health_items.append(("[green]\u2713[/green]", "miniautogen.yaml found"))
                for eng in engines:
                    health_items.append(
                        ("[green]\u2713[/green]", f'Engine "{eng.get("name", "?")}" configured')
                    )
                for agent in agents:
                    engine_name = agent.get("engine_profile", "") or agent.get("engine", "")
                    if engine_name:
                        health_items.append(
                            ("[green]\u2713[/green]", f'Agent "{agent.get("name", "?")}" has engine profile')
                        )
                    else:
                        health_items.append(
                            ("[yellow]\u26a0[/yellow]", f'Agent "{agent.get("name", "?")}" has no engine configured')
                        )

                ws.refresh_data(
                    agents_count=len(agents),
                    flows_count=len(flows),
                    engines_count=len(engines),
                    health_items=health_items if health_items else None,
                )
        except Exception:
            pass

    def _auto_start_server(self) -> None:
        """Auto-start the gateway server if a project is loaded and server is not running."""
        if self._provider is None or not self._provider.has_project():
            return
        try:
            status = self._provider.server_status()
            if status.get("status") != "running":
                self._provider.start_server(daemon=True)
        except Exception:
            pass

    def _update_server_status(self) -> None:
        """Update subtitle and tab bar with server status."""
        if self._provider is None:
            return
        server_state = "stopped"
        port = "?"
        try:
            status = self._provider.server_status()
            server_state = status.get("status", "stopped")
            port = status.get("port", "?")
            if server_state == "running":
                self.sub_title = f"Your AI Team at Work | Server: running (:{port})"
            elif server_state == "stopped":
                self.sub_title = "Your AI Team at Work | Server: stopped"
            else:
                self.sub_title = f"Your AI Team at Work | Server: {server_state}"
        except Exception:
            pass

        # Update tab bar server indicator
        try:
            tab_bar = self.query_one(TabBar)
            if server_state == "running":
                tab_bar.update_server_status(f"[green]\u25cf Server :{port}[/green]")
            else:
                tab_bar.update_server_status("[dim]\u25cf Server: off[/dim]")
        except Exception:
            pass

    def on_resize(self, event: object) -> None:
        """Handle terminal resize for responsive breakpoints."""
        self._apply_responsive()

    def _apply_responsive(self) -> None:
        """Show/hide sidebar and adjust width based on terminal width."""
        width = self.size.width
        try:
            sidebar = self.query_one(ExecutionSidebar)
            if width < _NARROW_BREAKPOINT:
                sidebar.display = False
            else:
                sidebar.display = True
                if width < _MEDIUM_BREAKPOINT:
                    sidebar.styles.width = "25"
                else:
                    sidebar.styles.width = "35"
        except Exception:
            pass

    # --- Theme ---

    def apply_theme(self, name: str) -> None:
        """Apply a DashTheme by *name*.

        Sets the Textual ``theme`` reactive which triggers CSS variable
        refresh and dark/light mode switching automatically.
        """
        if name not in THEMES:
            name = DEFAULT_THEME
        self._current_theme = name
        self.theme = name

    # --- Message handlers ---

    def action_switch_tab(self, tab_name: str) -> None:
        """Switch active tab via number keys."""
        try:
            tab_bar = self.query_one(TabBar)
            tab_bar.active_tab = tab_name
        except Exception:
            pass

    def on_tab_changed(self, event: TabChanged) -> None:
        """Handle tab changes from TabBar."""
        try:
            main = self.query_one(MainContent)
            main.switch_to(event.tab_name)
        except Exception:
            pass

    def on_tui_event(self, message: TuiEvent) -> None:
        """Forward execution events to sidebar log and record in provider."""
        try:
            sidebar = self.query_one(ExecutionSidebar)
            sidebar.interaction_log.handle_event(message.event)
        except Exception:
            pass
        # Record event in provider for queryable history
        if self._provider is not None:
            try:
                event_dict = {
                    "type": message.event.type,
                    "run_id": message.event.run_id,
                    "scope": message.event.scope,
                    "timestamp": message.event.timestamp.isoformat()
                    if hasattr(message.event, "timestamp") and message.event.timestamp
                    else None,
                    "payload": message.event.payload
                    if hasattr(message.event, "payload")
                    else {},
                }
                self._provider.record_event(event_dict)
            except Exception:
                pass

    def on_sidebar_refresh(self, message: SidebarRefresh) -> None:
        """Handle sidebar refresh request (agent created/deleted)."""
        self._populate_sidebar()
        self._refresh_workspace()

    def on_run_started(self, event: RunStarted) -> None:
        """Handle flow execution start."""
        try:
            sidebar = self.query_one(ExecutionSidebar)
            sidebar.start_execution()
        except Exception:
            pass

    def on_run_stopped(self, event: RunStopped) -> None:
        """Handle flow execution end."""
        try:
            sidebar = self.query_one(ExecutionSidebar)
            sidebar.stop_execution()
        except Exception:
            pass

    # --- Actions ---

    def action_help(self) -> None:
        """Show help overlay."""
        from miniautogen.tui.screens.help_screen import HelpScreen
        self.push_screen(HelpScreen())

    def action_back(self) -> None:
        """Navigate back or close panel."""
        pass

    def action_toggle_sidebar(self) -> None:
        """Toggle execution sidebar visibility."""
        try:
            sidebar = self.query_one(ExecutionSidebar)
            sidebar.display = not sidebar.display
        except Exception:
            pass

    def action_fullscreen(self) -> None:
        """Toggle fullscreen (hide/show sidebar)."""
        try:
            sidebar = self.query_one(ExecutionSidebar)
            sidebar.display = not sidebar.display
        except Exception:
            pass

    def action_stop_run(self) -> None:
        """Stop the current flow execution."""
        self.post_message(RunStopped(run_id="", final_status="stopped"))

    def action_diff_view(self) -> None:
        """Open diff view."""
        from miniautogen.tui.screens.diff_view import DiffViewScreen
        self.push_screen(DiffViewScreen())

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

    def on_unmount(self) -> None:
        """Stop server on TUI exit."""
        if self._provider is not None:
            try:
                status = self._provider.server_status()
                if status.get("status") == "running":
                    self._provider.stop_server()
            except Exception:
                pass
