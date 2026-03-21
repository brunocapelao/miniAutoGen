"""MonitorView: secondary screen with runs + events sub-tabs."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Static, TabbedContent, TabPane

from miniautogen.tui.views.base import SecondaryView


class MonitorView(SecondaryView):
    """Secondary view showing run history and event stream."""

    VIEW_TITLE = "Monitor"

    BINDINGS = [
        Binding("escape", "pop_screen", "Back", show=True),
        Binding("r", "refresh", "Refresh", show=True),
    ]

    def compose_content(self) -> ComposeResult:
        """Compose the Monitor view with Runs and Events tabs."""
        with TabbedContent("Runs", "Events"):
            with TabPane("Runs", id="runs-pane"):
                hint = Static(
                    "[dim]Press [b]r[/b] to refresh[/dim]",
                    id="runs-hint",
                )
                yield hint
                table = DataTable(id="runs-table")
                table.add_columns("Run ID", "Flow", "Status", "Duration")
                yield table
                yield Static(
                    "No runs yet.",
                    id="runs-empty",
                    classes="empty-state",
                )
            with TabPane("Events", id="events-pane"):
                hint = Static(
                    "[dim]Press [b]r[/b] to refresh[/dim]",
                    id="events-hint",
                )
                yield hint
                events_table = DataTable(id="events-table")
                events_table.add_columns("Timestamp", "Type", "Agent", "Payload")
                yield events_table
                yield Static(
                    "No events yet.",
                    id="events-empty",
                    classes="empty-state",
                )

    def on_mount(self) -> None:
        """Populate tables with data on mount."""
        self._refresh_runs()
        self._refresh_events()

    def _refresh_runs(self) -> None:
        """Reload run data into the runs table."""
        table = self.query_one("#runs-table", DataTable)
        table.clear()
        if self.provider is None:
            self._set_empty_visible("runs-empty", True)
            return
        runs = self.provider.get_runs()
        for run in runs:
            table.add_row(
                str(run.get("run_id", ""))[:8],
                run.get("pipeline_name", ""),
                run.get("status", ""),
                str(run.get("duration", "")),
            )
        self._set_empty_visible("runs-empty", table.row_count == 0)

    def _refresh_events(self) -> None:
        """Reload event data into the events table."""
        table = self.query_one("#events-table", DataTable)
        table.clear()
        if self.provider is None:
            self._set_empty_visible("events-empty", True)
            return
        events = self.provider.get_events()
        for event in events:
            table.add_row(
                event.get("timestamp", ""),
                event.get("type", ""),
                event.get("agent", ""),
                event.get("payload", ""),
            )
        self._set_empty_visible("events-empty", table.row_count == 0)

    def _set_empty_visible(self, element_id: str, visible: bool) -> None:
        """Show or hide an empty-state message."""
        try:
            empty = self.query_one(f"#{element_id}", Static)
            empty.display = visible
        except Exception:
            pass

    def action_refresh(self) -> None:
        """Refresh both runs and events tables."""
        self._refresh_runs()
        self._refresh_events()
        self.notify("Refreshed")
