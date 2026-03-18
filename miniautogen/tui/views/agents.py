"""`:agents` view -- agent roster with DataTable CRUD."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Static

from miniautogen.tui.views.base import SecondaryView


class AgentsView(SecondaryView):
    """Agent roster view with DataTable and CRUD operations."""

    VIEW_TITLE = "Agents"

    BINDINGS = [
        Binding("escape", "pop_screen", "Back", show=True),
        Binding("n", "new_agent", "New", show=True),
        Binding("e", "edit_agent", "Edit", show=True),
        Binding("d", "delete_agent", "Delete", show=True),
        Binding("r", "refresh_agents", "Refresh", show=True),
    ]

    def compose_content(self) -> ComposeResult:
        yield Static(
            "[dim]Keys: [b]n[/b]ew  [b]e[/b]dit  [b]d[/b]elete  [b]r[/b]efresh[/dim]",
            id="agents-hint",
        )
        table = DataTable(id="agents-table")
        table.add_columns("Name", "Role", "Engine", "Status")
        yield table

    def on_mount(self) -> None:
        """Populate table with agent data on mount."""
        self._refresh_table()

    def _refresh_table(self) -> None:
        """Reload agent data into the table."""
        table = self.query_one("#agents-table", DataTable)
        table.clear()
        if self.provider is None:
            return
        for agent in self.provider.get_agents():
            table.add_row(
                agent.get("name", "?"),
                agent.get("role", "?"),
                agent.get("engine_profile", "?"),
                "ready",
            )

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
        if self.provider is None:
            return
        try:
            self.provider.delete_agent(name)
            self.notify(f"Agent '{name}' deleted")
            self._refresh_table()
        except (ValueError, KeyError) as exc:
            self.notify(str(exc), severity="error")

    def action_refresh_agents(self) -> None:
        """Refresh the agents table."""
        self._refresh_table()
        self.notify("Refreshed")

    def _on_form_result(self, result: object) -> None:
        """Callback from form screen."""
        if result:
            self._refresh_table()
