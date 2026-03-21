"""Workspace tab: project overview, health check, quick actions."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Button, Static


class StatCard(Widget):
    """Single stat display card."""

    DEFAULT_CSS = """
    StatCard {
        background: $surface;
        border: round $primary-background;
        padding: 1 2;
        margin: 0 1 0 0;
        width: 1fr;
        height: auto;
        min-height: 7;
    }
    StatCard .stat-label {
        color: $text-muted;
        height: 1;
    }
    StatCard .stat-value {
        text-style: bold;
        color: $primary;
        height: 1;
    }
    StatCard .stat-sub {
        color: $text-muted;
        height: 1;
    }
    """

    def __init__(self, label: str, value: str = "0", sub: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._label = label
        self._value = value
        self._sub = sub

    def compose(self) -> ComposeResult:
        yield Static(self._label, classes="stat-label")
        yield Static(self._value, classes="stat-value", id=f"val-{self.id or self._label.lower()}")
        yield Static(self._sub, classes="stat-sub", id=f"sub-{self.id or self._label.lower()}")

    def update_stat(self, value: str, sub: str = "") -> None:
        try:
            self.query_one(f"#val-{self.id or self._label.lower()}", Static).update(value)
            if sub:
                self.query_one(f"#sub-{self.id or self._label.lower()}", Static).update(sub)
        except Exception:
            pass


class WorkspaceContent(Widget):
    """Home tab showing project overview and health status."""

    DEFAULT_CSS = """
    WorkspaceContent {
        height: 1fr;
        padding: 1 2;
    }
    WorkspaceContent .section-title {
        color: $text-muted;
        text-style: bold;
        margin: 1 0 0 0;
        height: 1;
    }
    WorkspaceContent #stat-row {
        layout: horizontal;
        height: auto;
        margin: 0 0 1 0;
    }
    WorkspaceContent #health-box {
        background: $surface;
        border: round $primary-background;
        padding: 1 2;
        margin: 0 0 1 0;
        height: auto;
    }
    WorkspaceContent #action-row {
        layout: horizontal;
        height: auto;
        margin: 1 0 0 0;
    }
    WorkspaceContent #action-row Button {
        margin: 0 1 0 0;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("PROJECT OVERVIEW", classes="section-title")
        with Horizontal(id="stat-row"):
            yield StatCard("Agents", "0", "—", id="card-agents")
            yield StatCard("Flows", "0", "—", id="card-flows")
            yield StatCard("Engines", "0", "—", id="card-engines")
            yield StatCard("Last Run", "—", "", id="card-lastrun")

        yield Static("HEALTH CHECK", classes="section-title")
        yield Static("Running checks...", id="health-box")

        yield Static("QUICK ACTIONS", classes="section-title")
        with Horizontal(id="action-row"):
            yield Button("[n] New Agent", id="btn-new-agent", variant="primary")
            yield Button("[r] Run Flow", id="btn-run-flow", variant="primary")
            yield Button("[:] Commands", id="btn-commands", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle quick action button clicks."""
        if event.button.id == "btn-new-agent":
            self.app.action_switch_tab("Agents")
            try:
                agents = self.app.query_one(
                    "AgentsContent",
                )
                agents.action_new_agent()
            except Exception:
                pass
        elif event.button.id == "btn-run-flow":
            self.app.action_switch_tab("Flows")
            try:
                flows = self.app.query_one(
                    "FlowsContent",
                )
                flows.action_run_flow()
            except Exception:
                pass
        elif event.button.id == "btn-commands":
            self.app.action_command_palette()

    def refresh_data(
        self,
        agents_count: int = 0,
        flows_count: int = 0,
        engines_count: int = 0,
        last_run_status: str = "—",
        health_items: list[tuple[str, str]] | None = None,
    ) -> None:
        """Update the workspace with fresh data."""
        try:
            self.query_one("#card-agents", StatCard).update_stat(
                str(agents_count), "all ready" if agents_count > 0 else "—"
            )
            self.query_one("#card-flows", StatCard).update_stat(str(flows_count))
            self.query_one("#card-engines", StatCard).update_stat(str(engines_count))
            self.query_one("#card-lastrun", StatCard).update_stat(last_run_status)
        except Exception:
            pass

        if health_items:
            lines = [f"{symbol} {text}" for symbol, text in health_items]
            try:
                self.query_one("#health-box", Static).update("\n".join(lines))
            except Exception:
                pass
