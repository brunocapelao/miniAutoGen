"""StepBlock widget -- represents one pipeline step in the interaction log.

Three visual states:
- **pending** (one line): ``○ Step 3: Review -- Reviewer``
- **expanded** (active): Full content with agent messages visible
- **collapsed** (done): ``✓ Step 1: Planning -- Planner  [3 messages]``

Supports:
- Agent icon + name for each message
- Collapsible with Enter key
- Auto-collapse when status transitions to DONE
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from miniautogen.tui.status import AgentStatus, StatusVocab


class StepBlock(Widget):
    """A single pipeline step in the interaction log."""

    DEFAULT_CSS = """
    StepBlock {
        height: auto;
        margin: 0 0 1 0;
        padding: 0 1;
    }

    StepBlock .step-header {
        text-style: bold;
    }

    StepBlock .step-messages {
        margin: 0 0 0 2;
    }

    StepBlock .step-message {
        margin: 0 0 0 1;
    }
    """

    status: reactive[AgentStatus] = reactive(AgentStatus.PENDING)
    collapsed: reactive[bool] = reactive(False)

    def __init__(
        self,
        step_number: int,
        step_label: str,
        agent_name: str | None = None,
        agent_icon: str | None = None,
        status: AgentStatus = AgentStatus.PENDING,
    ) -> None:
        super().__init__()
        self.step_number = step_number
        self.step_label = step_label
        self.agent_name = agent_name or ""
        self.agent_icon = agent_icon or ""
        self._messages: list[tuple[str, str]] = []  # (agent_name, content)
        self.status = status

    @property
    def message_count(self) -> int:
        """Number of messages in this step."""
        return len(self._messages)

    def add_message(self, agent_name: str, content: str) -> None:
        """Add a message to this step block."""
        self._messages.append((agent_name, content))

    def _render_header(self) -> str:
        """Build the header line for this step."""
        info = StatusVocab.get(self.status)
        agent_str = f" -- {self.agent_name}" if self.agent_name else ""
        icon_str = f"{self.agent_icon} " if self.agent_icon else ""
        count_str = (
            f"  [{len(self._messages)} messages]"
            if self.collapsed and self._messages
            else ""
        )
        return (
            f"[{info.color}]{info.symbol}[/{info.color}] "
            f"{icon_str}Step {self.step_number}: "
            f"{self.step_label}{agent_str}{count_str}"
        )

    def compose(self) -> ComposeResult:
        yield Static(self._render_header(), classes="step-header", id="header")

    def watch_status(self, new_status: AgentStatus) -> None:
        """Update display when status changes. Auto-collapse on DONE."""
        if new_status == AgentStatus.DONE:
            self.collapsed = True
        self._refresh_header()

    def watch_collapsed(self, is_collapsed: bool) -> None:
        """Update display when collapsed state changes."""
        self._refresh_header()

    def _refresh_header(self) -> None:
        """Refresh the header Static widget."""
        try:
            header = self.query_one("#header", Static)
            header.update(self._render_header())
        except Exception:
            pass  # Widget not yet mounted

    def key_enter(self) -> None:
        """Toggle collapsed state on Enter."""
        self.collapsed = not self.collapsed
