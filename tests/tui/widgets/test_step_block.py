"""Tests for the StepBlock widget -- a pipeline step in the interaction log."""

from __future__ import annotations

import pytest

from textual.widget import Widget

from miniautogen.tui.status import AgentStatus
from miniautogen.tui.widgets.step_block import StepBlock


def test_step_block_is_widget() -> None:
    assert issubclass(StepBlock, Widget)


def test_step_block_stores_step_info() -> None:
    block = StepBlock(
        step_number=1,
        step_label="Planning",
        agent_name="Planner",
        agent_icon="\U0001f3db",
    )
    assert block.step_number == 1
    assert block.step_label == "Planning"
    assert block.agent_name == "Planner"


def test_step_block_default_status_is_pending() -> None:
    block = StepBlock(
        step_number=1,
        step_label="Planning",
    )
    assert block.status == AgentStatus.PENDING


def test_step_block_status_update() -> None:
    block = StepBlock(
        step_number=1,
        step_label="Planning",
    )
    block.status = AgentStatus.ACTIVE
    assert block.status == AgentStatus.ACTIVE


def test_step_block_add_message() -> None:
    block = StepBlock(
        step_number=1,
        step_label="Planning",
    )
    block.add_message(agent_name="Planner", content="Starting plan.")
    assert block.message_count == 1


def test_step_block_collapsed_state() -> None:
    block = StepBlock(
        step_number=1,
        step_label="Planning",
    )
    assert block.collapsed is False
    block.collapsed = True
    assert block.collapsed is True


def test_step_block_done_auto_collapses() -> None:
    """When status changes to DONE, the block should auto-collapse."""
    block = StepBlock(
        step_number=1,
        step_label="Planning",
    )
    block.status = AgentStatus.DONE
    assert block.collapsed is True
