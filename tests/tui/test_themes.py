"""Tests for the theme system."""

from __future__ import annotations

from miniautogen.tui.themes import THEMES, get_theme


def test_four_themes_available() -> None:
    assert len(THEMES) == 4


def test_default_theme_is_tokyo_night() -> None:
    theme = get_theme("tokyo-night")
    assert theme is not None
    assert theme.name == "tokyo-night"


def test_all_themes_have_name() -> None:
    for name, theme in THEMES.items():
        assert theme.name == name


def test_get_nonexistent_theme_returns_default() -> None:
    theme = get_theme("nonexistent")
    assert theme.name == "tokyo-night"


def test_theme_names() -> None:
    expected = {"tokyo-night", "catppuccin", "monokai", "light"}
    assert set(THEMES.keys()) == expected


def test_all_themes_have_semantic_status_colors() -> None:
    for name, theme in THEMES.items():
        assert theme.status_active, f"{name} missing status_active"
        assert theme.status_done, f"{name} missing status_done"
        assert theme.status_working, f"{name} missing status_working"
        assert theme.status_waiting, f"{name} missing status_waiting"
        assert theme.status_failed, f"{name} missing status_failed"
        assert theme.status_cancelled, f"{name} missing status_cancelled"


def test_all_themes_have_surface_colors() -> None:
    for name, theme in THEMES.items():
        assert theme.background, f"{name} missing background"
        assert theme.surface, f"{name} missing surface"
        assert theme.primary, f"{name} missing primary"
        assert theme.text, f"{name} missing text"
        assert theme.text_muted, f"{name} missing text_muted"
