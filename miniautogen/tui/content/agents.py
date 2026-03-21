"""Agents tab: DataTable with CRUD operations."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import DataTable, Static

from miniautogen.tui.messages import SidebarRefresh


class AgentsContent(Widget, can_focus=True):
    """Agents tab with DataTable CRUD."""

    DEFAULT_CSS = """
    AgentsContent {
        height: 1fr;
    }
    AgentsContent .content-header {
        height: auto;
        padding: 1 2 0 2;
    }
    AgentsContent .content-title {
        text-style: bold;
        color: $text;
        height: 1;
    }
    AgentsContent .content-hint {
        color: $text-muted;
        height: 1;
        margin: 0 0 1 0;
    }
    AgentsContent DataTable {
        height: 1fr;
        width: 1fr;
        margin: 0 2;
    }
    AgentsContent .crud-empty {
        content-align: center middle;
        height: 1fr;
        color: $text-muted;
        text-style: italic;
        padding: 4;
    }
    """

    BINDINGS = [
        Binding("n", "new_agent", "New", show=True),
        Binding("e", "edit_agent", "Edit", show=True),
        Binding("x", "delete_agent", "Delete", show=True),
        Binding("f5", "refresh", "Refresh", show=True),
        Binding("enter", "view_detail", "Detail", show=True),
    ]

    @property
    def provider(self):
        """Access the DashDataProvider from the app."""
        return getattr(self.app, "_provider", None)

    def compose(self) -> ComposeResult:
        """Compose the agents content sections."""
        with Vertical(classes="content-header"):
            yield Static("Agents", classes="content-title")
            yield Static(
                "Keys: [bold]n[/bold] new  [bold]e[/bold] edit  [bold]x[/bold] delete  [bold]F5[/bold] refresh  [bold]Enter[/bold] detail",
                classes="content-hint",
            )
        table = DataTable(id="agents-table")
        table.add_columns("Name", "Role", "Engine", "Status")
        yield table
        yield Static(
            "No agents yet.\nPress [bold]n[/bold] to create one.",
            id="agents-empty",
            classes="crud-empty",
        )

    def on_mount(self) -> None:
        """Populate table with agent data on mount."""
        self._refresh_table()

    def _refresh_table(self) -> None:
        """Reload agent data into the table."""
        table = self.query_one("#agents-table", DataTable)
        table.clear()
        if self.provider is None:
            self._set_empty_visible(True)
            return
        agents = self.provider.get_agents()
        for agent in agents:
            table.add_row(
                agent.get("name", "?"),
                agent.get("role", "?"),
                agent.get("engine_profile", "?"),
                "ready",
            )
        self._set_empty_visible(table.row_count == 0)

    def _set_empty_visible(self, visible: bool) -> None:
        """Show or hide the empty-state message."""
        try:
            empty = self.query_one("#agents-empty", Static)
            table = self.query_one("#agents-table", DataTable)
            empty.display = visible
            table.display = not visible
        except Exception:
            pass

    def _get_selected_name(self) -> str | None:
        """Get the name from the currently selected row."""
        table = self.query_one("#agents-table", DataTable)
        if table.cursor_row is not None and table.row_count > 0:
            row = table.get_row_at(table.cursor_row)
            return str(row[0]) if row else None
        return None

    def action_new_agent(self) -> None:
        """Open agent creation form."""
        from miniautogen.tui.screens.create_form import CreateFormScreen

        self.app.push_screen(
            CreateFormScreen(resource_type="agent"),
            callback=self._on_form_result,
        )

    def action_edit_agent(self) -> None:
        """Open agent edit form."""
        name = self._get_selected_name()
        if not name:
            self.notify("No agent selected", severity="warning")
            return
        from miniautogen.tui.screens.create_form import CreateFormScreen

        self.app.push_screen(
            CreateFormScreen(resource_type="agent", edit_name=name),
            callback=self._on_form_result,
        )

    def action_delete_agent(self) -> None:
        """Delete selected agent with confirmation."""
        name = self._get_selected_name()
        if not name:
            self.notify("No agent selected", severity="warning")
            return
        from miniautogen.tui.screens.confirm_dialog import ConfirmDialog

        self.app.push_screen(
            ConfirmDialog(f"Delete agent '{name}'? This action cannot be undone."),
            callback=lambda confirmed: self._do_delete_agent(name) if confirmed else None,
        )

    def _do_delete_agent(self, name: str) -> None:
        """Perform the actual agent deletion after confirmation."""
        if self.provider is None:
            return
        try:
            self.provider.delete_agent(name)
            self.notify(f"Agent '{name}' deleted")
            self._refresh_table()
            self.app.post_message(SidebarRefresh())
        except (ValueError, KeyError) as exc:
            self.notify(str(exc), severity="error")

    def action_refresh(self) -> None:
        """Refresh the agents table."""
        self._refresh_table()
        self.notify("Refreshed")

    def action_view_detail(self) -> None:
        """View details of the selected agent."""
        name = self._get_selected_name()
        if not name or self.provider is None:
            return
        try:
            agent_data = self.provider.get_agent(name) if hasattr(
                self.provider, "get_agent"
            ) else None
            if agent_data:
                from miniautogen.tui.screens.agent_detail import AgentDetailScreen

                self.app.push_screen(AgentDetailScreen(agent_data))
        except Exception:
            pass

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle click/Enter on a DataTable row -- view agent detail."""
        if event.data_table.id == "agents-table":
            row = event.data_table.get_row(event.row_key)
            if row:
                name = str(row[0])
                if self.provider is not None and hasattr(self.provider, "get_agent"):
                    try:
                        agent_data = self.provider.get_agent(name)
                        if agent_data:
                            from miniautogen.tui.screens.agent_detail import AgentDetailScreen

                            self.app.push_screen(AgentDetailScreen(agent_data))
                    except Exception:
                        pass

    def _on_form_result(self, result: object) -> None:
        """Callback from form screen."""
        if result:
            self._refresh_table()
            self.app.post_message(SidebarRefresh())
