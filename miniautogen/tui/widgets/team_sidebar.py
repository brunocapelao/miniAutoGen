"""TeamSidebar widget -- shows the agent roster.

Displays each agent as an AgentCard with live status updates.
Supports responsive collapse (icons-only at narrow widths).
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Static

from miniautogen.tui.status import AgentStatus
from miniautogen.tui.widgets.agent_card import AgentCard


class TeamSidebar(Widget):
    """The left panel showing the agent roster."""

    DEFAULT_CSS = """
    TeamSidebar {
        width: 28;
        dock: left;
        background: $surface;
        border-right: solid $primary-background;
    }

    TeamSidebar .sidebar-title {
        text-style: bold;
        text-align: center;
        padding: 1;
        color: $text;
    }

    TeamSidebar VerticalScroll {
        height: 1fr;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._agents: dict[str, AgentCard] = {}

    @property
    def agent_count(self) -> int:
        """Return the number of agents in the sidebar."""
        return len(self._agents)

    def compose(self) -> ComposeResult:
        yield Static("The Team", classes="sidebar-title")
        yield VerticalScroll(id="agent-list")

    def add_agent(
        self,
        agent_id: str,
        name: str,
        role: str,
        icon: str = "robot",
        status: AgentStatus = AgentStatus.PENDING,
    ) -> None:
        """Add an agent to the sidebar."""
        card = AgentCard(
            agent_id=agent_id,
            name=name,
            role=role,
            icon=icon,
            status=status,
        )
        self._agents[agent_id] = card
        try:
            container = self.query_one("#agent-list", VerticalScroll)
            container.mount(card)
        except Exception:
            pass  # Widget not yet mounted

    def clear_agents(self) -> None:
        """Remove all agents from the sidebar."""
        for card in self._agents.values():
            try:
                card.remove()
            except Exception:
                pass  # Widget not yet mounted
        self._agents.clear()

    def update_agent_status(
        self,
        agent_id: str,
        status: AgentStatus,
    ) -> None:
        """Update an agent's status."""
        card = self._agents.get(agent_id)
        if card is not None:
            card.status = status

    def get_agent_card(self, agent_id: str) -> AgentCard | None:
        """Get an agent's card by ID."""
        return self._agents.get(agent_id)

    def highlight_agent(self, agent_id: str) -> None:
        """Highlight the currently active agent."""
        for aid, card in self._agents.items():
            if aid == agent_id:
                card.add_class("--highlighted")
            else:
                card.remove_class("--highlighted")
