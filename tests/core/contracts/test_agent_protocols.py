"""Tests for agent capability protocols: WorkflowAgent, DeliberationAgent, ConversationalAgent."""

from __future__ import annotations

from typing import Any

from miniautogen.core.contracts.agent import (
    ConversationalAgent,
    DeliberationAgent,
    WorkflowAgent,
)
from miniautogen.core.contracts.agentic_loop import RouterDecision
from miniautogen.core.contracts.deliberation import Contribution, Review


# --- Fake implementations ---


class _FakeWorkflowAgent:
    """Satisfies WorkflowAgent structurally."""

    async def process(self, input: Any) -> Any:
        return {"result": input}


class _FakeDeliberationAgent:
    """Satisfies DeliberationAgent structurally."""

    async def contribute(self, topic: str) -> Contribution:
        return Contribution(participant_id="agent-1", title=topic, content={"body": "analysis"})

    async def review(self, target_id: str, contribution: Contribution) -> Review:
        return Review(
            reviewer_id="agent-1",
            target_id=target_id,
            target_title=contribution.title,
            strengths=["good"],
            concerns=[],
            questions=[],
        )


class _FakeConversationalAgent:
    """Satisfies ConversationalAgent structurally."""

    async def reply(self, message: str, context: dict[str, Any]) -> str:
        return "Hello"

    async def route(self, conversation_history: list[Any]) -> RouterDecision:
        return RouterDecision(
            current_state_summary="summary",
            missing_information="none",
            next_agent="agent-2",
            terminate=False,
        )


class _BrokenWorkflowAgent:
    """Does NOT satisfy WorkflowAgent — missing process()."""

    pass


class _BrokenDeliberationAgent:
    """Does NOT satisfy DeliberationAgent — missing review()."""

    async def contribute(self, topic: str) -> Contribution:
        return Contribution(participant_id="x", title=topic)


class _BrokenConversationalAgent:
    """Does NOT satisfy ConversationalAgent — missing route()."""

    async def reply(self, message: str, context: dict[str, Any]) -> str:
        return "Hello"


# --- WorkflowAgent protocol ---


def test_workflow_agent_is_runtime_checkable() -> None:
    agent = _FakeWorkflowAgent()
    assert isinstance(agent, WorkflowAgent)


def test_broken_workflow_agent_does_not_satisfy_protocol() -> None:
    agent = _BrokenWorkflowAgent()
    assert not isinstance(agent, WorkflowAgent)


# --- DeliberationAgent protocol ---


def test_deliberation_agent_is_runtime_checkable() -> None:
    agent = _FakeDeliberationAgent()
    assert isinstance(agent, DeliberationAgent)


def test_broken_deliberation_agent_does_not_satisfy_protocol() -> None:
    agent = _BrokenDeliberationAgent()
    assert not isinstance(agent, DeliberationAgent)


# --- ConversationalAgent protocol ---


def test_conversational_agent_is_runtime_checkable() -> None:
    agent = _FakeConversationalAgent()
    assert isinstance(agent, ConversationalAgent)


def test_broken_conversational_agent_does_not_satisfy_protocol() -> None:
    agent = _BrokenConversationalAgent()
    assert not isinstance(agent, ConversationalAgent)


# --- Cross-protocol: an agent can satisfy multiple protocols ---


class _MultiCapabilityAgent:
    """Satisfies both WorkflowAgent and ConversationalAgent."""

    async def process(self, input: Any) -> Any:
        return input

    async def reply(self, message: str, context: dict[str, Any]) -> str:
        return "ok"

    async def route(self, conversation_history: list[Any]) -> RouterDecision:
        return RouterDecision(
            current_state_summary="s",
            missing_information="n",
            next_agent="a",
        )


def test_multi_capability_agent_satisfies_both_protocols() -> None:
    agent = _MultiCapabilityAgent()
    assert isinstance(agent, WorkflowAgent)
    assert isinstance(agent, ConversationalAgent)
