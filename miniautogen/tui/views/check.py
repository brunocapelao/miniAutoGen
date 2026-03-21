"""`:check` view -- project health check with DataTable."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Static

from miniautogen.tui.views.base import SecondaryView


class CheckView(SecondaryView):
    """Project health check view displaying validation results."""

    VIEW_TITLE = "Project health check"

    BINDINGS = [
        Binding("escape", "pop_screen", "Back", show=True),
        Binding("r", "rerun_checks", "Re-run", show=True),
    ]

    def compose_content(self) -> ComposeResult:
        yield Static(
            "[dim]Keys: [b]r[/b]efresh[/dim]",
            id="check-hint",
        )
        table = DataTable(id="check-table")
        table.add_columns("Status", "Category", "Check Name", "Message")
        yield table
        yield Static(
            "No project found -- checks unavailable.",
            id="check-empty",
            classes="empty-state",
        )

    def on_mount(self) -> None:
        """Run checks on mount."""
        self._run_checks()

    def _run_checks(self) -> None:
        """Execute check_project and populate the DataTable."""
        table = self.query_one("#check-table", DataTable)
        table.clear()

        if self.provider is None:
            self._set_empty_visible(True)
            return

        results = self.provider.check_project()
        if not results:
            self._set_empty_visible(True)
            return

        self._set_empty_visible(False)
        for result in results:
            if result.warning:
                status_icon = "[yellow]⚠[/yellow]"
            elif result.passed:
                status_icon = "[green]✓[/green]"
            else:
                status_icon = "[red]✗[/red]"

            table.add_row(
                status_icon,
                result.category,
                result.name,
                result.message,
            )

    def _set_empty_visible(self, visible: bool) -> None:
        """Show or hide the empty-state message."""
        try:
            empty = self.query_one("#check-empty", Static)
            empty.display = visible
        except Exception:
            pass

    def action_rerun_checks(self) -> None:
        """Re-run all project checks."""
        self._run_checks()
        self.notify("Checks refreshed")
