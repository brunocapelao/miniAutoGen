"""`:engines` view -- engine profiles."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import DataTable

from miniautogen.tui.views.base import SecondaryView


class EnginesView(SecondaryView):
    VIEW_TITLE = "Engines"

    def compose_content(self) -> ComposeResult:
        table = DataTable(id="engines-table")
        table.add_columns("Name", "Kind", "Provider", "Model", "Temperature")
        yield table
