"""Tests for FlowsContent widget."""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import DataTable

from miniautogen.tui.content.flows import FlowsContent


def test_flows_content_is_widget() -> None:
    """Test that FlowsContent is a valid Textual widget."""
    fc = FlowsContent()
    assert hasattr(fc, "compose")


class FlowsTestApp(App):
    """Test application containing FlowsContent."""

    def compose(self) -> ComposeResult:
        yield FlowsContent()


@pytest.mark.asyncio
async def test_flows_renders() -> None:
    """Test that FlowsContent renders without error."""
    app = FlowsTestApp()
    async with app.run_test(size=(120, 40)):
        fc = app.query_one(FlowsContent)
        assert fc is not None


@pytest.mark.asyncio
async def test_flows_has_data_table() -> None:
    """Test that FlowsContent has a DataTable."""
    app = FlowsTestApp()
    async with app.run_test(size=(120, 40)):
        table = app.query_one(DataTable)
        assert table is not None


@pytest.mark.asyncio
async def test_flows_table_has_columns() -> None:
    """Test that the DataTable has the expected columns."""
    app = FlowsTestApp()
    async with app.run_test(size=(120, 40)):
        table = app.query_one(DataTable)
        # Verify table has columns by checking columns dict
        assert len(table.columns) >= 4


@pytest.mark.asyncio
async def test_flows_table_empty_initially() -> None:
    """Test that the DataTable is empty initially (no provider)."""
    app = FlowsTestApp()
    async with app.run_test(size=(120, 40)):
        table = app.query_one(DataTable)
        assert table.row_count == 0


@pytest.mark.asyncio
async def test_flows_has_title_and_hint() -> None:
    """Test that FlowsContent has title and hint sections."""
    app = FlowsTestApp()
    async with app.run_test(size=(120, 40)):
        fc = app.query_one(FlowsContent)
        # Should have a title Static widget with class "content-title"
        # and a hint Static widget with class "content-hint"
        title = fc.query_one(".content-title")
        hint = fc.query_one(".content-hint")
        assert title is not None
        assert hint is not None


@pytest.mark.asyncio
async def test_flows_has_empty_state() -> None:
    """Test that FlowsContent has an empty-state message."""
    app = FlowsTestApp()
    async with app.run_test(size=(120, 40)):
        fc = app.query_one(FlowsContent)
        empty = fc.query_one("#flows-empty")
        assert empty is not None
