"""Tests for AgentsContent widget."""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import DataTable

from miniautogen.tui.content.agents import AgentsContent


def test_agents_content_is_widget() -> None:
    """Test that AgentsContent is a valid Textual widget."""
    ac = AgentsContent()
    assert hasattr(ac, "compose")


class AgentsTestApp(App):
    """Test application containing AgentsContent."""

    def compose(self) -> ComposeResult:
        yield AgentsContent()


@pytest.mark.asyncio
async def test_agents_renders() -> None:
    """Test that AgentsContent renders without error."""
    app = AgentsTestApp()
    async with app.run_test(size=(120, 40)):
        ac = app.query_one(AgentsContent)
        assert ac is not None


@pytest.mark.asyncio
async def test_agents_has_data_table() -> None:
    """Test that AgentsContent has a DataTable."""
    app = AgentsTestApp()
    async with app.run_test(size=(120, 40)):
        table = app.query_one(DataTable)
        assert table is not None


@pytest.mark.asyncio
async def test_agents_table_has_columns() -> None:
    """Test that the DataTable has the expected columns."""
    app = AgentsTestApp()
    async with app.run_test(size=(120, 40)):
        table = app.query_one(DataTable)
        # Verify table has columns by checking columns dict
        assert len(table.columns) >= 4


@pytest.mark.asyncio
async def test_agents_table_empty_initially() -> None:
    """Test that the DataTable is empty initially (no provider)."""
    app = AgentsTestApp()
    async with app.run_test(size=(120, 40)):
        table = app.query_one(DataTable)
        assert table.row_count == 0


@pytest.mark.asyncio
async def test_agents_has_title_and_hint() -> None:
    """Test that AgentsContent has title and hint sections."""
    app = AgentsTestApp()
    async with app.run_test(size=(120, 40)):
        ac = app.query_one(AgentsContent)
        # Should have a title Static widget with class "content-title"
        # and a hint Static widget with class "content-hint"
        title = ac.query_one(".content-title")
        hint = ac.query_one(".content-hint")
        assert title is not None
        assert hint is not None


@pytest.mark.asyncio
async def test_agents_has_empty_state() -> None:
    """Test that AgentsContent has an empty-state message."""
    app = AgentsTestApp()
    async with app.run_test(size=(120, 40)):
        ac = app.query_one(AgentsContent)
        empty = ac.query_one("#agents-empty")
        assert empty is not None
