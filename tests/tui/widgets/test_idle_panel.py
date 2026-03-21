"""Tests for the IdlePanel widget -- sidebar idle state."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widget import Widget

from miniautogen.tui.widgets.idle_panel import IdlePanel


def test_idle_panel_is_widget() -> None:
    """IdlePanel should be a Widget subclass."""
    assert issubclass(IdlePanel, Widget)
    panel = IdlePanel()
    assert hasattr(panel, "compose")


def test_idle_panel_initial_state() -> None:
    """IdlePanel should start with no agents or runs."""
    panel = IdlePanel()
    assert panel.agent_count == 0
    assert panel.run_count == 0


def test_idle_panel_set_agents() -> None:
    """IdlePanel should store and count agents."""
    panel = IdlePanel()
    agents = [
        {"name": "planner", "status": "idle"},
        {"name": "researcher", "status": "idle"},
    ]
    panel.set_agents(agents)
    assert panel.agent_count == 2
    assert panel._agents == agents


def test_idle_panel_set_recent_runs() -> None:
    """IdlePanel should store and count runs, limited to 5."""
    panel = IdlePanel()
    runs = [
        {"flow_name": "research-flow", "status": "done", "ago": "2m"},
        {"flow_name": "analysis-flow", "status": "done", "ago": "5m"},
    ]
    panel.set_recent_runs(runs)
    assert panel.run_count == 2
    assert len(panel._recent_runs) == 2

    # Test that we limit to 5 runs
    many_runs = [{"flow_name": f"flow-{i}", "status": "done", "ago": f"{i}m"} for i in range(10)]
    panel.set_recent_runs(many_runs)
    assert panel.run_count == 5


def test_idle_panel_empty_agents_display() -> None:
    """IdlePanel should handle empty agent list gracefully."""
    panel = IdlePanel()
    panel.set_agents([])
    # Should not raise exception when refreshing
    panel._refresh_team()


def test_idle_panel_empty_runs_display() -> None:
    """IdlePanel should handle empty runs list gracefully."""
    panel = IdlePanel()
    panel.set_recent_runs([])
    # Should not raise exception when refreshing
    panel._refresh_runs()


class IdlePanelTestApp(App):
    """Test harness for IdlePanel."""

    def compose(self) -> ComposeResult:
        yield IdlePanel()


@pytest.mark.asyncio
async def test_idle_panel_renders_empty() -> None:
    """IdlePanel should render in an empty state."""
    app = IdlePanelTestApp()
    async with app.run_test(size=(40, 20)) as pilot:
        panel = app.query_one(IdlePanel)
        assert panel is not None
        assert panel.agent_count == 0
        assert panel.run_count == 0


@pytest.mark.asyncio
async def test_idle_panel_renders_with_agents() -> None:
    """IdlePanel should render with agents displayed."""
    app = IdlePanelTestApp()
    async with app.run_test(size=(40, 20)) as pilot:
        panel = app.query_one(IdlePanel)
        agents = [
            {"name": "planner", "status": "idle"},
            {"name": "researcher", "status": "active"},
        ]
        panel.set_agents(agents)
        await pilot.pause()
        assert panel.agent_count == 2


@pytest.mark.asyncio
async def test_idle_panel_renders_with_recent_runs() -> None:
    """IdlePanel should render with recent runs displayed."""
    app = IdlePanelTestApp()
    async with app.run_test(size=(40, 20)) as pilot:
        panel = app.query_one(IdlePanel)
        runs = [
            {"flow_name": "research-flow", "status": "done", "ago": "2m"},
            {"flow_name": "analysis-flow", "status": "failed", "ago": "15m"},
        ]
        panel.set_recent_runs(runs)
        await pilot.pause()
        assert panel.run_count == 2
