"""HumanAgent — human as a first-class participant in coordination flows.

Implements the same agent protocols (WorkflowAgent, ConversationalAgent,
DeliberationAgent) but directs interactions to a human via a pluggable
InputChannel. The runtime treats the human exactly like an AI agent,
pausing execution until human input arrives.

This enables true Human-Swarm coordination where humans participate as
peers alongside LLM agents in Workflow, Deliberation, and AgenticLoop
coordination modes.

Architecture:
    HumanAgent wraps an InputChannel (stdin, websocket, HTTP queue, etc.)
    and satisfies the same protocols as AgentRuntime. The coordination
    runtimes dispatch to it identically — they don't know (or care)
    whether the agent is human or AI.

Usage::

    from miniautogen.core.runtime.human_agent import HumanAgent, StdinInputChannel

    # Terminal-based human
    human = HumanAgent(agent_id="human-reviewer", channel=StdinInputChannel())

    # Or async queue-based (for web/Slack)
    human = HumanAgent(agent_id="pm", channel=QueueInputChannel())

    # Use in any coordination mode
    registry = {"analyst": ai_agent, "pm": human}
    result = await deliberation_runtime.run(agents, context, plan)

.. stability:: experimental
"""

from __future__ import annotations

import asyncio
from typing import Any, Protocol, runtime_checkable

from miniautogen.core.contracts.agentic_loop import RouterDecision
from miniautogen.core.contracts.deliberation import (
    Contribution,
    DeliberationState,
    FinalDocument,
    Review,
)


@runtime_checkable
class InputChannel(Protocol):
    """Protocol for receiving human input.

    Implementations can be synchronous (stdin), asynchronous (websocket),
    or queue-based (HTTP endpoint). The HumanAgent awaits the channel's
    ``receive()`` method, blocking the flow until input arrives.
    """

    async def send_prompt(self, prompt: str, context: dict[str, Any]) -> None:
        """Display a prompt to the human.

        Args:
            prompt: The question or task for the human.
            context: Additional context (agent_id, action, topic, etc.).
        """
        ...

    async def receive(self, timeout_seconds: float | None = None) -> str:
        """Wait for and return human input.

        Args:
            timeout_seconds: Maximum time to wait (None = indefinite).

        Returns:
            The human's text response.

        Raises:
            TimeoutError: If timeout_seconds exceeded.
        """
        ...


class StdinInputChannel:
    """InputChannel that reads from stdin (terminal).

    Suitable for CLI and interactive terminal sessions.
    """

    async def send_prompt(self, prompt: str, context: dict[str, Any]) -> None:
        agent_id = context.get("agent_id", "human")
        action = context.get("action", "input")
        print(f"\n[{agent_id}] ({action}) {prompt}")

    async def receive(self, timeout_seconds: float | None = None) -> str:
        loop = asyncio.get_running_loop()
        if timeout_seconds is not None:
            return await asyncio.wait_for(
                loop.run_in_executor(None, input, "> "),
                timeout=timeout_seconds,
            )
        return await loop.run_in_executor(None, input, "> ")


class QueueInputChannel:
    """InputChannel backed by an asyncio.Queue.

    Ideal for web UIs, Slack bots, and other async integrations.
    The external system pushes responses into the queue; the HumanAgent
    awaits them.

    Example::

        channel = QueueInputChannel()
        human = HumanAgent(agent_id="pm", channel=channel)

        # In your web handler:
        channel.push_response("Looks good, approved!")
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._last_prompt: str | None = None
        self._last_context: dict[str, Any] = {}

    @property
    def last_prompt(self) -> str | None:
        """The last prompt sent to the human."""
        return self._last_prompt

    @property
    def last_context(self) -> dict[str, Any]:
        """The context of the last prompt."""
        return self._last_context

    async def send_prompt(self, prompt: str, context: dict[str, Any]) -> None:
        self._last_prompt = prompt
        self._last_context = context

    async def receive(self, timeout_seconds: float | None = None) -> str:
        if timeout_seconds is not None:
            return await asyncio.wait_for(
                self._queue.get(), timeout=timeout_seconds,
            )
        return await self._queue.get()

    def push_response(self, response: str) -> None:
        """Push a response into the queue (called by external system)."""
        self._queue.put_nowait(response)


class HumanAgent:
    """Human participant that satisfies all agent coordination protocols.

    Wraps an InputChannel to present prompts and collect responses.
    The coordination runtime treats this exactly like an AI agent.

    Satisfies: WorkflowAgent, ConversationalAgent, DeliberationAgent.
    """

    def __init__(
        self,
        *,
        agent_id: str,
        channel: InputChannel,
        timeout_seconds: float | None = None,
    ) -> None:
        self._agent_id = agent_id
        self._channel = channel
        self._timeout = timeout_seconds

    @property
    def agent_id(self) -> str:
        return self._agent_id

    # -- WorkflowAgent protocol --

    async def process(self, input: Any) -> Any:
        """Present the input to the human and return their response."""
        await self._channel.send_prompt(
            f"Please process the following:\n\n{input}",
            {"agent_id": self._agent_id, "action": "process"},
        )
        return await self._channel.receive(self._timeout)

    # -- ConversationalAgent protocol --

    async def reply(self, message: str, context: dict[str, Any]) -> str:
        await self._channel.send_prompt(
            message,
            {"agent_id": self._agent_id, "action": "reply", **context},
        )
        return await self._channel.receive(self._timeout)

    async def route(self, conversation_history: list[Any]) -> RouterDecision:
        history_text = "\n".join(str(m) for m in conversation_history[-5:])
        await self._channel.send_prompt(
            f"Conversation so far:\n{history_text}\n\n"
            "Who should speak next? (or type 'done' to finish)",
            {"agent_id": self._agent_id, "action": "route"},
        )
        response = await self._channel.receive(self._timeout)

        if response.strip().lower() in ("done", "finish", "end", "terminate"):
            return RouterDecision(
                current_state_summary="Human terminated",
                missing_information="none",
                terminate=True,
            )
        return RouterDecision(
            current_state_summary="Human routed",
            missing_information="pending",
            next_agent=response.strip(),
        )

    # -- DeliberationAgent protocol --

    async def contribute(self, topic: str) -> Contribution:
        await self._channel.send_prompt(
            f"Topic: {topic}\n\nPlease provide your contribution:",
            {"agent_id": self._agent_id, "action": "contribute", "topic": topic},
        )
        response = await self._channel.receive(self._timeout)
        return Contribution(
            participant_id=self._agent_id,
            title=topic,
            content={"text": response},
        )

    async def review(self, target_id: str, contribution: Contribution) -> Review:
        content_text = str(contribution.content)
        await self._channel.send_prompt(
            f"Review {target_id}'s contribution on '{contribution.title}':\n"
            f"{content_text}\n\n"
            "Please list strengths, concerns, and questions:",
            {
                "agent_id": self._agent_id,
                "action": "review",
                "target_id": target_id,
            },
        )
        response = await self._channel.receive(self._timeout)
        return Review(
            reviewer_id=self._agent_id,
            target_id=target_id,
            target_title=contribution.title,
            strengths=[],
            concerns=[response] if response.strip() else [],
            questions=[],
        )

    async def consolidate(
        self,
        topic: str,
        contributions: list[Contribution],
        reviews: list[Review],
    ) -> DeliberationState:
        summary = "\n".join(
            f"- {c.participant_id}: {c.title}" for c in contributions
        )
        await self._channel.send_prompt(
            f"Topic: {topic}\nContributions:\n{summary}\n\n"
            "Is the deliberation sufficient? (yes/no)",
            {"agent_id": self._agent_id, "action": "consolidate"},
        )
        response = await self._channel.receive(self._timeout)
        is_sufficient = response.strip().lower() in ("yes", "y", "sufficient")
        return DeliberationState(
            review_cycle=1,
            is_sufficient=is_sufficient,
            leader_decision=response,
        )

    async def produce_final_document(
        self,
        state: DeliberationState,
        contributions: list[Contribution],
    ) -> FinalDocument:
        await self._channel.send_prompt(
            "Please write the final summary document:",
            {"agent_id": self._agent_id, "action": "produce_final_document"},
        )
        response = await self._channel.receive(self._timeout)
        return FinalDocument(
            executive_summary=response,
            decision_summary=state.leader_decision or "Human decision",
            body_markdown=response,
        )

    # -- Lifecycle --

    async def initialize(self) -> None:
        """No-op — humans don't need initialization."""

    async def close(self) -> None:
        """No-op — humans don't need cleanup."""
