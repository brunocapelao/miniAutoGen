"""`:pipelines` view -- pipeline list with DataTable CRUD."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import DataTable

from miniautogen.tui.views.base import SecondaryView


class PipelinesView(SecondaryView):
    VIEW_TITLE = "Pipelines"

    def compose_content(self) -> ComposeResult:
        table = DataTable(id="pipelines-table")
        table.add_columns("Name", "Target", "Mode", "Agents", "Status")
        yield table
