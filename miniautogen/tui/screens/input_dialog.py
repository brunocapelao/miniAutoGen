"""Input dialog for collecting optional text before pipeline execution."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static


class InputDialog(ModalScreen[str | None]):
    """Modal prompting the user for optional text input.

    Dismisses with the entered string (or None if empty / cancelled).
    """

    DEFAULT_CSS = """
    InputDialog {
        align: center middle;
    }
    InputDialog > Vertical {
        width: 70;
        height: auto;
        max-height: 15;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    InputDialog > Vertical > Input {
        margin-top: 1;
    }
    InputDialog > Vertical > Horizontal {
        height: auto;
        align: right middle;
        margin-top: 1;
    }
    InputDialog Button {
        margin-left: 1;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, title: str, placeholder: str = "") -> None:
        super().__init__()
        self._title = title
        self._placeholder = placeholder

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(f"[bold]{self._title}[/bold]")
            yield Input(placeholder=self._placeholder, id="dialog-input")
            with Horizontal():
                yield Button("Cancel", variant="default", id="cancel")
                yield Button("OK", variant="primary", id="ok")

    def on_mount(self) -> None:
        """Focus the input field on open."""
        self.query_one("#dialog-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok":
            value = self.query_one("#dialog-input", Input).value
            self.dismiss(value if value else None)
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Allow pressing Enter in the input to confirm."""
        value = event.value
        self.dismiss(value if value else None)

    def action_cancel(self) -> None:
        """Escape key cancels and dismisses with None."""
        self.dismiss(None)
