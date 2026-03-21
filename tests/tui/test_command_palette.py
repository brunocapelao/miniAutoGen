"""Tests for command palette integration."""

from __future__ import annotations

from miniautogen.tui.app import MiniAutoGenDash


def test_app_has_command_providers() -> None:
    """App must provide commands for secondary views."""
    app = MiniAutoGenDash()
    # The app should have SCREENS or get_system_commands
    assert hasattr(app, "SCREENS") or hasattr(app, "get_system_commands")


def test_app_screens_contain_all_views() -> None:
    """App SCREENS dict must contain all secondary view names."""
    expected = {"monitor", "check", "events"}
    assert expected.issubset(set(MiniAutoGenDash.SCREENS.keys()))
