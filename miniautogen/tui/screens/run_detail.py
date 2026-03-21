"""Run detail modal screen."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static


class RunDetailScreen(ModalScreen):
    """Shows full details for a selected pipeline run."""

    DEFAULT_CSS = """
    RunDetailScreen {
        align: center middle;
    }
    RunDetailScreen > Vertical {
        width: 70;
        height: auto;
        max-height: 25;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("q", "dismiss", "Close"),
    ]

    def __init__(
        self,
        run_id: str,
        pipeline: str,
        status: str,
        started: str,
        duration: str,
        events: str,
    ) -> None:
        super().__init__()
        self._run_id = run_id
        self._pipeline = pipeline
        self._status = status
        self._started = started
        self._duration = duration
        self._events = events

    def compose(self) -> ComposeResult:
        status_color = {
            "completed": "green",
            "failed": "red",
            "running": "yellow",
            "cancelled": "dim",
        }.get(self._status.lower(), "white")

        detail_text = (
            f"[bold]Run Detail[/bold]\n\n"
            f"[b]Run ID:[/b]    {self._run_id}\n"
            f"[b]Pipeline:[/b]  {self._pipeline}\n"
            f"[b]Status:[/b]    [{status_color}]{self._status}[/{status_color}]\n"
            f"[b]Started:[/b]   {self._started}\n"
            f"[b]Duration:[/b]  {self._duration}\n"
            f"[b]Events:[/b]    {self._events}\n\n"
            f"[dim]Press [b]Escape[/b] or [b]q[/b] to close[/dim]"
        )
        with Vertical():
            yield Static(detail_text)
