"""Tests for InitWizardScreen."""

from __future__ import annotations

from textual.screen import ModalScreen

from miniautogen.tui.screens.init_wizard import InitWizardScreen


def test_init_wizard_is_modal_screen() -> None:
    assert issubclass(InitWizardScreen, ModalScreen)


def test_init_wizard_creates_instance() -> None:
    wizard = InitWizardScreen()
    assert wizard is not None
