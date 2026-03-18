"""`:pipelines` view -- pipeline list with DataTable CRUD."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Static

from miniautogen.tui.views.base import SecondaryView


class PipelinesView(SecondaryView):
    VIEW_TITLE = "Pipelines"

    BINDINGS = [
        Binding("escape", "pop_screen", "Back", show=True),
        Binding("n", "new_pipeline", "New", show=True),
        Binding("e", "edit_pipeline", "Edit", show=True),
        Binding("d", "delete_pipeline", "Delete", show=True),
        Binding("r", "run_pipeline", "Run", show=True),
        Binding("f5", "refresh_pipelines", "Refresh", show=True),
    ]

    def compose_content(self) -> ComposeResult:
        yield Static(
            "[dim]Keys: [b]n[/b]ew  [b]e[/b]dit  [b]d[/b]elete  [b]r[/b]un  [b]F5[/b] refresh[/dim]",
            id="pipelines-hint",
        )
        table = DataTable(id="pipelines-table")
        table.add_columns("Name", "Target", "Mode", "Agents", "Status")
        yield table

    def on_mount(self) -> None:
        """Populate table with pipeline data on mount."""
        self._refresh_table()

    def _refresh_table(self) -> None:
        """Reload pipeline data into the table."""
        table = self.query_one("#pipelines-table", DataTable)
        table.clear()
        if self.provider is None:
            return
        for pipeline in self.provider.get_pipelines():
            participants = pipeline.get("participants", [])
            agents_str = ", ".join(participants) if participants else "(none)"
            table.add_row(
                pipeline.get("name", "?"),
                pipeline.get("target", "?"),
                pipeline.get("mode", "?"),
                agents_str,
                "ready",
            )

    def _get_selected_name(self) -> str | None:
        """Get the name from the currently selected row."""
        table = self.query_one("#pipelines-table", DataTable)
        if table.cursor_row is not None and table.row_count > 0:
            row = table.get_row_at(table.cursor_row)
            return str(row[0]) if row else None
        return None

    def action_new_pipeline(self) -> None:
        """Open pipeline creation form."""
        from miniautogen.tui.screens.create_form import CreateFormScreen

        self.app.push_screen(
            CreateFormScreen(resource_type="pipeline"),
            callback=self._on_form_result,
        )

    def action_edit_pipeline(self) -> None:
        """Open pipeline edit form."""
        name = self._get_selected_name()
        if not name:
            self.notify("No pipeline selected", severity="warning")
            return
        from miniautogen.tui.screens.create_form import CreateFormScreen

        self.app.push_screen(
            CreateFormScreen(resource_type="pipeline", edit_name=name),
            callback=self._on_form_result,
        )

    def action_delete_pipeline(self) -> None:
        """Delete selected pipeline with confirmation."""
        name = self._get_selected_name()
        if not name:
            self.notify("No pipeline selected", severity="warning")
            return
        if self.provider is None:
            return
        try:
            self.provider.delete_pipeline(name)
            self.notify(f"Pipeline '{name}' deleted")
            self._refresh_table()
        except (ValueError, KeyError) as exc:
            self.notify(str(exc), severity="error")

    def action_run_pipeline(self) -> None:
        """Run the selected pipeline."""
        name = self._get_selected_name()
        if not name:
            self.notify("No pipeline selected", severity="warning")
            return
        self.notify(f"Launching pipeline '{name}'...")
        # Switch to workspace and trigger execution
        self.app.pop_screen()
        self.app.post_message_from_child = name  # type: ignore[attr-defined]

    def action_refresh_pipelines(self) -> None:
        """Refresh the pipelines table."""
        self._refresh_table()
        self.notify("Refreshed")

    def _on_form_result(self, result: object) -> None:
        """Callback from form screen."""
        if result:
            self._refresh_table()
