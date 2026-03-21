"""Config tab: engines, project settings, server controls, theme."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Button, DataTable, Static

from miniautogen.tui.themes import THEMES


class ConfigContent(Widget, can_focus=True):
    """Config tab with engines CRUD, project info, server controls, theme."""

    DEFAULT_CSS = """
    ConfigContent {
        height: 1fr;
        padding: 1 2;
    }
    ConfigContent .section-title {
        color: $text-muted;
        text-style: bold;
        margin: 1 0 0 0;
        height: 1;
    }
    ConfigContent .content-hint {
        color: $text-muted;
        height: 1;
        margin: 0 0 1 0;
    }
    ConfigContent DataTable {
        height: auto;
        max-height: 40%;
        width: 1fr;
        margin: 0 0 1 0;
    }
    ConfigContent .config-box {
        background: $surface;
        border: round $primary-background;
        padding: 1 2;
        margin: 0 0 1 0;
        height: auto;
    }
    ConfigContent .server-controls {
        layout: horizontal;
        height: auto;
        margin: 0 0 1 0;
    }
    ConfigContent .server-controls Button {
        margin: 0 1 0 0;
    }
    """

    BINDINGS = [
        Binding("n", "new_engine", "New Engine", show=True),
        Binding("e", "edit_engine", "Edit", show=True),
        Binding("x", "delete_engine", "Delete", show=True),
        Binding("f5", "refresh", "Refresh", show=True),
        Binding("shift+s", "server_start", "Start Server", show=False),
        Binding("shift+x", "server_stop", "Stop Server", show=False),
        Binding("shift+t", "cycle_theme", "Theme", show=False),
    ]

    @property
    def provider(self):
        """Get the provider from the app."""
        return getattr(self.app, "_provider", None)

    def compose(self) -> ComposeResult:
        """Compose the config content sections."""
        yield Static("ENGINES", classes="section-title", id="engines-section")
        yield Static(
            "Keys: [bold]n[/bold] new  [bold]e[/bold] edit  [bold]x[/bold] delete  [bold]F5[/bold] refresh",
            classes="content-hint",
        )
        table = DataTable(id="engines-table")
        table.add_columns("Name", "Kind", "Provider", "Model")
        yield table

        yield Static("PROJECT", classes="section-title", id="project-section")
        yield Static("Loading...", id="project-info", classes="config-box")

        yield Static("SERVER", classes="section-title")
        yield Static("Status: checking...", id="server-status", classes="config-box")
        with Horizontal(classes="server-controls"):
            yield Button("[S] Start", id="btn-server-start", variant="success")
            yield Button("[X] Stop", id="btn-server-stop", variant="error")

        yield Static("THEME", classes="section-title")
        yield Button("[T] Switch Theme", id="btn-theme-switch", variant="primary")

    def on_mount(self) -> None:
        """Populate tables and displays on mount."""
        self._refresh_engines()
        self._refresh_project()

    def _refresh_engines(self) -> None:
        """Reload engine data into the table."""
        table = self.query_one("#engines-table", DataTable)
        table.clear()
        if self.provider is None:
            return
        try:
            engines = self.provider.get_engines()
            for eng in engines:
                table.add_row(
                    eng.get("name", "?"),
                    eng.get("kind", "api"),
                    eng.get("provider", "?"),
                    eng.get("model", "?"),
                )
        except Exception:
            pass

    def _refresh_project(self) -> None:
        """Refresh the project info display."""
        if self.provider is None:
            return
        try:
            config = self.provider.get_config()
            lines = [
                f"[b]Name:[/b] {config.get('project_name', '?')}",
                f"[b]Version:[/b] {config.get('version', '?')}",
                f"[b]Default Engine:[/b] {config.get('default_engine', '?')}",
            ]
            self.query_one("#project-info", Static).update("\n".join(lines))
        except Exception:
            pass

    def _get_selected_engine_name(self) -> str | None:
        """Get the name from the currently selected engine row."""
        table = self.query_one("#engines-table", DataTable)
        if table.cursor_row is not None and table.row_count > 0:
            row = table.get_row_at(table.cursor_row)
            return str(row[0]) if row else None
        return None

    def action_new_engine(self) -> None:
        """Open engine creation form."""
        from miniautogen.tui.screens.create_form import CreateFormScreen

        self.app.push_screen(
            CreateFormScreen(resource_type="engine"),
            callback=self._on_form_result,
        )

    def action_edit_engine(self) -> None:
        """Open engine edit form."""
        name = self._get_selected_engine_name()
        if not name:
            self.app.notify("No engine selected", severity="warning")
            return
        from miniautogen.tui.screens.create_form import CreateFormScreen

        self.app.push_screen(
            CreateFormScreen(resource_type="engine", edit_name=name),
            callback=self._on_form_result,
        )

    def action_delete_engine(self) -> None:
        """Delete selected engine with confirmation."""
        name = self._get_selected_engine_name()
        if not name:
            self.app.notify("No engine selected", severity="warning")
            return
        from miniautogen.tui.screens.confirm_dialog import ConfirmDialog

        self.app.push_screen(
            ConfirmDialog(f"Delete engine '{name}'?"),
            callback=lambda confirmed: self._do_delete_engine(name) if confirmed else None,
        )

    def _do_delete_engine(self, name: str) -> None:
        """Perform the actual engine deletion after confirmation."""
        if self.provider is None:
            return
        try:
            self.provider.delete_engine(name)
            self.app.notify(f"Engine '{name}' deleted")
            self._refresh_engines()
        except Exception as exc:
            self.app.notify(str(exc), severity="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle server control and theme button clicks."""
        if event.button.id == "btn-server-start":
            self.action_server_start()
        elif event.button.id == "btn-server-stop":
            self.action_server_stop()
        elif event.button.id == "btn-theme-switch":
            self.action_cycle_theme()

    def action_server_start(self) -> None:
        """Start the server."""
        if self.provider:
            try:
                result = self.provider.start_server(daemon=True)
                self.app.notify(str(result))
            except Exception as e:
                self.app.notify(str(e), severity="error")

    def action_server_stop(self) -> None:
        """Stop the server."""
        if self.provider:
            try:
                result = self.provider.stop_server()
                self.app.notify(str(result))
            except Exception as e:
                self.app.notify(str(e), severity="error")

    def action_cycle_theme(self) -> None:
        """Cycle to the next available theme and apply it."""
        theme_names = list(THEMES.keys())
        current = getattr(self.app, "_current_theme", "tokyo-night")
        try:
            idx = theme_names.index(current)
            next_idx = (idx + 1) % len(theme_names)
            next_theme = theme_names[next_idx]
            self.app.apply_theme(next_theme)
            self.query_one("#btn-theme-switch", Button).label = (
                f"[T] Theme: {next_theme}"
            )
            self.app.notify(f"Theme changed to {next_theme}")
        except Exception as e:
            self.app.notify(f"Theme switch failed: {e}", severity="error")

    def action_refresh(self) -> None:
        """Refresh engines and project info."""
        self._refresh_engines()
        self._refresh_project()
        self.app.notify("Refreshed")

    def _on_form_result(self, result: bool) -> None:
        """Callback from form screen."""
        if result:
            self._refresh_engines()
