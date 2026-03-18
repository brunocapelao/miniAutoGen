"""Tests for the MiniAutoGen Dash app shell."""

from __future__ import annotations

import pytest

from textual.app import App

from miniautogen.tui.app import MiniAutoGenDash


def test_app_is_textual_app() -> None:
    assert issubclass(MiniAutoGenDash, App)


def test_app_has_title() -> None:
    app = MiniAutoGenDash()
    assert app.TITLE == "MiniAutoGen Dash"


def test_app_has_subtitle() -> None:
    app = MiniAutoGenDash()
    assert "team" in app.SUB_TITLE.lower() or "agent" in app.SUB_TITLE.lower()


def test_app_has_key_bindings() -> None:
    app = MiniAutoGenDash()
    binding_keys = {b.key for b in app.BINDINGS}
    # Core navigation keys from the design spec
    assert "question_mark" in binding_keys or "?" in binding_keys
    assert "escape" in binding_keys
    assert "f" in binding_keys
    assert "t" in binding_keys


def test_app_has_css() -> None:
    """App must define CSS (inline or file)."""
    app = MiniAutoGenDash()
    assert app.CSS or app.CSS_PATH


@pytest.mark.asyncio
async def test_app_mounts_without_error() -> None:
    """Smoke test: the app mounts and can be started in headless mode."""
    app = MiniAutoGenDash()
    async with app.run_test(size=(120, 40)) as pilot:
        assert app.is_running
        await pilot.press("q")
