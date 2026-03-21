"""Tests for ConfigContent widget."""

import pytest
from textual.app import App, ComposeResult

from miniautogen.tui.content.config import ConfigContent


def test_config_content_is_widget() -> None:
    """Test that ConfigContent is a valid Textual widget."""
    cc = ConfigContent()
    assert hasattr(cc, "compose")


class ConfigTestApp(App):
    """Test application containing ConfigContent."""

    def compose(self) -> ComposeResult:
        yield ConfigContent()


@pytest.mark.asyncio
async def test_config_renders() -> None:
    """Test that ConfigContent renders without error."""
    app = ConfigTestApp()
    async with app.run_test(size=(120, 40)):
        cc = app.query_one(ConfigContent)
        assert cc is not None


@pytest.mark.asyncio
async def test_config_has_engines_section() -> None:
    """Test that ConfigContent has an engines section."""
    app = ConfigTestApp()
    async with app.run_test(size=(120, 40)):
        cc = app.query_one(ConfigContent)
        engines = cc.query_one("#engines-section")
        assert engines is not None


@pytest.mark.asyncio
async def test_config_has_engines_table() -> None:
    """Test that ConfigContent has an engines DataTable."""
    app = ConfigTestApp()
    async with app.run_test(size=(120, 40)):
        cc = app.query_one(ConfigContent)
        table = cc.query_one("#engines-table")
        assert table is not None


@pytest.mark.asyncio
async def test_config_has_project_section() -> None:
    """Test that ConfigContent has a project section."""
    app = ConfigTestApp()
    async with app.run_test(size=(120, 40)):
        cc = app.query_one(ConfigContent)
        project = cc.query_one("#project-section")
        assert project is not None


@pytest.mark.asyncio
async def test_config_has_server_section() -> None:
    """Test that ConfigContent has a server section."""
    app = ConfigTestApp()
    async with app.run_test(size=(120, 40)):
        cc = app.query_one(ConfigContent)
        # Server section is a Static with "SERVER" label
        server_label = cc.query(".section-title")
        # Find the server label among all section labels
        found_server = False
        for label in server_label:
            content = str(label.render())
            if "SERVER" in content:
                found_server = True
                break
        assert found_server


@pytest.mark.asyncio
async def test_config_has_theme_section() -> None:
    """Test that ConfigContent has a theme section."""
    app = ConfigTestApp()
    async with app.run_test(size=(120, 40)):
        cc = app.query_one(ConfigContent)
        # Theme section is a Static with "THEME" label
        theme_label = cc.query(".section-title")
        # Find the theme label among all section labels
        found_theme = False
        for label in theme_label:
            content = str(label.render())
            if "THEME" in content:
                found_theme = True
                break
        assert found_theme


@pytest.mark.asyncio
async def test_config_bindings_exist() -> None:
    """Test that ConfigContent has the expected key bindings."""
    app = ConfigTestApp()
    async with app.run_test(size=(120, 40)):
        cc = app.query_one(ConfigContent)
        # Check that action methods exist
        assert hasattr(cc, "action_new_engine")
        assert hasattr(cc, "action_edit_engine")
        assert hasattr(cc, "action_delete_engine")
        assert hasattr(cc, "action_refresh")
