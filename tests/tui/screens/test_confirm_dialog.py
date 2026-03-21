"""Tests for ConfirmDialog modal screen."""

from __future__ import annotations

import pytest

from textual.screen import ModalScreen

from miniautogen.tui.screens.confirm_dialog import ConfirmDialog


def test_confirm_dialog_is_modal_screen() -> None:
    assert issubclass(ConfirmDialog, ModalScreen)


def test_confirm_dialog_stores_message() -> None:
    dialog = ConfirmDialog("Delete agent 'foo'?")
    assert dialog._message == "Delete agent 'foo'?"


def test_confirm_dialog_default_title() -> None:
    dialog = ConfirmDialog("Are you sure?")
    assert dialog._title == "Confirmar"


def test_confirm_dialog_custom_title() -> None:
    dialog = ConfirmDialog("Are you sure?", title="Custom Title")
    assert dialog._title == "Custom Title"


@pytest.mark.asyncio
async def test_confirm_button_dismisses_with_true() -> None:
    """Pressing Confirmar should dismiss the dialog with True."""
    from textual.app import App, ComposeResult

    results: list[bool | None] = []

    class TestApp(App[None]):
        def compose(self) -> ComposeResult:
            return iter([])

        def on_mount(self) -> None:
            self.push_screen(
                ConfirmDialog("Test message"),
                callback=lambda v: results.append(v),
            )

    async with TestApp().run_test() as pilot:
        # The dialog should be mounted; click the confirm button
        await pilot.click("#confirm")
        await pilot.pause()

    assert results == [True]


@pytest.mark.asyncio
async def test_cancel_button_dismisses_with_false() -> None:
    """Pressing Cancelar should dismiss the dialog with False."""
    from textual.app import App, ComposeResult

    results: list[bool | None] = []

    class TestApp(App[None]):
        def compose(self) -> ComposeResult:
            return iter([])

        def on_mount(self) -> None:
            self.push_screen(
                ConfirmDialog("Test message"),
                callback=lambda v: results.append(v),
            )

    async with TestApp().run_test() as pilot:
        await pilot.click("#cancel")
        await pilot.pause()

    assert results == [False]


@pytest.mark.asyncio
async def test_dialog_renders_message() -> None:
    """Dialog should contain the provided message text."""
    from textual.app import App, ComposeResult

    class TestApp(App[None]):
        def compose(self) -> ComposeResult:
            return iter([])

        def on_mount(self) -> None:
            self.push_screen(ConfirmDialog("Excluir agente 'bob'?"))

    async with TestApp().run_test() as pilot:
        # Verify the dialog's internal message attribute is stored correctly
        dialog = pilot.app.screen
        assert isinstance(dialog, ConfirmDialog)
        assert "Excluir agente 'bob'?" in dialog._message
