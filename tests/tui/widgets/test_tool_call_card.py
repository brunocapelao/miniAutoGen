"""Tests for the ToolCallCard widget -- inline tool invocation display."""

from __future__ import annotations

import pytest

from textual.widget import Widget

from miniautogen.tui.widgets.tool_call_card import ToolCallCard


def test_tool_call_card_is_widget() -> None:
    assert issubclass(ToolCallCard, Widget)


def test_tool_call_card_stores_info() -> None:
    card = ToolCallCard(
        tool_name="file_write",
        action="Writing main.py",
        status="executing",
    )
    assert card.tool_name == "file_write"
    assert card.action == "Writing main.py"
    assert card.status == "executing"


def test_tool_call_card_status_update() -> None:
    card = ToolCallCard(
        tool_name="file_write",
        action="Writing main.py",
        status="executing",
    )
    card.status = "done"
    assert card.status == "done"


def test_tool_call_card_failed_status() -> None:
    card = ToolCallCard(
        tool_name="file_write",
        action="Writing main.py",
        status="failed",
    )
    assert card.status == "failed"


def test_tool_call_card_optional_result() -> None:
    card = ToolCallCard(
        tool_name="file_read",
        action="Reading config.yaml",
        status="done",
        result_summary="42 lines read",
    )
    assert card.result_summary == "42 lines read"


def test_tool_call_card_optional_elapsed() -> None:
    card = ToolCallCard(
        tool_name="shell_exec",
        action="Running tests",
        status="done",
        elapsed=1.5,
    )
    assert card.elapsed == 1.5
