"""Tests for the ExecutionSidebar widget -- right panel with idle/active states."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widget import Widget

from miniautogen.tui.widgets.execution_sidebar import ExecutionSidebar
from miniautogen.tui.widgets.idle_panel import IdlePanel
from miniautogen.tui.widgets.interaction_log import InteractionLog


def test_execution_sidebar_is_widget() -> None:
    """ExecutionSidebar should be a Widget subclass."""
    assert issubclass(ExecutionSidebar, Widget)
    sidebar = ExecutionSidebar()
    assert hasattr(sidebar, "compose")


def test_execution_sidebar_starts_idle() -> None:
    """ExecutionSidebar should start with is_executing = False."""
    sidebar = ExecutionSidebar()
    assert sidebar.is_executing is False


def test_execution_sidebar_has_interaction_log() -> None:
    """ExecutionSidebar should have an interaction_log attribute."""
    sidebar = ExecutionSidebar()
    assert hasattr(sidebar, "interaction_log")
    assert isinstance(sidebar.interaction_log, InteractionLog)


def test_execution_sidebar_start_execution() -> None:
    """ExecutionSidebar.start_execution() should set is_executing = True."""
    sidebar = ExecutionSidebar()
    sidebar.start_execution()
    assert sidebar.is_executing is True


def test_execution_sidebar_stop_execution() -> None:
    """ExecutionSidebar.stop_execution() should set is_executing = False."""
    sidebar = ExecutionSidebar()
    sidebar.start_execution()
    assert sidebar.is_executing is True
    sidebar.stop_execution()
    assert sidebar.is_executing is False


def test_execution_sidebar_set_agents() -> None:
    """ExecutionSidebar.set_agents() should proxy to IdlePanel."""
    sidebar = ExecutionSidebar()
    agents = [
        {"name": "planner", "status": "idle"},
        {"name": "researcher", "status": "idle"},
    ]
    # Should not raise exception
    sidebar.set_agents(agents)


def test_execution_sidebar_set_recent_runs() -> None:
    """ExecutionSidebar.set_recent_runs() should proxy to IdlePanel."""
    sidebar = ExecutionSidebar()
    runs = [
        {"flow_name": "research-flow", "status": "done", "ago": "2m"},
        {"flow_name": "analysis-flow", "status": "done", "ago": "5m"},
    ]
    # Should not raise exception
    sidebar.set_recent_runs(runs)


class ExecutionSidebarTestApp(App):
    """Test harness for ExecutionSidebar."""

    def compose(self) -> ComposeResult:
        yield ExecutionSidebar()


@pytest.mark.asyncio
async def test_sidebar_renders_idle() -> None:
    """ExecutionSidebar should render in idle state."""
    app = ExecutionSidebarTestApp()
    async with app.run_test(size=(40, 30)) as pilot:
        sidebar = app.query_one(ExecutionSidebar)
        assert sidebar is not None
        assert sidebar.is_executing is False
        # IdlePanel should be visible
        idle_panel = app.query_one(IdlePanel)
        assert idle_panel is not None


@pytest.mark.asyncio
async def test_sidebar_transitions_to_active() -> None:
    """ExecutionSidebar should show execution log when started."""
    app = ExecutionSidebarTestApp()
    async with app.run_test(size=(40, 30)) as pilot:
        sidebar = app.query_one(ExecutionSidebar)
        sidebar.start_execution()
        await pilot.pause()
        assert sidebar.is_executing is True


@pytest.mark.asyncio
async def test_sidebar_transitions_to_idle_again() -> None:
    """ExecutionSidebar should hide execution log when stopped."""
    app = ExecutionSidebarTestApp()
    async with app.run_test(size=(40, 30)) as pilot:
        sidebar = app.query_one(ExecutionSidebar)
        sidebar.start_execution()
        await pilot.pause()
        assert sidebar.is_executing is True
        sidebar.stop_execution()
        await pilot.pause()
        assert sidebar.is_executing is False


@pytest.mark.asyncio
async def test_sidebar_with_agents_and_runs() -> None:
    """ExecutionSidebar should display agents and runs in idle panel."""
    app = ExecutionSidebarTestApp()
    async with app.run_test(size=(40, 30)) as pilot:
        sidebar = app.query_one(ExecutionSidebar)
        agents = [{"name": "planner", "status": "idle"}]
        runs = [{"flow_name": "research-flow", "status": "done", "ago": "2m"}]
        sidebar.set_agents(agents)
        sidebar.set_recent_runs(runs)
        await pilot.pause()
        idle_panel = app.query_one(IdlePanel)
        assert idle_panel.agent_count == 1
        assert idle_panel.run_count == 1
