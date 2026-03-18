"""`:agents` view -- agent roster with DataTable CRUD."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import DataTable

from miniautogen.tui.views.base import SecondaryView


class AgentsView(SecondaryView):
    """Agent roster view with DataTable."""

    VIEW_TITLE = "Agents"

    def compose_content(self) -> ComposeResult:
        table = DataTable(id="agents-table")
        table.add_columns("ID", "Name", "Role", "Engine", "Status")
        yield table
