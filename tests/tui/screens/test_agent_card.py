"""Tests for the AgentCard modal screen."""

from __future__ import annotations

import pytest

from textual.screen import ModalScreen

from miniautogen.tui.screens.agent_card import AgentCardScreen


def test_agent_card_screen_is_modal() -> None:
    assert issubclass(AgentCardScreen, ModalScreen)


def test_agent_card_screen_stores_agent_info() -> None:
    screen = AgentCardScreen(
        agent_id="writer",
        agent_name="Writer",
        role="Developer",
        engine="gpt-4",
        goal="Write clean code",
        tools=["file_write", "shell_exec"],
        permissions=["read", "write"],
        status="active",
    )
    assert screen.agent_id == "writer"
    assert screen.agent_name == "Writer"
    assert screen.role == "Developer"
    assert screen.engine == "gpt-4"
    assert screen.goal == "Write clean code"
    assert screen.tools == ["file_write", "shell_exec"]
    assert screen.permissions == ["read", "write"]
    assert screen.status == "active"


def test_agent_card_screen_defaults() -> None:
    screen = AgentCardScreen(
        agent_id="planner",
        agent_name="Planner",
    )
    assert screen.role == ""
    assert screen.engine == ""
    assert screen.goal == ""
    assert screen.tools == []
    assert screen.permissions == []
    assert screen.status == "pending"
