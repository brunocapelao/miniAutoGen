"""Help screen showing available keyboard shortcuts."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static


_HELP_TEXT = """\
[bold]MiniAutoGen Dash -- Keyboard Shortcuts[/bold]

[bold underline]Global[/bold underline]
  [b]?[/b]         Show this help screen
  [b]:[/b]         Open command palette
  [b]q[/b]         Quit
  [b]f[/b]         Toggle fullscreen (hide/show sidebar)
  [b]t[/b]         Toggle team sidebar
  [b]Escape[/b]    Go back / close screen

[bold underline]Views[/bold underline]
  [b]n[/b]         New item
  [b]e[/b]         Edit selected item
  [b]d[/b]         Delete selected item
  [b]r[/b]         Refresh current view
  [b]Enter[/b]     Show detail / open

[bold underline]Pipelines / Flows[/bold underline]
  [b]x[/b]         Run selected pipeline
  [b]c[/b]         Cancel running pipeline
  [b]Tab[/b]       Next tab

[bold underline]Server[/bold underline]
  [b]Ctrl+S[/b]    Start gateway server
  [b]Ctrl+X[/b]    Stop gateway server

[dim]Press [b]Escape[/b] or [b]?[/b] to close[/dim]
"""


class HelpScreen(ModalScreen):
    """Shows keyboard shortcuts and navigation help."""

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }
    HelpScreen > Vertical {
        width: 70;
        height: auto;
        max-height: 35;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("question_mark", "dismiss", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(_HELP_TEXT)
