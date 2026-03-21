"""Team sidebar widget: Bit Office style AI team status and activity feed.

Replaces ExecutionSidebar and IdlePanel with a unified sidebar that shows
agent cards (idle state) and an activity feed (running state).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static


# ---------------------------------------------------------------------------
# Role emoji mapping
# ---------------------------------------------------------------------------

_ROLE_EMOJIS: dict[str, str] = {
    "architect": "\U0001f3d7\ufe0f",    # construction crane
    "designer": "\U0001f3d7\ufe0f",
    "developer": "\U0001f6e0\ufe0f",    # hammer and wrench
    "coder": "\U0001f6e0\ufe0f",
    "programmer": "\U0001f6e0\ufe0f",
    "tester": "\U0001f9ea",              # test tube
    "qa": "\U0001f9ea",
    "lead": "\U0001f451",               # crown
    "tech lead": "\U0001f451",
    "manager": "\U0001f451",
    "reviewer": "\U0001f451",
}

_DEFAULT_EMOJI = "\U0001f916"  # robot


def _emoji_for_role(role: str) -> str:
    """Return an emoji for a given agent role, falling back to robot."""
    return _ROLE_EMOJIS.get(role.lower().strip(), _DEFAULT_EMOJI)


# ---------------------------------------------------------------------------
# Status dot rendering
# ---------------------------------------------------------------------------

_STATUS_DOTS: dict[str, str] = {
    "ready": "[green]\u25cf[/green]",
    "working": "[yellow]\u25cf[/yellow]",
    "error": "[red]\u25cf[/red]",
    "waiting": "[dim]\u25cf[/dim]",
}


def _status_dot(status: str) -> str:
    """Return Rich markup for a coloured status dot."""
    return _STATUS_DOTS.get(status, _STATUS_DOTS["waiting"])


# ---------------------------------------------------------------------------
# Internal data models
# ---------------------------------------------------------------------------

@dataclass
class AgentCard:
    """Display state for a single agent in the sidebar."""

    name: str
    role: str = ""
    status: str = "ready"
    message: str = ""


@dataclass
class ActivityEntry:
    """A single line in the activity feed."""

    agent_name: str
    message: str


# ---------------------------------------------------------------------------
# Widget
# ---------------------------------------------------------------------------

class TeamSidebar(Widget):
    """Right-docked sidebar showing AI team status in Bit Office style.

    Two visual states:

    * **Idle** -- compact agent cards with status dots.
    * **Running** -- agent cards plus a scrollable activity feed.

    Public API
    ----------
    refresh_agents()
        Reload the agent list from ``self.app._provider.get_agents()``.
    update_agent_status(name, status, message="")
        Update a single agent's status dot and optional message.
    add_activity(agent_name, message)
        Append an entry to the activity feed (auto-shows feed section).
    clear_activity()
        Clear all entries from the activity feed.
    """

    DEFAULT_CSS = """
    TeamSidebar {
        dock: right;
        width: 32;
        height: 1fr;
        background: $surface;
        border-left: tall $primary-background;
    }

    TeamSidebar #ts-header {
        height: 1;
        padding: 0 1;
        background: $primary 15%;
        content-align: center middle;
    }
    TeamSidebar #ts-header-label {
        width: 1fr;
        color: $primary;
        text-style: bold;
        text-align: center;
    }

    TeamSidebar #ts-cards {
        height: auto;
        max-height: 50%;
        padding: 0 1;
    }
    TeamSidebar .agent-row {
        height: 1;
        width: 1fr;
    }

    TeamSidebar #ts-activity-header {
        height: 1;
        padding: 0 1;
        background: $primary 10%;
        content-align: center middle;
    }
    TeamSidebar #ts-activity-label {
        width: 1fr;
        color: $primary;
        text-style: bold;
        text-align: center;
    }

    TeamSidebar #ts-activity-scroll {
        height: 1fr;
        padding: 0 1;
    }
    TeamSidebar .activity-agent {
        height: 1;
        color: $text;
        text-style: bold;
    }
    TeamSidebar .activity-msg {
        height: 1;
        color: $text-muted;
        padding: 0 0 0 2;
    }
    """

    is_running: reactive[bool] = reactive(False)

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._agents: dict[str, AgentCard] = {}
        self._activity: list[ActivityEntry] = []

    # ------------------------------------------------------------------
    # Compose
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        """Build the sidebar layout."""
        # Header
        with Vertical(id="ts-header"):
            yield Static("TEAM", id="ts-header-label")

        # Agent cards section
        yield Vertical(id="ts-cards")

        # Activity feed header + scrollable area
        with Vertical(id="ts-activity-header"):
            yield Static("ACTIVITY", id="ts-activity-label")
        yield VerticalScroll(id="ts-activity-scroll")

    def on_mount(self) -> None:
        """Initialise visibility and load agents from provider."""
        self._update_activity_visibility()
        self.refresh_agents()

    # ------------------------------------------------------------------
    # Reactive watchers
    # ------------------------------------------------------------------

    def watch_is_running(self, value: bool) -> None:
        """Show/hide the activity feed when running state changes."""
        self._update_activity_visibility()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh_agents(self) -> None:
        """Reload agent list from the app's data provider.

        Reads ``self.app._provider.get_agents()`` and rebuilds agent cards.
        Safe to call before the provider is available.
        """
        try:
            provider = getattr(self.app, "_provider", None)
            if provider is None:
                return
            raw_agents: list[dict[str, Any]] = provider.get_agents()
        except Exception:
            return

        self._agents.clear()
        for agent_data in raw_agents:
            name: str = agent_data.get("name", "unknown")
            role: str = agent_data.get("role", agent_data.get("type", ""))
            card = AgentCard(name=name, role=role, status="ready")
            self._agents[name] = card

        self._render_cards()

    def update_agent_status(
        self, name: str, status: str, message: str = ""
    ) -> None:
        """Update a specific agent's status dot and optional message.

        Args:
            name: Agent name (must match an existing card).
            status: One of ``"ready"``, ``"working"``, ``"error"``,
                ``"waiting"``.
            message: Optional short description of current activity.
        """
        card = self._agents.get(name)
        if card is None:
            # Auto-create a card for unknown agents
            card = AgentCard(name=name, status=status, message=message)
            self._agents[name] = card
        else:
            card.status = status
            card.message = message

        self._render_cards()

    def add_activity(self, agent_name: str, message: str) -> None:
        """Append an entry to the activity feed.

        Automatically shows the activity section and sets ``is_running``
        to ``True`` if it is not already.

        Args:
            agent_name: Display name of the agent.
            message: Short description of the activity.
        """
        self._activity.append(ActivityEntry(agent_name=agent_name, message=message))
        if not self.is_running:
            self.is_running = True
        self._render_activity()

    def clear_activity(self) -> None:
        """Clear all entries from the activity feed."""
        self._activity.clear()
        self._render_activity()

    # ------------------------------------------------------------------
    # Internal rendering helpers
    # ------------------------------------------------------------------

    def _update_activity_visibility(self) -> None:
        """Toggle visibility of the activity section."""
        try:
            header = self.query_one("#ts-activity-header")
            scroll = self.query_one("#ts-activity-scroll")
            header.display = self.is_running
            scroll.display = self.is_running
        except Exception:
            pass

    def _render_cards(self) -> None:
        """Re-render all agent cards into the cards container."""
        try:
            container = self.query_one("#ts-cards", Vertical)
        except Exception:
            return

        container.remove_children()

        for card in self._agents.values():
            emoji = _emoji_for_role(card.role)
            dot = _status_dot(card.status)

            # Build the line:  <emoji> <Name>  · <Role>  <dot>
            role_label = card.role.capitalize() if card.role else ""
            # Pad name + role to fill width, then append dot
            name_part = f"{emoji} {card.name}"
            if role_label:
                name_part += f"  [dim]\u00b7 {role_label}[/dim]"

            # Right-align the dot using padding
            available = 28  # 32 - padding/borders
            visible_len = len(card.name) + 2  # emoji space + name
            if role_label:
                visible_len += 4 + len(role_label)  # " · " + role
            pad = max(1, available - visible_len)
            line = f"{name_part}{' ' * pad}{dot}"

            row = Static(line, classes="agent-row")
            container.mount(row)

    def _render_activity(self) -> None:
        """Re-render the activity feed."""
        try:
            scroll = self.query_one("#ts-activity-scroll", VerticalScroll)
        except Exception:
            return

        scroll.remove_children()

        for entry in self._activity:
            agent_label = Static(
                f"\u25b8 {entry.agent_name}", classes="activity-agent"
            )
            msg_label = Static(entry.message, classes="activity-msg")
            scroll.mount(agent_label)
            scroll.mount(msg_label)

        # Auto-scroll to bottom
        scroll.scroll_end(animate=False)
