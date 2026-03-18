"""`:events` view -- raw event stream with filters."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Input, Static

from miniautogen.tui.views.base import SecondaryView


class EventsView(SecondaryView):
    """Raw event stream with filter support.

    Filter syntax:
    - `/error`, `/approval`, `/tool` -- filter by event type
    - `@planner`, `@writer` -- filter by agent
    - Any other text -- filter by content keyword
    """

    VIEW_TITLE = "Events"

    BINDINGS = [
        Binding("escape", "pop_screen", "Back", show=True),
        Binding("r", "refresh_events", "Refresh", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._all_events: list[dict] = []

    def compose_content(self) -> ComposeResult:
        yield Static(
            "[dim]Filter: /type  @agent  keyword[/dim]",
            id="events-hint",
        )
        yield Input(placeholder="Filter events (type, run_id, agent_id)...", id="event-filter")
        table = DataTable(id="events-table")
        table.add_columns("Timestamp", "Type", "Run ID", "Agent", "Payload")
        yield table

    def on_mount(self) -> None:
        """Populate table with events on mount."""
        self._refresh_table()

    def _refresh_table(self) -> None:
        """Reload event data into the table."""
        if self.provider is not None:
            self._all_events = self.provider.get_events()
        self._apply_filter("")

    def _apply_filter(self, filter_text: str) -> None:
        """Apply filter to events and update table."""
        table = self.query_one("#events-table", DataTable)
        table.clear()

        for event in self._all_events:
            if not self._matches_filter(event, filter_text):
                continue
            table.add_row(
                str(event.get("timestamp", "")),
                event.get("type", "?"),
                str(event.get("run_id", ""))[:8],
                event.get("agent", ""),
                str(event.get("payload", ""))[:60],
            )

    def _matches_filter(self, event: dict, filter_text: str) -> bool:
        """Check if an event matches the filter string."""
        if not filter_text:
            return True

        ft = filter_text.strip()

        # Filter by type: /error, /approval, etc.
        if ft.startswith("/"):
            type_filter = ft[1:].lower()
            return type_filter in event.get("type", "").lower()

        # Filter by agent: @planner, @writer, etc.
        if ft.startswith("@"):
            agent_filter = ft[1:].lower()
            return agent_filter in event.get("agent", "").lower()

        # General keyword search across all fields
        ft_lower = ft.lower()
        searchable = " ".join(
            str(v).lower() for v in event.values()
        )
        return ft_lower in searchable

    def on_input_changed(self, event: Input.Changed) -> None:
        """React to filter input changes in real-time."""
        if event.input.id == "event-filter":
            self._apply_filter(event.value)

    def add_event(self, event_data: dict) -> None:
        """Add a live event to the view (called from workspace)."""
        self._all_events.append(event_data)
        try:
            filter_input = self.query_one("#event-filter", Input)
            self._apply_filter(filter_input.value)
        except Exception:
            self._apply_filter("")

    def action_refresh_events(self) -> None:
        """Refresh events."""
        self._refresh_table()
        self.notify("Refreshed")
