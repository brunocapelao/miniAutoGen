"""Sidebar idle state: team status + recent runs."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from miniautogen.tui.status import AgentStatus, StatusVocab


class IdlePanel(Widget):
    """Shows team status and recent runs when no flow is executing."""

    DEFAULT_CSS = """
    IdlePanel {
        height: 1fr;
        padding: 1;
    }
    IdlePanel .section-label {
        color: $text-muted;
        text-style: bold;
        margin: 1 0 0 0;
        height: 1;
    }
    IdlePanel .separator {
        height: 1;
        margin: 1 0;
        color: $primary-background;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._agents: list[dict] = []
        self._recent_runs: list[dict] = []

    @property
    def agent_count(self) -> int:
        """Return the number of stored agents."""
        return len(self._agents)

    @property
    def run_count(self) -> int:
        """Return the number of stored runs."""
        return len(self._recent_runs)

    def compose(self) -> ComposeResult:
        """Compose the idle panel with team status and recent runs sections."""
        yield Static("TEAM STATUS", classes="section-label")
        yield Static("", id="team-list")
        yield Static("─" * 20, classes="separator")
        yield Static("RECENT", classes="section-label")
        yield Static("", id="recent-list")

    def set_agents(self, agents: list[dict]) -> None:
        """Update the agents list and refresh display."""
        self._agents = agents
        self._refresh_team()

    def set_recent_runs(self, runs: list[dict]) -> None:
        """Update the recent runs list (max 5) and refresh display."""
        self._recent_runs = runs[:5]
        self._refresh_runs()

    def _refresh_team(self) -> None:
        """Refresh the team status display."""
        try:
            team_list = self.query_one("#team-list", Static)
        except Exception:
            return

        if not self._agents:
            team_list.update("No agents configured.")
            return

        # Map string statuses to AgentStatus enum
        _STATUS_MAP = {
            "idle": AgentStatus.PENDING,
            "working": AgentStatus.WORKING,
            "done": AgentStatus.DONE,
            "active": AgentStatus.ACTIVE,
            "waiting": AgentStatus.WAITING,
            "failed": AgentStatus.FAILED,
            "cancelled": AgentStatus.CANCELLED,
        }

        lines = []
        for agent in self._agents:
            status_str = agent.get("status", "idle")
            agent_status = _STATUS_MAP.get(status_str, AgentStatus.PENDING)
            info = StatusVocab.get(agent_status)
            symbol = info.symbol if info else "\u25cb"
            name = agent.get("name", "unknown")
            padding = " " * max(1, 22 - len(name))
            lines.append(f"{symbol} {name}[dim]{padding}{status_str}[/dim]")

        team_list.update("\n".join(lines))

    def _refresh_runs(self) -> None:
        """Refresh the recent runs display."""
        try:
            runs_list = self.query_one("#recent-list", Static)
        except Exception:
            return

        if not self._recent_runs:
            runs_list.update("No runs yet.")
            return

        lines = []
        for run in self._recent_runs:
            name = run.get("flow_name", "unknown")
            ago = run.get("ago", "")
            if run.get("status") == "done":
                status_color = "[green]"
                status_char = "\u2713"
            else:
                status_color = "[red]"
                status_char = "\u2715"
            padding = " " * max(1, 20 - len(name))
            lines.append(f"{status_color}{status_char}[/] {name}[dim]{padding}{ago}[/dim]")

        runs_list.update("\n".join(lines))
