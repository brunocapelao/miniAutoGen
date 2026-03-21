"""Confirmation dialog for destructive actions."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class ConfirmDialog(ModalScreen[bool]):
    """Modal asking user to confirm a destructive action."""

    DEFAULT_CSS = """
    ConfirmDialog {
        align: center middle;
    }
    ConfirmDialog > Vertical {
        width: 60;
        height: auto;
        max-height: 15;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    ConfirmDialog > Vertical > Horizontal {
        height: auto;
        align: right middle;
        margin-top: 1;
    }
    ConfirmDialog Button {
        margin-left: 1;
    }
    """

    def __init__(self, message: str, title: str = "Confirmar") -> None:
        super().__init__()
        self._message = message
        self._title = title

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(f"[bold]{self._title}[/bold]\n\n{self._message}")
            with Horizontal():
                yield Button("Cancelar", variant="default", id="cancel")
                yield Button("Confirmar", variant="error", id="confirm")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm")
