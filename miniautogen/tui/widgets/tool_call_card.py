"""ToolCallCard widget -- inline card showing tool invocations.

Displays tool name, action description, and execution status
with a sidebar indicator (▌).

Statuses: executing, done, failed.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

# Status display mapping
_STATUS_DISPLAY: dict[str, tuple[str, str]] = {
    "executing": ("\u25d0", "yellow"),       # ◐ yellow
    "done": ("\u2713", "dim green"),          # ✓ green
    "failed": ("\u2715", "red"),              # ✕ red
}


class ToolCallCard(Widget):
    """Inline card showing a tool invocation in the interaction log.

    Shows: sidebar indicator ▌, tool name, action, status.
    """

    DEFAULT_CSS = """
    ToolCallCard {
        height: auto;
        margin: 0 0 0 2;
        padding: 0 1;
    }

    ToolCallCard .tool-indicator {
        width: 1;
        color: $accent;
    }

    ToolCallCard .tool-content {
        margin: 0 0 0 1;
    }
    """

    status: reactive[str] = reactive("executing")

    def __init__(
        self,
        tool_name: str,
        action: str,
        status: str = "executing",
        result_summary: str | None = None,
        elapsed: float | None = None,
    ) -> None:
        super().__init__()
        self.tool_name = tool_name
        self.action = action
        self.result_summary = result_summary
        self.elapsed = elapsed
        self.status = status

    def _render_content(self) -> str:
        """Build the display string for this tool call."""
        symbol, color = _STATUS_DISPLAY.get(
            self.status, ("\u25d0", "yellow")
        )
        elapsed_str = f" {self.elapsed:.1f}s" if self.elapsed else ""
        summary_str = f" {self.result_summary}" if self.result_summary else ""
        return (
            f"\u258c \U0001f527 {self.tool_name}  "
            f"[{color}]{symbol} {self.status}[/{color}]"
            f"{elapsed_str}{summary_str}"
        )

    def compose(self) -> ComposeResult:
        yield Static(self._render_content(), id="tool-content")

    def watch_status(self, new_status: str) -> None:
        """Update display when status changes."""
        try:
            content = self.query_one("#tool-content", Static)
            content.update(self._render_content())
        except Exception:
            pass  # Widget not yet mounted
