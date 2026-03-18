"""Tests for the PipelineTabs widget."""

from __future__ import annotations

from textual.widget import Widget

from miniautogen.tui.status import AgentStatus
from miniautogen.tui.widgets.pipeline_tabs import PipelineTabs


def test_pipeline_tabs_is_widget() -> None:
    assert issubclass(PipelineTabs, Widget)


def test_pipeline_tabs_starts_empty() -> None:
    tabs = PipelineTabs()
    assert tabs.tab_count == 0
    assert tabs.active_tab is None


def test_pipeline_tabs_add_tab() -> None:
    tabs = PipelineTabs()
    tabs.add_tab(pipeline_id="p1", name="Pipeline 1")
    assert tabs.tab_count == 1
    assert tabs.active_tab is not None
    assert tabs.active_tab.pipeline_id == "p1"
    assert tabs.active_tab.name == "Pipeline 1"


def test_pipeline_tabs_add_multiple_tabs() -> None:
    tabs = PipelineTabs()
    tabs.add_tab(pipeline_id="p1", name="Pipeline 1")
    tabs.add_tab(pipeline_id="p2", name="Pipeline 2")
    assert tabs.tab_count == 2
    # Most recently added tab is active
    assert tabs.active_tab is not None
    assert tabs.active_tab.pipeline_id == "p2"


def test_pipeline_tabs_switch_to() -> None:
    tabs = PipelineTabs()
    tabs.add_tab(pipeline_id="p1", name="Pipeline 1")
    tabs.add_tab(pipeline_id="p2", name="Pipeline 2")
    tabs.switch_to(0)
    assert tabs.active_index == 0
    assert tabs.active_tab is not None
    assert tabs.active_tab.pipeline_id == "p1"


def test_pipeline_tabs_switch_to_invalid_index() -> None:
    tabs = PipelineTabs()
    tabs.add_tab(pipeline_id="p1", name="Pipeline 1")
    tabs.switch_to(99)  # Should not raise
    assert tabs.active_index == 0  # Unchanged


def test_pipeline_tabs_next_tab() -> None:
    tabs = PipelineTabs()
    tabs.add_tab(pipeline_id="p1", name="Pipeline 1")
    tabs.add_tab(pipeline_id="p2", name="Pipeline 2")
    tabs.switch_to(0)
    tabs.next_tab()
    assert tabs.active_index == 1


def test_pipeline_tabs_next_tab_wraps() -> None:
    tabs = PipelineTabs()
    tabs.add_tab(pipeline_id="p1", name="Pipeline 1")
    tabs.add_tab(pipeline_id="p2", name="Pipeline 2")
    # active_index is 1 after adding p2
    tabs.next_tab()
    assert tabs.active_index == 0


def test_pipeline_tabs_remove_tab() -> None:
    tabs = PipelineTabs()
    tabs.add_tab(pipeline_id="p1", name="Pipeline 1")
    tabs.add_tab(pipeline_id="p2", name="Pipeline 2")
    tabs.remove_tab("p1")
    assert tabs.tab_count == 1
    assert tabs.active_tab is not None
    assert tabs.active_tab.pipeline_id == "p2"


def test_pipeline_tabs_update_status() -> None:
    tabs = PipelineTabs()
    tabs.add_tab(pipeline_id="p1", name="Pipeline 1")
    tabs.update_tab_status("p1", AgentStatus.ACTIVE)
    assert tabs.active_tab is not None
    assert tabs.active_tab.status == AgentStatus.ACTIVE


def test_pipeline_tabs_default_status_is_pending() -> None:
    tabs = PipelineTabs()
    tabs.add_tab(pipeline_id="p1", name="Pipeline 1")
    assert tabs.active_tab is not None
    assert tabs.active_tab.status == AgentStatus.PENDING
