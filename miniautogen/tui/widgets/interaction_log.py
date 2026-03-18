"""InteractionLog widget -- the conversation-style work panel.

This is the killer feature of MiniAutoGen Dash. It displays pipeline
execution as a chat-like conversation with:
- Agent messages with icon + name
- Syntax-highlighted code blocks (via Rich)
- Inline tool call cards
- Collapsible steps
- Streaming indicators (░░░ thinking..., cursor ▊)
- Auto-scroll with manual override

Uses RichLog internally to handle large volumes efficiently.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import RichLog

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.types import EventType
from miniautogen.tui.event_mapper import EventMapper
from miniautogen.tui.status import AgentStatus, StatusVocab

# Map of event types that represent agent messages
_MESSAGE_EVENTS: set[str] = {
    EventType.AGENT_REPLIED.value,
    EventType.BACKEND_MESSAGE_COMPLETED.value,
}

_TOOL_EVENTS: set[str] = {
    EventType.TOOL_INVOKED.value,
    EventType.TOOL_SUCCEEDED.value,
    EventType.TOOL_FAILED.value,
    EventType.BACKEND_TOOL_CALL_REQUESTED.value,
    EventType.BACKEND_TOOL_CALL_EXECUTED.value,
}

_STEP_START_EVENTS: set[str] = {
    EventType.COMPONENT_STARTED.value,
    EventType.DELIBERATION_STARTED.value,
    EventType.AGENTIC_LOOP_STARTED.value,
}

_STREAMING_EVENTS: set[str] = {
    EventType.BACKEND_MESSAGE_DELTA.value,
    EventType.BACKEND_TURN_STARTED.value,
}


class InteractionLog(Widget):
    """The main conversation log panel.

    Receives events and renders them as a chat-thread conversation.
    Supports auto-scroll that pauses when user scrolls up.
    """

    DEFAULT_CSS = """
    InteractionLog {
        height: 1fr;
    }

    InteractionLog RichLog {
        height: 1fr;
        scrollbar-size: 1 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._entry_count = 0
        self._auto_scroll = True

    @property
    def entry_count(self) -> int:
        return self._entry_count

    def compose(self) -> ComposeResult:
        yield RichLog(
            highlight=True,
            markup=True,
            wrap=True,
            auto_scroll=True,
            id="log",
        )

    def _get_log(self) -> RichLog:
        """Get the underlying RichLog widget."""
        return self.query_one("#log", RichLog)

    def add_agent_message(
        self,
        agent_id: str,
        agent_name: str,
        content: str,
    ) -> None:
        """Add an agent message entry to the log."""
        try:
            log = self._get_log()
            log.write(f"[bold]{agent_name}[/bold]")
            log.write(content)
            log.write("")  # blank line separator
        except Exception:
            pass  # Widget not yet mounted
        self._entry_count += 1

    def add_tool_call(
        self,
        agent_id: str,
        tool_name: str,
        status: str,
        result_summary: str | None = None,
        elapsed: float | None = None,
    ) -> None:
        """Add a tool call card to the log."""
        status_indicator = "\u25d0" if status == "executing" else "\u2713"
        elapsed_str = f" {elapsed:.1f}s" if elapsed else ""
        summary = f" {result_summary}" if result_summary else ""

        try:
            log = self._get_log()
            log.write(
                f"  \u258c \U0001f527 {tool_name}  "
                f"{status_indicator} {status}{elapsed_str}{summary}"
            )
        except Exception:
            pass
        self._entry_count += 1

    def add_step_header(
        self,
        step_number: int,
        step_label: str,
        agent_name: str | None = None,
    ) -> None:
        """Add a step header to the log."""
        agent_str = f" ({agent_name})" if agent_name else ""
        try:
            log = self._get_log()
            log.write("")
            log.write(
                f"[bold]\u2500\u2500\u2500 Step {step_number}: "
                f"{step_label}{agent_str} \u2500\u2500\u2500[/bold]"
            )
            log.write("")
        except Exception:
            pass
        self._entry_count += 1

    def add_streaming_indicator(
        self,
        agent_id: str,
        state: str = "thinking",
    ) -> None:
        """Add a streaming state indicator (░░░ thinking..., cursor ▊)."""
        if state == "thinking":
            indicator = "\u2591\u2591\u2591 thinking..."
        elif state == "generating":
            indicator = "\u258a"
        else:
            indicator = f"\u25d0 {state}..."

        try:
            log = self._get_log()
            log.write(f"  [dim]{indicator}[/dim]")
        except Exception:
            pass
        self._entry_count += 1

    def handle_event(self, event: ExecutionEvent) -> None:
        """Process an ExecutionEvent and add appropriate log entries.

        Groups events by step/component and dispatches to the
        appropriate rendering method.
        """
        etype = event.type
        payload = event.payload
        agent_id = payload.get("agent_id", "system")
        agent_name = payload.get("agent_name", agent_id)

        if etype in _STEP_START_EVENTS:
            step_num = payload.get("step_number", 0)
            step_label = payload.get(
                "component_name", payload.get("label", "")
            )
            self.add_step_header(step_num, step_label, agent_name)

        elif etype in _MESSAGE_EVENTS:
            content = payload.get("content", payload.get("message", ""))
            self.add_agent_message(agent_id, agent_name, content)

        elif etype in _TOOL_EVENTS:
            tool_name = payload.get(
                "tool_name", payload.get("name", "unknown")
            )
            if etype in {
                EventType.TOOL_INVOKED.value,
                EventType.BACKEND_TOOL_CALL_REQUESTED.value,
            }:
                self.add_tool_call(agent_id, tool_name, "executing")
            elif etype == EventType.TOOL_SUCCEEDED.value:
                summary = payload.get("summary", "")
                self.add_tool_call(
                    agent_id, tool_name, "done", result_summary=summary
                )
            elif etype == EventType.TOOL_FAILED.value:
                error = payload.get("error", "failed")
                self.add_tool_call(
                    agent_id, tool_name, "failed", result_summary=error
                )
            elif etype == EventType.BACKEND_TOOL_CALL_EXECUTED.value:
                self.add_tool_call(agent_id, tool_name, "done")

        elif etype in _STREAMING_EVENTS:
            if etype == EventType.BACKEND_MESSAGE_DELTA.value:
                self.add_streaming_indicator(agent_id, "generating")
            else:
                self.add_streaming_indicator(agent_id, "thinking")
