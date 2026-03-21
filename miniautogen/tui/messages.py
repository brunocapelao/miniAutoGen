"""Textual messages for TUI event handling.

These messages bridge ExecutionEvents from the core event system
into Textual's message loop, enabling reactive UI updates.
"""

from __future__ import annotations

from textual.message import Message

from miniautogen.core.contracts.events import ExecutionEvent


class SidebarRefresh(Message):
    """Posted when the agent roster changes (create/delete) to trigger sidebar refresh."""
    pass


class RunCompleted(Message):
    """Posted when a pipeline run completes (success or failure)."""

    def __init__(self, pipeline_name: str, status: str) -> None:
        super().__init__()
        self.pipeline_name = pipeline_name
        self.status = status


class TabChanged(Message):
    """Posted when user switches tabs."""

    def __init__(self, tab_name: str) -> None:
        super().__init__()
        self.tab_name = tab_name


class RunStarted(Message):
    """Posted when a flow execution begins."""

    def __init__(self, flow_name: str, run_id: str) -> None:
        super().__init__()
        self.flow_name = flow_name
        self.run_id = run_id


class RunStopped(Message):
    """Posted when a flow execution ends (any reason)."""

    def __init__(self, run_id: str, final_status: str) -> None:
        super().__init__()
        self.run_id = run_id
        self.final_status = final_status


class TuiEvent(Message):
    """Wraps a core ExecutionEvent as a Textual Message.

    Posted by the EventBridgeWorker into the Textual message loop.
    Widgets subscribe to this message to update their display.
    """

    def __init__(self, event: ExecutionEvent) -> None:
        super().__init__()
        self.event = event
