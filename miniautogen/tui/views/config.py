"""`:config` view -- project configuration display."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Static

from miniautogen.tui.views.base import SecondaryView


class ConfigView(SecondaryView):
    VIEW_TITLE = "Config"

    BINDINGS = [
        Binding("escape", "pop_screen", "Back", show=True),
        Binding("r", "refresh_config", "Refresh", show=True),
    ]

    def compose_content(self) -> ComposeResult:
        yield Static(id="config-display")

    def on_mount(self) -> None:
        """Display project configuration on mount."""
        self._refresh_display()

    def _refresh_display(self) -> None:
        """Refresh the config display."""
        display = self.query_one("#config-display", Static)
        if self.provider is None:
            display.update("[dim]No project configuration found.[/dim]")
            return

        config = self.provider.get_config()
        if not config:
            display.update("[dim]Could not load project configuration.[/dim]")
            return

        lines = [
            "[bold]Project Configuration[/bold]",
            "",
            f"  [b]Name:[/b]           {config.get('project_name', '?')}",
            f"  [b]Version:[/b]        {config.get('version', '?')}",
            f"  [b]Default Engine:[/b] {config.get('default_engine', '?')}",
            f"  [b]Default Memory:[/b] {config.get('default_memory', '?')}",
            "",
            "[bold]Resource Counts[/bold]",
            "",
            f"  [b]Engines:[/b]   {config.get('engine_count', 0)}",
            f"  [b]Agents:[/b]    {config.get('agent_count', 0)}",
            f"  [b]Pipelines:[/b] {config.get('pipeline_count', 0)}",
            "",
            "[bold]Database[/bold]",
            "",
            f"  [b]URL:[/b] {config.get('database', '(none)')}",
        ]
        display.update("\n".join(lines))

    def action_refresh_config(self) -> None:
        """Refresh config display."""
        self._refresh_display()
        self.notify("Refreshed")
