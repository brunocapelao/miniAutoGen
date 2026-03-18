"""AgentCard widget -- stub for Phase 1 dependency.

This is a minimal stub so Phase 2 widgets can import AgentCard.
The full implementation will be provided by the Phase 1 agent.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from miniautogen.tui.status import AgentStatus, StatusVocab


class AgentCard(Widget):
    """Displays a single agent's info: icon, name, role, status."""

    DEFAULT_CSS = """
    AgentCard {
        height: 3;
        padding: 0 1;
    }

    AgentCard.--highlighted {
        background: $accent;
    }
    """

    status: reactive[AgentStatus] = reactive(AgentStatus.PENDING)

    def __init__(
        self,
        agent_id: str,
        name: str,
        role: str,
        icon: str = "robot",
        status: AgentStatus = AgentStatus.PENDING,
    ) -> None:
        super().__init__()
        self.agent_id = agent_id
        self.agent_name = name
        self.role = role
        self.icon = icon
        self.status = status

    def compose(self) -> ComposeResult:
        info = StatusVocab.get(self.status)
        yield Static(
            f"{info.symbol} {self.agent_name} [{self.role}]",
            id="agent-info",
        )

    def watch_status(self, new_status: AgentStatus) -> None:
        """Update display when status changes."""
        try:
            info = StatusVocab.get(new_status)
            label = self.query_one("#agent-info", Static)
            label.update(f"{info.symbol} {self.agent_name} [{self.role}]")
        except Exception:
            pass
