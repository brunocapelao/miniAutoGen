"""Base class for secondary views (`:command` screens).

All secondary views are Textual Screens that can be pushed
onto the screen stack via the command palette.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, Static


class SecondaryView(Screen):
    """Base screen for secondary views like :agents, :pipelines, etc."""

    VIEW_TITLE: str = "View"

    BINDINGS = [
        Binding("escape", "pop_screen", "Back", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(
            f"[bold]{self.VIEW_TITLE}[/bold]",
            id="view-title",
        )
        yield from self.compose_content()
        yield Footer()

    def compose_content(self) -> ComposeResult:
        """Override in subclasses to provide view-specific content."""
        yield Static("[dim]No content[/dim]")
