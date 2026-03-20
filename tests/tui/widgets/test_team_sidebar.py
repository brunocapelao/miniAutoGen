"""Tests for the TeamSidebar widget."""

from __future__ import annotations

import pytest

from textual.widget import Widget

from miniautogen.tui.status import AgentStatus
from miniautogen.tui.widgets.team_sidebar import TeamSidebar


def test_team_sidebar_is_widget() -> None:
    assert issubclass(TeamSidebar, Widget)


def test_team_sidebar_starts_empty() -> None:
    sidebar = TeamSidebar()
    assert sidebar.agent_count == 0


def test_team_sidebar_add_agent() -> None:
    sidebar = TeamSidebar()
    sidebar.add_agent(
        agent_id="writer",
        name="Writer",
        role="Developer",
        icon="pencil2",
    )
    assert sidebar.agent_count == 1


def test_team_sidebar_add_multiple_agents() -> None:
    sidebar = TeamSidebar()
    sidebar.add_agent(agent_id="writer", name="Writer", role="Developer")
    sidebar.add_agent(agent_id="reviewer", name="Reviewer", role="QA")
    assert sidebar.agent_count == 2


def test_team_sidebar_update_agent_status() -> None:
    sidebar = TeamSidebar()
    sidebar.add_agent(agent_id="writer", name="Writer", role="Developer")
    sidebar.update_agent_status("writer", AgentStatus.ACTIVE)
    card = sidebar.get_agent_card("writer")
    assert card is not None
    assert card.status == AgentStatus.ACTIVE


def test_team_sidebar_get_nonexistent_agent() -> None:
    sidebar = TeamSidebar()
    assert sidebar.get_agent_card("nonexistent") is None


def test_team_sidebar_update_nonexistent_agent_no_error() -> None:
    sidebar = TeamSidebar()
    # Should not raise
    sidebar.update_agent_status("nonexistent", AgentStatus.FAILED)


def test_team_sidebar_clear_agents() -> None:
    sidebar = TeamSidebar()
    sidebar.add_agent(agent_id="writer", name="Writer", role="Developer")
    sidebar.add_agent(agent_id="reviewer", name="Reviewer", role="QA")
    assert sidebar.agent_count == 2
    sidebar.clear_agents()
    assert sidebar.agent_count == 0


def test_team_sidebar_default_status_is_pending() -> None:
    sidebar = TeamSidebar()
    sidebar.add_agent(agent_id="writer", name="Writer", role="Developer")
    card = sidebar.get_agent_card("writer")
    assert card is not None
    assert card.status == AgentStatus.PENDING
