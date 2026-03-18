"""AgentCard modal screen -- detailed view of a single agent.

Slides in from the right (via Textual's ModalScreen) showing:
- Agent name (large), role, engine, goal
- Tools list, permissions, current status
- [e]dit and [h]istory action stubs
- Esc to close
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static


class AgentCardScreen(ModalScreen[None]):
    """Modal screen showing detailed agent information."""

    DEFAULT_CSS = """
    AgentCardScreen {
        align: right middle;
    }

    AgentCardScreen #agent-card-panel {
        width: 60;
        height: 100%;
        background: $surface;
        border-left: tall $accent;
        padding: 1 2;
    }

    AgentCardScreen .agent-card-title {
        text-style: bold;
        text-align: center;
        margin: 1 0;
    }

    AgentCardScreen .agent-card-section {
        margin: 1 0;
    }

    AgentCardScreen .agent-card-label {
        text-style: bold;
        color: $accent;
    }

    AgentCardScreen .agent-card-value {
        margin: 0 0 0 2;
    }

    AgentCardScreen .agent-card-list-item {
        margin: 0 0 0 4;
        color: $text-muted;
    }

    AgentCardScreen .agent-card-actions {
        margin: 2 0;
        text-align: center;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=True),
        Binding("e", "edit", "Edit", show=True),
        Binding("h", "history", "History", show=True),
    ]

    def __init__(
        self,
        agent_id: str,
        agent_name: str,
        role: str = "",
        engine: str = "",
        goal: str = "",
        tools: list[str] | None = None,
        permissions: list[str] | None = None,
        status: str = "pending",
    ) -> None:
        super().__init__()
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.role = role
        self.engine = engine
        self.goal = goal
        self.tools = tools or []
        self.permissions = permissions or []
        self.status = status

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="agent-card-panel"):
            # Title
            yield Static(
                f"\U0001f916 {self.agent_name}",
                classes="agent-card-title",
            )

            # Basic info
            with Vertical(classes="agent-card-section"):
                yield Static("Role", classes="agent-card-label")
                yield Static(
                    self.role or "[dim]Not specified[/dim]",
                    classes="agent-card-value",
                )

            with Vertical(classes="agent-card-section"):
                yield Static("Engine", classes="agent-card-label")
                yield Static(
                    self.engine or "[dim]Not specified[/dim]",
                    classes="agent-card-value",
                )

            with Vertical(classes="agent-card-section"):
                yield Static("Goal", classes="agent-card-label")
                yield Static(
                    self.goal or "[dim]Not specified[/dim]",
                    classes="agent-card-value",
                )

            with Vertical(classes="agent-card-section"):
                yield Static("Status", classes="agent-card-label")
                yield Static(
                    self.status,
                    classes="agent-card-value",
                )

            # Tools
            with Vertical(classes="agent-card-section"):
                yield Static("Tools", classes="agent-card-label")
                if self.tools:
                    for tool in self.tools:
                        yield Static(
                            f"\u2022 {tool}",
                            classes="agent-card-list-item",
                        )
                else:
                    yield Static(
                        "[dim]No tools[/dim]",
                        classes="agent-card-value",
                    )

            # Permissions
            with Vertical(classes="agent-card-section"):
                yield Static("Permissions", classes="agent-card-label")
                if self.permissions:
                    for perm in self.permissions:
                        yield Static(
                            f"\u2022 {perm}",
                            classes="agent-card-list-item",
                        )
                else:
                    yield Static(
                        "[dim]No permissions[/dim]",
                        classes="agent-card-value",
                    )

            # Action hints
            yield Static(
                "[dim][e]dit  [h]istory  [Esc] close[/dim]",
                classes="agent-card-actions",
            )

    def action_edit(self) -> None:
        """Edit agent configuration (stub)."""
        self.notify("Edit agent: not yet implemented")

    def action_history(self) -> None:
        """View agent history (stub)."""
        self.notify("Agent history: not yet implemented")

    def action_dismiss(self) -> None:
        """Close the modal."""
        self.dismiss(None)
