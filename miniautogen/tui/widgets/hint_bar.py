"""Context-aware hint bar showing available keyboard shortcuts.

Always visible at the bottom of the screen, above the Footer.
Updates based on the current context (workspace, agent detail, etc.).
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

_DEFAULT_HINTS = "[Enter]detail  [/]search  [:]commands  [d]iff  [?]help"

_AGENT_DETAIL_HINTS = "[e]dit  [h]istory  [Esc]close"

_APPROVAL_HINTS = "[A]pprove  [D]eny  [Esc]dismiss"

_PIPELINE_HINTS = "[Tab]next tab  [1-9]switch tab  [Enter]detail  [?]help"

_CONTEXT_MAP: dict[str, str] = {
    "workspace": _DEFAULT_HINTS,
    "agent_detail": _AGENT_DETAIL_HINTS,
    "approval": _APPROVAL_HINTS,
    "pipeline": _PIPELINE_HINTS,
}


class HintBar(Widget):
    """Displays context-sensitive keyboard shortcut hints."""

    DEFAULT_CSS = """
    HintBar {
        dock: bottom;
        height: 1;
        padding: 0 1;
        background: $surface;
        color: $text-muted;
    }
    """

    def __init__(self, context: str = "workspace") -> None:
        super().__init__()
        self._context = context

    @property
    def context(self) -> str:
        """Return the current hint context."""
        return self._context

    def get_hint_text(self) -> str:
        """Get the hint text for the current context."""
        return _CONTEXT_MAP.get(self._context, _DEFAULT_HINTS)

    def compose(self) -> ComposeResult:
        yield Static(self.get_hint_text(), id="hints")

    def set_context(self, context: str) -> None:
        """Update the hint context."""
        self._context = context
        try:
            hints = self.query_one("#hints", Static)
            hints.update(self.get_hint_text())
        except Exception:
            pass
