"""AgentCard widget -- stub for Phase 1 dependency.

This is a minimal stub so Phase 2 widgets can import AgentCard.
The full implementation will be provided by the Phase 1 agent.
"""

from __future__ import annotations

import logging

from textual.app import ComposeResult
from textual.events import Key
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from miniautogen.tui.status import AgentStatus, StatusVocab

logger = logging.getLogger(__name__)


class AgentCard(Widget):
    """Displays a single agent's info: icon, name, role, status."""

    DEFAULT_CSS = """
    AgentCard {
        height: 3;
        padding: 0 1;
    }

    AgentCard:focus {
        border: tall $accent;
    }

    AgentCard.--highlighted {
        background: $accent;
    }
    """

    can_focus = True

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

    def on_key(self, event: Key) -> None:
        """Open AgentCardScreen detail modal when Enter is pressed."""
        if event.key == "enter":
            event.stop()
            self._open_detail_screen()

    def on_click(self) -> None:
        """Open AgentCardScreen detail modal on click."""
        self._open_detail_screen()

    def _open_detail_screen(self) -> None:
        """Push AgentCardScreen for this agent."""
        try:
            from miniautogen.tui.screens.agent_card import AgentCardScreen

            provider = getattr(self.app, "_provider", None)
            engine = ""
            goal = ""
            tools: list[str] = []
            permissions: list[str] = []

            if provider is not None:
                try:
                    data = provider.get_agent(self.agent_name)
                    engine = data.get("engine_profile", "")
                    goal = data.get("goal", "")
                    tools = data.get("tools", []) or []
                    permissions = data.get("permissions", []) or []
                except Exception:
                    logger.exception(
                        "Failed to load agent details for %s", self.agent_name
                    )

            self.app.push_screen(
                AgentCardScreen(
                    agent_id=self.agent_id,
                    agent_name=self.agent_name,
                    role=self.role,
                    engine=engine,
                    goal=goal,
                    tools=tools,
                    permissions=permissions,
                    status=self.status.value,
                )
            )
        except Exception:
            logger.exception("Failed to open AgentCardScreen for %s", self.agent_id)

    def watch_status(self, new_status: AgentStatus) -> None:
        """Update display when status changes."""
        try:
            info = StatusVocab.get(new_status)
            label = self.query_one("#agent-info", Static)
            label.update(f"{info.symbol} {self.agent_name} [{self.role}]")
        except Exception:
            pass
