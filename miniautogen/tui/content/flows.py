"""Flows tab: DataTable with CRUD and run trigger."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import DataTable, Static

from miniautogen.tui.messages import RunStarted, SidebarRefresh


class FlowsContent(Widget, can_focus=True):
    """Flows tab with DataTable CRUD and run trigger."""

    DEFAULT_CSS = """
    FlowsContent {
        height: 1fr;
    }
    FlowsContent .content-header {
        height: auto;
        padding: 1 2 0 2;
    }
    FlowsContent .content-title {
        text-style: bold;
        color: $text;
        height: 1;
    }
    FlowsContent .content-hint {
        color: $text-muted;
        height: 1;
        margin: 0 0 1 0;
    }
    FlowsContent DataTable {
        height: 1fr;
        width: 1fr;
        margin: 0 2;
    }
    FlowsContent .crud-empty {
        content-align: center middle;
        height: 1fr;
        color: $text-muted;
        text-style: italic;
        padding: 4;
    }
    """

    BINDINGS = [
        Binding("n", "new_flow", "New", show=True),
        Binding("e", "edit_flow", "Edit", show=True),
        Binding("x", "delete_flow", "Delete", show=True),
        Binding("r", "run_flow", "Run", show=True),
        Binding("f5", "refresh", "Refresh", show=True),
    ]

    @property
    def provider(self):
        """Access the DashDataProvider from the app."""
        return getattr(self.app, "_provider", None)

    def compose(self) -> ComposeResult:
        """Compose the flows content sections."""
        with Vertical(classes="content-header"):
            yield Static("Flows", classes="content-title")
            yield Static(
                "Keys: [bold]n[/bold] new  [bold]e[/bold] edit  [bold]x[/bold] delete  [bold]r[/bold] run  [bold]F5[/bold] refresh",
                classes="content-hint",
            )
        table = DataTable(id="flows-table")
        table.add_columns("Name", "Mode", "Agents", "Status")
        yield table
        yield Static(
            "No flows defined.\nPress [bold]n[/bold] to create one.",
            id="flows-empty",
            classes="crud-empty",
        )

    def on_mount(self) -> None:
        """Populate table with flow data on mount."""
        self._refresh_table()

    def _refresh_table(self) -> None:
        """Reload flow data into the table."""
        table = self.query_one("#flows-table", DataTable)
        table.clear()
        if self.provider is None:
            self._set_empty_visible(True)
            return
        pipelines = self.provider.get_pipelines()
        for pipeline in pipelines:
            agents = pipeline.get("participants", [])
            agent_count = len(agents) if isinstance(agents, list) else str(agents)
            table.add_row(
                pipeline.get("name", "?"),
                pipeline.get("mode", "workflow"),
                str(agent_count),
                "ready",
            )
        self._set_empty_visible(table.row_count == 0)

    def _set_empty_visible(self, visible: bool) -> None:
        """Show or hide the empty-state message."""
        try:
            empty = self.query_one("#flows-empty", Static)
            table = self.query_one("#flows-table", DataTable)
            empty.display = visible
            table.display = not visible
        except Exception:
            pass

    def _get_selected_name(self) -> str | None:
        """Get the name from the currently selected row."""
        table = self.query_one("#flows-table", DataTable)
        if table.cursor_row is not None and table.row_count > 0:
            row = table.get_row_at(table.cursor_row)
            return str(row[0]) if row else None
        return None

    def action_new_flow(self) -> None:
        """Open flow creation form."""
        from miniautogen.tui.screens.create_form import CreateFormScreen

        self.app.push_screen(
            CreateFormScreen(resource_type="pipeline"),
            callback=self._on_form_result,
        )

    def action_edit_flow(self) -> None:
        """Open flow edit form."""
        name = self._get_selected_name()
        if not name:
            self.notify("No flow selected", severity="warning")
            return
        from miniautogen.tui.screens.create_form import CreateFormScreen

        self.app.push_screen(
            CreateFormScreen(resource_type="pipeline", edit_name=name),
            callback=self._on_form_result,
        )

    def action_delete_flow(self) -> None:
        """Delete selected flow with confirmation."""
        name = self._get_selected_name()
        if not name:
            self.notify("No flow selected", severity="warning")
            return
        from miniautogen.tui.screens.confirm_dialog import ConfirmDialog

        self.app.push_screen(
            ConfirmDialog(f"Delete flow '{name}'? This action cannot be undone."),
            callback=lambda confirmed: self._do_delete_flow(name) if confirmed else None,
        )

    def _do_delete_flow(self, name: str) -> None:
        """Perform the actual flow deletion after confirmation."""
        if self.provider is None:
            return
        try:
            self.provider.delete_pipeline(name)
            self.notify(f"Flow '{name}' deleted")
            self._refresh_table()
            self.app.post_message(SidebarRefresh())
        except (ValueError, KeyError) as exc:
            self.notify(str(exc), severity="error")

    def action_run_flow(self) -> None:
        """Start execution of the selected flow."""
        name = self._get_selected_name()
        if not name:
            self.notify("No flow selected", severity="warning")
            return
        self.post_message(RunStarted(flow_name=name, run_id=""))
        self.notify(f"Starting flow '{name}'...")

    def action_refresh(self) -> None:
        """Refresh the flows table."""
        self._refresh_table()
        self.notify("Refreshed")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle click/Enter on a DataTable row -- open edit form."""
        if event.data_table.id == "flows-table":
            row = event.data_table.get_row(event.row_key)
            if row:
                name = str(row[0])
                from miniautogen.tui.screens.create_form import CreateFormScreen

                self.app.push_screen(
                    CreateFormScreen(resource_type="pipeline", edit_name=name),
                    callback=self._on_form_result,
                )

    def _on_form_result(self, result: object) -> None:
        """Callback from form screen."""
        if result:
            self._refresh_table()
            self.app.post_message(SidebarRefresh())
