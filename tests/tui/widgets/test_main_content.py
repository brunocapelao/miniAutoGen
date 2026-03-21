"""Tests for the MainContent widget -- container that swaps child content widgets per tab."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from miniautogen.tui.widgets.main_content import MainContent


class PlaceholderContent(Widget):
    """Simple placeholder widget for testing."""

    def __init__(self, label: str) -> None:
        super().__init__(id=f"content-{label}")
        self.label = label

    def compose(self) -> ComposeResult:
        yield Static(self.label)


def test_main_content_is_widget() -> None:
    """MainContent should be a Widget subclass."""
    mc = MainContent()
    assert hasattr(mc, "compose")


def test_main_content_register_tab() -> None:
    """MainContent should support registering tabs."""
    mc = MainContent()
    placeholder = PlaceholderContent("Workspace")
    mc.register_tab("Workspace", placeholder)
    assert "Workspace" in mc._tabs
    assert mc._tabs["Workspace"] is placeholder


def test_main_content_multiple_tabs() -> None:
    """MainContent should support multiple registered tabs."""
    mc = MainContent()
    mc.register_tab("Workspace", PlaceholderContent("Workspace"))
    mc.register_tab("Flows", PlaceholderContent("Flows"))
    assert len(mc._tabs) == 2
    assert "Workspace" in mc._tabs
    assert "Flows" in mc._tabs


@pytest.mark.asyncio
async def test_main_content_shows_default_tab() -> None:
    """MainContent should show the default tab (Workspace) on mount."""

    class MainContentTestApp(App):
        def compose(self) -> ComposeResult:
            mc = MainContent()
            mc.register_tab("Workspace", PlaceholderContent("Workspace"))
            mc.register_tab("Flows", PlaceholderContent("Flows"))
            yield mc

    app = MainContentTestApp()
    async with app.run_test(size=(80, 20)) as pilot:
        mc = app.query_one(MainContent)
        assert mc.active_tab == "Workspace"


@pytest.mark.asyncio
async def test_main_content_switches_tab() -> None:
    """MainContent should switch to a different tab when switch_to is called."""

    class MainContentTestApp(App):
        def compose(self) -> ComposeResult:
            mc = MainContent()
            mc.register_tab("Workspace", PlaceholderContent("Workspace"))
            mc.register_tab("Flows", PlaceholderContent("Flows"))
            yield mc

    app = MainContentTestApp()
    async with app.run_test(size=(80, 20)) as pilot:
        mc = app.query_one(MainContent)
        assert mc.active_tab == "Workspace"
        mc.switch_to("Flows")
        await pilot.pause()
        assert mc.active_tab == "Flows"


@pytest.mark.asyncio
async def test_main_content_switch_to_nonexistent_tab() -> None:
    """MainContent should not change active_tab when switching to nonexistent tab."""

    class MainContentTestApp(App):
        def compose(self) -> ComposeResult:
            mc = MainContent()
            mc.register_tab("Workspace", PlaceholderContent("Workspace"))
            yield mc

    app = MainContentTestApp()
    async with app.run_test(size=(80, 20)) as pilot:
        mc = app.query_one(MainContent)
        assert mc.active_tab == "Workspace"
        mc.switch_to("NonExistent")
        await pilot.pause()
        assert mc.active_tab == "Workspace"
