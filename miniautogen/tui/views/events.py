"""`:events` view -- raw event stream with filters."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import DataTable, Input

from miniautogen.tui.views.base import SecondaryView


class EventsView(SecondaryView):
    """Raw event stream with filter support."""

    VIEW_TITLE = "Events"

    def compose_content(self) -> ComposeResult:
        yield Input(placeholder="Filter events (type, run_id, agent_id)...", id="event-filter")
        table = DataTable(id="events-table")
        table.add_columns("Timestamp", "Type", "Run ID", "Agent", "Payload")
        yield table
