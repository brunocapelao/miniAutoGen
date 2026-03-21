"""Tests for TabBar widget."""
import pytest
from textual.app import App, ComposeResult
from miniautogen.tui.widgets.tab_bar import TabBar


def test_tab_bar_is_widget() -> None:
    """TabBar should be a Textual widget."""
    bar = TabBar()
    assert hasattr(bar, "compose")


def test_tab_bar_default_tabs() -> None:
    """TabBar should have four default tabs."""
    bar = TabBar()
    assert bar.tab_names == ["Workspace", "Flows", "Agents", "Config"]


def test_tab_bar_active_tab_default() -> None:
    """TabBar should default to 'Workspace' as active."""
    bar = TabBar()
    assert bar.active_tab == "Workspace"


def test_tab_bar_set_active() -> None:
    """Setting active_tab property should work."""
    bar = TabBar()
    bar.active_tab = "Flows"
    assert bar.active_tab == "Flows"


class TabBarTestApp(App):
    """Test harness for TabBar."""

    def compose(self) -> ComposeResult:
        yield TabBar()


@pytest.mark.asyncio
async def test_tab_bar_renders() -> None:
    """TabBar should render with default active tab."""
    app = TabBarTestApp()
    async with app.run_test(size=(120, 5)) as pilot:
        bar = app.query_one(TabBar)
        assert bar.active_tab == "Workspace"


@pytest.mark.asyncio
async def test_tab_bar_switch_programmatic() -> None:
    """Programmatic tab switches should update active_tab."""
    app = TabBarTestApp()
    async with app.run_test(size=(120, 5)) as pilot:
        bar = app.query_one(TabBar)
        bar.active_tab = "Flows"
        assert bar.active_tab == "Flows"
        bar.active_tab = "Agents"
        assert bar.active_tab == "Agents"
        bar.active_tab = "Config"
        assert bar.active_tab == "Config"
        bar.active_tab = "Workspace"
        assert bar.active_tab == "Workspace"
