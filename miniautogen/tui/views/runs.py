"""`:runs` view -- run history."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Static

from miniautogen.tui.views.base import SecondaryView


class RunsView(SecondaryView):
    VIEW_TITLE = "Runs"

    BINDINGS = [
        Binding("escape", "pop_screen", "Back", show=True),
        Binding("r", "refresh_runs", "Refresh", show=True),
        Binding("enter", "show_detail", "Detail", show=True),
    ]

    def compose_content(self) -> ComposeResult:
        yield Static(
            "[dim]Keys: [b]Enter[/b] detail  [b]r[/b]efresh[/dim]",
            id="runs-hint",
        )
        table = DataTable(id="runs-table")
        table.add_columns("Run ID", "Pipeline", "Status", "Started", "Duration", "Events")
        yield table

    def on_mount(self) -> None:
        """Populate table with run data on mount."""
        self._refresh_table()

    def _refresh_table(self) -> None:
        """Reload run data into the table."""
        table = self.query_one("#runs-table", DataTable)
        table.clear()
        if self.provider is None:
            return
        runs = self.provider.get_runs()
        if not runs:
            self.notify("No runs recorded yet", severity="information")
            return
        for run in runs:
            table.add_row(
                str(run.get("run_id", "?"))[:8],
                run.get("pipeline", "?"),
                run.get("status", "?"),
                str(run.get("started", "")),
                str(run.get("duration", "")),
                str(run.get("events", 0)),
            )

    def action_refresh_runs(self) -> None:
        """Refresh runs table."""
        self._refresh_table()
        self.notify("Refreshed")

    def action_show_detail(self) -> None:
        """Show detail for the selected run."""
        table = self.query_one("#runs-table", DataTable)
        if table.cursor_row is not None and table.row_count > 0:
            row = table.get_row_at(table.cursor_row)
            if row:
                self.notify(f"Run: {row[0]} | Status: {row[2]}")
