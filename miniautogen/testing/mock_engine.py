"""MockEngine — deterministic agent simulation for unit tests.

Instead of mocking HTTP responses (fragile when prompts change), MockEngine
mocks the *agent decision* — the semantic behavior. This lets you test
coordination logic ("if Agent A delegates to B, does the flow do X?")
without tokens or network.

Usage::

    engine = MockEngine()

    # Script responses per agent
    engine.script("analyst", [
        {"action": "process", "response": "analysis complete"},
        {"action": "contribute", "response": {"title": "Analysis", "content": {}}},
    ])

    # Or use a callable for dynamic responses
    engine.script_fn("reviewer", lambda action, input: "approved")

    # Use as agent in coordination runtimes
    result = await workflow_runtime.run(
        agents=[engine.agent("analyst"), engine.agent("reviewer")],
        context=ctx,
        plan=plan,
    )

    # Verify interactions
    assert engine.call_count("analyst") == 2
    assert engine.calls("analyst")[0]["action"] == "process"
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from miniautogen.core.contracts.agentic_loop import RouterDecision
from miniautogen.core.contracts.deliberation import (
    Contribution,
    DeliberationState,
    FinalDocument,
    Review,
)


@dataclass
class _CallRecord:
    """Record of a single agent method invocation."""

    action: str
    input: Any
    response: Any


class MockAgent:
    """A mock agent that replays scripted responses.

    Satisfies WorkflowAgent, ConversationalAgent, and DeliberationAgent
    protocols via duck typing — exactly like AgentRuntime.
    """

    def __init__(
        self,
        agent_id: str,
        responses: list[dict[str, Any]] | None = None,
        response_fn: Callable[[str, Any], Any] | None = None,
    ) -> None:
        self._agent_id = agent_id
        self._responses = list(responses) if responses else []
        self._response_fn = response_fn
        self._call_index = 0
        self._calls: list[_CallRecord] = []

    @property
    def agent_id(self) -> str:
        return self._agent_id

    def _get_response(self, action: str, input_data: Any) -> Any:
        """Get the next scripted response or call the response function."""
        if self._response_fn is not None:
            return self._response_fn(action, input_data)

        if self._call_index >= len(self._responses):
            raise IndexError(
                f"MockAgent '{self._agent_id}' ran out of scripted responses "
                f"(called {self._call_index + 1} times, "
                f"only {len(self._responses)} scripted)"
            )

        entry = self._responses[self._call_index]
        self._call_index += 1
        return entry.get("response", entry.get("output", ""))

    def _record(self, action: str, input_data: Any, response: Any) -> None:
        self._calls.append(_CallRecord(action=action, input=input_data, response=response))

    # -- WorkflowAgent protocol --

    async def process(self, input: Any) -> Any:
        response = self._get_response("process", input)
        self._record("process", input, response)
        return response

    # -- ConversationalAgent protocol --

    async def reply(self, message: str, context: dict[str, Any]) -> str:
        response = self._get_response("reply", message)
        self._record("reply", message, response)
        return str(response)

    async def route(self, conversation_history: list[Any]) -> RouterDecision:
        response = self._get_response("route", conversation_history)
        self._record("route", conversation_history, response)
        if isinstance(response, RouterDecision):
            return response
        if isinstance(response, dict):
            return RouterDecision(**response)
        raise TypeError(f"route response must be RouterDecision or dict, got {type(response)}")

    # -- DeliberationAgent protocol --

    async def contribute(self, topic: str) -> Contribution:
        response = self._get_response("contribute", topic)
        self._record("contribute", topic, response)
        if isinstance(response, Contribution):
            return response
        if isinstance(response, dict):
            return Contribution(
                participant_id=self._agent_id,
                title=response.get("title", topic),
                content=response.get("content", {}),
            )
        return Contribution(
            participant_id=self._agent_id,
            title=topic,
            content={"text": str(response)},
        )

    async def review(self, target_id: str, contribution: Contribution) -> Review:
        response = self._get_response("review", (target_id, contribution))
        self._record("review", (target_id, contribution), response)
        if isinstance(response, Review):
            return response
        if isinstance(response, dict):
            return Review(
                reviewer_id=self._agent_id,
                target_id=target_id,
                target_title=contribution.title,
                strengths=response.get("strengths", []),
                concerns=response.get("concerns", []),
                questions=response.get("questions", []),
            )
        return Review(
            reviewer_id=self._agent_id,
            target_id=target_id,
            target_title=contribution.title,
            strengths=[],
            concerns=[str(response)] if response else [],
            questions=[],
        )

    async def consolidate(
        self,
        topic: str,
        contributions: list[Contribution],
        reviews: list[Review],
    ) -> DeliberationState:
        response = self._get_response("consolidate", (topic, contributions, reviews))
        self._record("consolidate", topic, response)
        if isinstance(response, DeliberationState):
            return response
        if isinstance(response, dict):
            return DeliberationState(**response)
        return DeliberationState(review_cycle=1, is_sufficient=True)

    async def produce_final_document(
        self,
        state: DeliberationState,
        contributions: list[Contribution],
    ) -> FinalDocument:
        response = self._get_response("produce_final_document", (state, contributions))
        self._record("produce_final_document", state, response)
        if isinstance(response, FinalDocument):
            return response
        if isinstance(response, dict):
            return FinalDocument(**response)
        return FinalDocument(
            executive_summary=str(response) if response else "Mock summary",
            decision_summary="Mock decision",
            body_markdown="",
        )

    # -- Lifecycle --

    async def initialize(self) -> None:
        """No-op for mock agents."""

    async def close(self) -> None:
        """No-op for mock agents."""

    # -- Execution (AgentRuntime-compatible) --

    async def execute(self, prompt: str) -> str:
        response = self._get_response("execute", prompt)
        self._record("execute", prompt, response)
        return str(response)


class MockEngine:
    """Factory for creating deterministic mock agents for testing.

    Manages a registry of mock agents with scripted responses.
    Use this to test coordination logic without LLM calls.

    Example::

        engine = MockEngine()
        engine.script("analyst", [
            {"action": "process", "response": "analyzed data"},
        ])
        engine.script("reviewer", [
            {"action": "process", "response": "review complete"},
        ])

        # Get agents for use in runtimes
        analyst = engine.agent("analyst")
        reviewer = engine.agent("reviewer")

        # After execution, verify interactions
        assert engine.call_count("analyst") == 1
        assert engine.calls("analyst")[0].action == "process"
    """

    def __init__(self) -> None:
        self._agents: dict[str, MockAgent] = {}

    def script(
        self,
        agent_id: str,
        responses: list[dict[str, Any]],
    ) -> "MockEngine":
        """Script deterministic responses for an agent.

        Args:
            agent_id: Agent identifier.
            responses: List of response dicts. Each dict should have:
                - "response" or "output": The value to return.
                Responses are consumed in order.

        Returns:
            Self for method chaining.
        """
        self._agents[agent_id] = MockAgent(agent_id, responses=responses)
        return self

    def script_fn(
        self,
        agent_id: str,
        fn: Callable[[str, Any], Any],
    ) -> "MockEngine":
        """Script a dynamic response function for an agent.

        Args:
            agent_id: Agent identifier.
            fn: Callable(action, input) -> response. Called for every
                agent method invocation.

        Returns:
            Self for method chaining.
        """
        self._agents[agent_id] = MockAgent(agent_id, response_fn=fn)
        return self

    def agent(self, agent_id: str) -> MockAgent:
        """Get the MockAgent for the given ID.

        Raises:
            KeyError: If agent has not been scripted.
        """
        if agent_id not in self._agents:
            raise KeyError(
                f"No mock agent scripted for '{agent_id}'. "
                f"Call engine.script('{agent_id}', [...]) first."
            )
        return self._agents[agent_id]

    def registry(self) -> dict[str, MockAgent]:
        """Get all agents as a registry dict (for coordination runtimes)."""
        return dict(self._agents)

    def call_count(self, agent_id: str) -> int:
        """Get the number of calls made to an agent."""
        return len(self._agents[agent_id]._calls)

    def calls(self, agent_id: str) -> list[_CallRecord]:
        """Get all call records for an agent."""
        return list(self._agents[agent_id]._calls)

    def reset(self) -> None:
        """Reset all agents to their initial state."""
        for agent in self._agents.values():
            agent._call_index = 0
            agent._calls.clear()
