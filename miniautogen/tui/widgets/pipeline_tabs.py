"""PipelineTabs widget -- tab bar for multiple active pipelines.

Shows a horizontal tab bar with status indicators and pipeline names.
Supports switching with click, Tab key, or number keys (1-9).
"""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from miniautogen.tui.status import AgentStatus, StatusVocab


@dataclass
class PipelineTabInfo:
    """Metadata for a single pipeline tab."""

    pipeline_id: str
    name: str
    status: AgentStatus = AgentStatus.PENDING


class PipelineTabs(Widget):
    """Tab bar for switching between active pipelines."""

    DEFAULT_CSS = """
    PipelineTabs {
        dock: top;
        height: 1;
        background: $surface;
    }

    PipelineTabs .tab {
        padding: 0 2;
    }

    PipelineTabs .tab.--active {
        text-style: bold;
        background: $primary-background;
    }
    """

    active_index: reactive[int] = reactive(0)

    class TabChanged(Message):
        """Posted when the active tab changes."""

        def __init__(self, pipeline_id: str, index: int) -> None:
            super().__init__()
            self.pipeline_id = pipeline_id
            self.index = index

    def __init__(self) -> None:
        super().__init__()
        self._tabs: list[PipelineTabInfo] = []

    @property
    def tab_count(self) -> int:
        """Return the number of tabs."""
        return len(self._tabs)

    @property
    def active_tab(self) -> PipelineTabInfo | None:
        """Return the currently active tab info, or None if no tabs."""
        if 0 <= self.active_index < len(self._tabs):
            return self._tabs[self.active_index]
        return None

    def compose(self) -> ComposeResult:
        yield Static("No pipelines", id="tabs-container")

    def add_tab(
        self,
        pipeline_id: str,
        name: str,
        status: AgentStatus = AgentStatus.PENDING,
    ) -> None:
        """Add a pipeline tab."""
        self._tabs.append(PipelineTabInfo(
            pipeline_id=pipeline_id,
            name=name,
            status=status,
        ))
        self._refresh_tabs()
        # Activate the newly added tab
        self.active_index = len(self._tabs) - 1

    def remove_tab(self, pipeline_id: str) -> None:
        """Remove a pipeline tab by ID."""
        self._tabs = [t for t in self._tabs if t.pipeline_id != pipeline_id]
        if self.active_index >= len(self._tabs):
            self.active_index = max(0, len(self._tabs) - 1)
        self._refresh_tabs()

    def update_tab_status(self, pipeline_id: str, status: AgentStatus) -> None:
        """Update the status indicator for a pipeline tab."""
        for tab in self._tabs:
            if tab.pipeline_id == pipeline_id:
                tab.status = status
                break
        self._refresh_tabs()

    def switch_to(self, index: int) -> None:
        """Switch to a tab by index."""
        if 0 <= index < len(self._tabs):
            self.active_index = index
            self.post_message(
                self.TabChanged(
                    pipeline_id=self._tabs[index].pipeline_id,
                    index=index,
                )
            )

    def next_tab(self) -> None:
        """Switch to the next tab (wrapping)."""
        if self._tabs:
            self.switch_to((self.active_index + 1) % len(self._tabs))

    def _refresh_tabs(self) -> None:
        """Re-render the tab bar."""
        try:
            container = self.query_one("#tabs-container", Static)
            if not self._tabs:
                container.update("No pipelines")
                return
            parts: list[str] = []
            for i, tab in enumerate(self._tabs):
                info = StatusVocab.get(tab.status)
                marker = " * " if i == self.active_index else "   "
                parts.append(f"{marker}{info.symbol} {tab.name}")
            container.update("  ".join(parts))
        except Exception:
            pass

    def watch_active_index(self, new_index: int) -> None:
        """React to active index changes."""
        self._refresh_tabs()
