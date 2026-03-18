"""Diff view screen for showing code changes from tool_call results.

Accessible via [d] key from the workspace. Shows syntax-highlighted
diffs using Rich Syntax.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, RichLog, Static


class DiffViewScreen(Screen):
    """Shows code changes/diffs from tool_call results.

    Displays syntax-highlighted content using RichLog.
    """

    BINDINGS = [
        Binding("escape", "pop_screen", "Back", show=True),
        Binding("c", "clear_diff", "Clear", show=True),
    ]

    def __init__(self, diffs: list[dict] | None = None) -> None:
        super().__init__()
        self._diffs = diffs or []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("[bold]Diff View[/bold]", id="diff-title")
        yield RichLog(id="diff-log", highlight=True, markup=True)
        yield Footer()

    def on_mount(self) -> None:
        """Populate with diff data on mount."""
        log = self.query_one("#diff-log", RichLog)

        if not self._diffs:
            log.write("[dim]No diffs to display.[/dim]")
            log.write("[dim]Diffs appear here when tool_call results contain code changes.[/dim]")
            return

        for diff_entry in self._diffs:
            file_path = diff_entry.get("file", "unknown")
            content = diff_entry.get("content", "")
            action = diff_entry.get("action", "modified")

            log.write(f"\n[bold blue]--- {file_path} ({action}) ---[/bold blue]")

            for line in content.split("\n"):
                if line.startswith("+"):
                    log.write(f"[green]{line}[/green]")
                elif line.startswith("-"):
                    log.write(f"[red]{line}[/red]")
                elif line.startswith("@@"):
                    log.write(f"[cyan]{line}[/cyan]")
                else:
                    log.write(line)

    def add_diff(self, file_path: str, content: str, action: str = "modified") -> None:
        """Add a diff entry dynamically."""
        self._diffs.append({
            "file": file_path,
            "content": content,
            "action": action,
        })

    def action_clear_diff(self) -> None:
        """Clear all diffs."""
        self._diffs.clear()
        try:
            log = self.query_one("#diff-log", RichLog)
            log.clear()
            log.write("[dim]Cleared.[/dim]")
        except Exception:
            pass
