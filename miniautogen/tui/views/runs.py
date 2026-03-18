"""`:runs` view -- run history."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import DataTable

from miniautogen.tui.views.base import SecondaryView


class RunsView(SecondaryView):
    VIEW_TITLE = "Runs"

    def compose_content(self) -> ComposeResult:
        table = DataTable(id="runs-table")
        table.add_columns("Run ID", "Pipeline", "Status", "Started", "Duration", "Events")
        yield table
