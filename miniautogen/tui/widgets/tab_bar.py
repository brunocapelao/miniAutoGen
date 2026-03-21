"""Tab bar navigation widget for MiniAutoGen Dash."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.events import Click
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from miniautogen.tui.messages import TabChanged

_TABS = ["Workspace", "Flows", "Agents", "Config"]


class _ClickableTab(Static):
    """A Static widget that handles click events to switch tabs."""

    def __init__(self, label: str, tab_name: str, **kwargs) -> None:
        super().__init__(label, **kwargs)
        self._tab_name = tab_name

    def on_click(self, event: Click) -> None:
        """Handle click on this tab."""
        event.stop()
        tab_bar = self.ancestors_with_self[-1]
        for ancestor in self.ancestors_with_self:
            if isinstance(ancestor, TabBar):
                ancestor.active_tab = self._tab_name
                break


class TabBar(Widget):
    """Horizontal tab bar with brand, 4 tabs, and status indicator.

    Number key bindings (1-4) live on the App, not here,
    because DataTables in content widgets steal focus.
    """

    DEFAULT_CSS = """
    TabBar {
        dock: top;
        height: 3;
        background: $surface;
        layout: horizontal;
        padding: 0 1;
    }
    TabBar #tab-brand {
        width: auto;
        padding: 1 2 1 1;
        color: $primary;
        text-style: bold;
    }
    TabBar #tab-nav {
        width: 1fr;
        height: 3;
        layout: horizontal;
    }
    TabBar .tab {
        width: auto;
        padding: 1 2;
        height: 3;
        color: $text-muted;
    }
    TabBar .tab.--active {
        color: $primary;
        text-style: bold;
        padding: 1 2 0 2;
        border-bottom: tall $primary;
    }
    TabBar .tab:hover {
        color: $text;
        background: $primary 10%;
    }
    TabBar #tab-status {
        width: auto;
        padding: 1 1 1 2;
        color: $text-muted;
    }
    """

    active_tab: reactive[str] = reactive("Workspace")

    def __init__(self) -> None:
        super().__init__()
        self._server_status = ""

    @property
    def tab_names(self) -> list[str]:
        return list(_TABS)

    def compose(self) -> ComposeResult:
        yield Static("MiniAutoGen", id="tab-brand")
        with Horizontal(id="tab-nav"):
            for name in _TABS:
                classes = "tab --active" if name == self.active_tab else "tab"
                yield _ClickableTab(
                    name, tab_name=name, classes=classes, id=f"tab-{name.lower()}"
                )
        yield Static("", id="tab-status")

    def watch_active_tab(self, old_value: str, new_value: str) -> None:
        if not self.is_mounted:
            return
        for name in _TABS:
            try:
                tab = self.query_one(f"#tab-{name.lower()}")
                tab.set_classes("tab --active" if name == new_value else "tab")
            except Exception:
                pass
        self.post_message(TabChanged(tab_name=new_value))

    def action_switch_tab(self, tab_name: str) -> None:
        if tab_name in _TABS:
            self.active_tab = tab_name

    def update_server_status(self, status_text: str) -> None:
        """Update the server status indicator on the right."""
        self._server_status = status_text
        try:
            self.query_one("#tab-status", Static).update(status_text)
        except Exception:
            pass
