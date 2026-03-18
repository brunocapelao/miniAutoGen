"""EmptyState widget -- shown when no pipeline is running.

Displays a friendly message with instructions on how to start
a pipeline run.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static


class EmptyState(Widget):
    """Shows a welcome message when no pipeline is active."""

    DEFAULT_CSS = """
    EmptyState {
        content-align: center middle;
        text-align: center;
        height: 1fr;
        color: $text-muted;
    }

    EmptyState #empty-title {
        text-style: bold;
        margin-bottom: 1;
    }

    EmptyState #empty-pipelines {
        margin-top: 1;
        color: $text;
    }

    EmptyState #empty-instructions {
        margin-top: 1;
        color: $text-muted;
    }
    """

    def __init__(
        self,
        pipelines: list[str] | None = None,
    ) -> None:
        super().__init__()
        self._pipelines = pipelines or []

    @property
    def pipelines(self) -> list[str]:
        """Return the list of available pipelines."""
        return list(self._pipelines)

    def compose(self) -> ComposeResult:
        yield Static("Your team is ready.", id="empty-title")
        if self._pipelines:
            listing = "\n".join(f"  \u2022 {p}" for p in self._pipelines)
            yield Static(
                f"Available pipelines:\n{listing}",
                id="empty-pipelines",
            )
        yield Static(
            "[dim]miniautogen run <pipeline>[/dim]",
            id="empty-instructions",
        )

    def get_display_text(self) -> str:
        """Return the full display text (for testing without mount)."""
        parts = ["Your team is ready."]
        if self._pipelines:
            parts.append("Available pipelines:")
            for p in self._pipelines:
                parts.append(f"  \u2022 {p}")
        parts.append("miniautogen run <pipeline>")
        return "\n".join(parts)
