"""Container that swaps content widgets based on active tab."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget


class MainContent(Widget):
    """Main content area that shows one tab's content at a time.

    This widget manages a collection of content widgets (one per tab) and
    controls their visibility based on the active tab. Only the content
    for the active tab is displayed; others are hidden.
    """

    DEFAULT_CSS = """
    MainContent { width: 1fr; height: 1fr; }
    """

    active_tab: reactive[str] = reactive("Workspace")

    def __init__(self) -> None:
        super().__init__()
        self._tabs: dict[str, Widget] = {}

    def register_tab(self, name: str, content: Widget) -> None:
        """Register a content widget for a named tab.

        Args:
            name: The tab name (e.g., "Workspace", "Flows").
            content: The Widget to display when this tab is active.
        """
        self._tabs[name] = content

    def compose(self) -> ComposeResult:
        """Yield all registered tab content widgets.

        Initially, display state is set based on active_tab.
        """
        for name, widget in self._tabs.items():
            widget.display = name == self.active_tab
            yield widget

    def switch_to(self, tab_name: str) -> None:
        """Switch to the specified tab if it exists.

        Args:
            tab_name: The name of the tab to switch to.
        """
        if tab_name in self._tabs:
            self.active_tab = tab_name

    def watch_active_tab(self, old_value: str, new_value: str) -> None:
        """React to changes in active_tab by updating widget visibility.

        This is called automatically when active_tab changes via reactive.

        Args:
            old_value: The previous active tab name.
            new_value: The new active tab name.
        """
        for name, widget in self._tabs.items():
            is_active = name == new_value
            widget.display = is_active
            if is_active and hasattr(widget, "_refresh_table"):
                widget._refresh_table()
