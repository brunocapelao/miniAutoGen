"""`:engines` view -- engine profiles with DataTable CRUD."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Static

from miniautogen.tui.views.base import SecondaryView


class EnginesView(SecondaryView):
    VIEW_TITLE = "Engines"

    BINDINGS = [
        Binding("escape", "pop_screen", "Back", show=True),
        Binding("n", "new_engine", "New", show=True),
        Binding("e", "edit_engine", "Edit", show=True),
        Binding("d", "delete_engine", "Delete", show=True),
        Binding("r", "refresh_engines", "Refresh", show=True),
    ]

    def compose_content(self) -> ComposeResult:
        yield Static(
            "[dim]Keys: [b]n[/b]ew  [b]e[/b]dit  [b]d[/b]elete  [b]r[/b]efresh[/dim]",
            id="engines-hint",
        )
        table = DataTable(id="engines-table")
        table.add_columns("Name", "Kind", "Provider", "Model", "Temperature")
        yield table

    def on_mount(self) -> None:
        """Populate table with engine data on mount."""
        self._refresh_table()

    def _refresh_table(self) -> None:
        """Reload engine data into the table."""
        table = self.query_one("#engines-table", DataTable)
        table.clear()
        if self.provider is None:
            return
        for engine in self.provider.get_engines():
            table.add_row(
                engine.get("name", "?"),
                engine.get("kind", "api"),
                engine.get("provider", "?"),
                engine.get("model", "?"),
                str(engine.get("temperature", "0.2")),
            )

    def _get_selected_name(self) -> str | None:
        """Get the name from the currently selected row."""
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
        name = self._get_selected_name()
        if not name:
            self.notify("No engine selected", severity="warning")
            return
        from miniautogen.tui.screens.create_form import CreateFormScreen

        self.app.push_screen(
            CreateFormScreen(resource_type="engine", edit_name=name),
            callback=self._on_form_result,
        )

    def action_delete_engine(self) -> None:
        """Delete selected engine with confirmation."""
        name = self._get_selected_name()
        if not name:
            self.notify("No engine selected", severity="warning")
            return
        if self.provider is None:
            return
        try:
            self.provider.delete_engine(name)
            self.notify(f"Engine '{name}' deleted")
            self._refresh_table()
        except (ValueError, KeyError) as exc:
            self.notify(str(exc), severity="error")

    def action_refresh_engines(self) -> None:
        """Refresh the engines table."""
        self._refresh_table()
        self.notify("Refreshed")

    def _on_form_result(self, result: object) -> None:
        """Callback from form screen."""
        if result:
            self._refresh_table()
