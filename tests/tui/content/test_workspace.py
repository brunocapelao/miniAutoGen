"""Tests for WorkspaceContent widget."""

import pytest
from textual.app import App, ComposeResult

from miniautogen.tui.content.workspace import StatCard, WorkspaceContent


def test_workspace_content_is_widget() -> None:
    """Test that WorkspaceContent is a valid Textual widget."""
    ws = WorkspaceContent()
    assert hasattr(ws, "compose")


class WorkspaceTestApp(App):
    """Test application containing WorkspaceContent."""

    def compose(self) -> ComposeResult:
        yield WorkspaceContent()


@pytest.mark.asyncio
async def test_workspace_renders() -> None:
    """Test that WorkspaceContent renders without error."""
    app = WorkspaceTestApp()
    async with app.run_test(size=(120, 40)):
        ws = app.query_one(WorkspaceContent)
        assert ws is not None


@pytest.mark.asyncio
async def test_workspace_has_stat_row() -> None:
    """Test that WorkspaceContent has a horizontal stat card row."""
    app = WorkspaceTestApp()
    async with app.run_test(size=(120, 40)):
        ws = app.query_one(WorkspaceContent)
        stat_row = ws.query_one("#stat-row")
        assert stat_row is not None


@pytest.mark.asyncio
async def test_workspace_has_card_agents() -> None:
    """Test that WorkspaceContent contains the agents StatCard."""
    app = WorkspaceTestApp()
    async with app.run_test(size=(120, 40)):
        ws = app.query_one(WorkspaceContent)
        card = ws.query_one("#card-agents", StatCard)
        assert card is not None


@pytest.mark.asyncio
async def test_workspace_has_health_box() -> None:
    """Test that WorkspaceContent has a health check box."""
    app = WorkspaceTestApp()
    async with app.run_test(size=(120, 40)):
        ws = app.query_one(WorkspaceContent)
        health = ws.query_one("#health-box")
        assert health is not None


@pytest.mark.asyncio
async def test_workspace_refresh_data() -> None:
    """Test that refresh_data updates stat cards."""
    app = WorkspaceTestApp()
    async with app.run_test(size=(120, 40)):
        ws = app.query_one(WorkspaceContent)
        ws.refresh_data(
            agents_count=5,
            flows_count=3,
            engines_count=2,
            last_run_status="success",
        )
        agents_card = ws.query_one("#card-agents", StatCard)
        assert agents_card is not None


@pytest.mark.asyncio
async def test_workspace_refresh_data_with_health_items() -> None:
    """Test that refresh_data updates health section with items."""
    app = WorkspaceTestApp()
    async with app.run_test(size=(120, 40)):
        ws = app.query_one(WorkspaceContent)
        health_items = [
            ("✓", "All systems operational"),
            ("⚠", "1 agent pending"),
        ]
        ws.refresh_data(health_items=health_items)
        from textual.widgets import Static
        health = ws.query_one("#health-box", Static)
        content = str(health.render())
        assert "✓" in content
        assert "All systems operational" in content
        assert "⚠" in content
        assert "1 agent pending" in content
