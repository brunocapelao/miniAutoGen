"""AgentRuntime compositor — the core bridge between agents and drivers.

AgentRuntime wraps an AgentDriver with hooks, tools, memory, and delegation,
satisfying WorkflowAgent, ConversationalAgent, and DeliberationAgent protocols
via duck typing.

Public methods: process(), reply(), route(), contribute(), review(),
                initialize(), close()

Internal: _execute_turn(request) -> TurnResult

See docs/pt/architecture/07-agent-anatomy.md for the full design.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, AsyncIterator

import anyio

from miniautogen.backends.driver import AgentDriver
from miniautogen.backends.models import (
    AgentEvent,
    SendTurnRequest,
    StartSessionRequest,
)
from miniautogen.core.contracts.agent_hook import AgentHook
from miniautogen.core.contracts.agentic_loop import RouterDecision
from miniautogen.core.contracts.delegation import (
    DelegationRouterProtocol,
    PersistableMemory,
)
from miniautogen.core.contracts.deliberation import Contribution, DeliberationState, FinalDocument, Review
from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.contracts.memory_provider import MemoryProvider
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.tool_registry import ToolCall, ToolRegistryProtocol
from miniautogen.core.contracts.turn_result import TurnResult
from miniautogen.core.events.event_sink import EventSink, NullEventSink
from miniautogen.core.events.types import EventType
from miniautogen.core.contracts.interaction import InteractionStrategy
from miniautogen.core.runtime.agent_errors import AgentClosedError, AgentSecurityError
from miniautogen.core.runtime.default_prompts import (
    build_default_contribute_prompt,
    build_default_review_prompt,
    build_default_consolidate_prompt,
    build_default_final_document_prompt,
    build_default_route_prompt,
)
from miniautogen.core.runtime.prompt_resolver import resolve_prompt


class AgentRuntime:
    """Compositor that bridges agent protocols to a backend driver.

    Satisfies WorkflowAgent, ConversationalAgent, and DeliberationAgent
    protocols via duck typing. Wraps an AgentDriver with hooks, tools,
    memory, and delegation.
    """

    def __init__(
        self,
        *,
        agent_id: str,
        driver: AgentDriver,
        run_context: RunContext,
        event_sink: EventSink | None = None,
        system_prompt: str | None = None,
        hooks: list[AgentHook] | None = None,
        memory: MemoryProvider | None = None,
        tool_registry: ToolRegistryProtocol | None = None,
        delegation: DelegationRouterProtocol | None = None,
        interaction_strategy: InteractionStrategy | None = None,
        flow_prompts: dict[str, str] | None = None,
        response_format: str = "json",
    ) -> None:
        self._agent_id = agent_id
        self._driver = driver
        self._run_context = run_context
        self._event_sink: EventSink = event_sink or NullEventSink()
        self._system_prompt = system_prompt
        self._hooks = list(hooks) if hooks else []
        self._memory = memory
        self._tool_registry = tool_registry
        self._delegation = delegation
        self._interaction_strategy = interaction_strategy
        self._flow_prompts = flow_prompts or {}
        # TODO(review): _response_format is stored but not yet used in parsing
        # logic. Requires broader design discussion on how response_format
        # should interact with InteractionStrategy and default JSON parsing.
        self._response_format = response_format

        self._session_id: str | None = None
        self._closed = False
        self._prompt_hash: str | None = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def agent_id(self) -> str:
        return self._agent_id

    @property
    def is_closed(self) -> bool:
        return self._closed

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Start driver session, load prompt, hydrate memory from disk."""
        response = await self._driver.start_session(
            StartSessionRequest(
                backend_id=self._agent_id,
                system_prompt=self._system_prompt,
            )
        )
        self._session_id = response.session_id

        # Compute prompt integrity hash (Fix 6)
        if self._system_prompt:
            self._prompt_hash = hashlib.sha256(
                self._system_prompt.encode()
            ).hexdigest()

        # Load persisted memory from disk (Fix 3)
        if isinstance(self._memory, PersistableMemory):
            await self._memory.load_from_disk()

        # Hydrate memory context
        if self._memory is not None:
            await self._memory.get_context(
                self._agent_id,
                self._run_context,
            )
            await self._emit(
                EventType.AGENT_MEMORY_LOADED,
                {"agent_id": self._agent_id},
            )

        await self._emit(
            EventType.AGENT_INITIALIZED,
            {"agent_id": self._agent_id, "session_id": self._session_id},
        )

    async def close(self) -> None:
        """Distill memory, persist to disk, close driver session.

        Runs in a shielded cancel scope to prevent cancellation during cleanup.
        """
        with anyio.CancelScope(shield=True):
            # Distill memory
            if self._memory is not None:
                await self._memory.distill(self._agent_id)

            # Persist memory to disk (Fix 3)
            if isinstance(self._memory, PersistableMemory):
                await self._memory.persist_to_disk()
                await self._emit(
                    EventType.AGENT_MEMORY_SAVED,
                    {"agent_id": self._agent_id},
                )

            # Close driver session
            if self._session_id is not None:
                await self._driver.close_session(self._session_id)

            self._closed = True

            await self._emit(
                EventType.AGENT_CLOSED,
                {"agent_id": self._agent_id},
            )

    # ------------------------------------------------------------------
    # WorkflowAgent protocol
    # ------------------------------------------------------------------

    async def process(self, input: Any) -> Any:
        """Execute a workflow turn. Returns the driver's text output."""
        self._check_closed()
        messages = self._build_messages(str(input))
        result = await self._execute_turn(messages)
        return result.text

    async def execute(self, prompt: str) -> str:
        """Execute a prompt and return raw response.

        No parsing, no format assumptions. The AgentRuntime enriches the
        prompt with context (system prompt, memory, tools) and delegates
        to the backend driver.

        This is the preferred method for Coordination Runtimes that build
        their own prompts and handle their own response parsing.

        Args:
            prompt: The complete prompt to send to the agent.

        Returns:
            Raw text response from the backend driver.
        """
        self._check_closed()
        messages = self._build_messages(prompt)
        result = await self._execute_turn(messages)
        return result.text

    # ------------------------------------------------------------------
    # ConversationalAgent protocol
    # ------------------------------------------------------------------

    async def reply(self, message: str, context: dict[str, Any]) -> str:
        """Reply to a conversational message."""
        self._check_closed()
        messages = self._build_messages(message)
        result = await self._execute_turn(messages)
        return result.text

    async def route(self, conversation_history: list[Any]) -> RouterDecision:
        """Route a conversation to the next agent.

        Uses cascade resolution: InteractionStrategy -> YAML -> default.
        """
        self._check_closed()

        prompt = await resolve_prompt(
            action="route",
            context={"conversation_history": conversation_history},
            strategy=self._interaction_strategy,
            flow_prompts=self._flow_prompts,
            default_prompt=build_default_route_prompt(),
        )

        messages: list[dict[str, Any]] = []
        for item in conversation_history:
            if isinstance(item, dict):
                messages.append(item)
            else:
                messages.append({"role": "user", "content": str(item)})
        messages.append({"role": "user", "content": prompt})

        result = await self._execute_turn(messages)
        data = json.loads(result.text)
        return RouterDecision(**data)

    # ------------------------------------------------------------------
    # DeliberationAgent protocol
    # ------------------------------------------------------------------

    async def contribute(self, topic: str) -> Contribution:
        """Produce a contribution for a deliberation topic.

        Uses cascade resolution: InteractionStrategy -> YAML -> default.
        """
        self._check_closed()

        prompt = await resolve_prompt(
            action="contribute",
            context={"topic": topic},
            strategy=self._interaction_strategy,
            flow_prompts=self._flow_prompts,
            default_prompt=build_default_contribute_prompt(topic=topic),
        )
        result_text = await self.execute(prompt)

        # Use InteractionStrategy.parse_response() when available
        if self._interaction_strategy is not None:
            parsed = await self._interaction_strategy.parse_response("contribute", result_text)
            return Contribution(
                participant_id=self._agent_id,
                title=parsed.get("title", topic),
                content=parsed.get("content", {}),
            )

        # Default JSON parsing fallback
        try:
            data = json.loads(result_text)
        except (json.JSONDecodeError, TypeError, ValueError):
            # Backend returned free text — wrap it as a contribution
            return Contribution(
                participant_id=self._agent_id,
                title=topic,
                content={"text": result_text},
            )
        return Contribution(
            participant_id=self._agent_id,
            title=data.get("title", topic),
            content=data.get("content", {}),
        )

    async def review(
        self, target_id: str, contribution: Contribution
    ) -> Review:
        """Review another agent's contribution.

        Uses cascade resolution: InteractionStrategy -> YAML -> default.
        """
        self._check_closed()

        prompt = await resolve_prompt(
            action="review",
            context={
                "target_id": target_id,
                "target": target_id,
                "contribution": contribution,
                "content": str(contribution.content),
                "role": self._agent_id,
            },
            strategy=self._interaction_strategy,
            flow_prompts=self._flow_prompts,
            default_prompt=build_default_review_prompt(
                target_id=target_id, contribution=contribution
            ),
        )
        result_text = await self.execute(prompt)

        # Use InteractionStrategy.parse_response() when available
        if self._interaction_strategy is not None:
            parsed = await self._interaction_strategy.parse_response("review", result_text)
            return Review(
                reviewer_id=self._agent_id,
                target_id=target_id,
                target_title=contribution.title,
                strengths=parsed.get("strengths", []),
                concerns=parsed.get("concerns", []),
                questions=parsed.get("questions", []),
            )

        # Default JSON parsing fallback (with fence extraction)
        data = self._extract_json(result_text)
        if data is None:
            text = result_text or ""
            data = {
                "strengths": [],
                "concerns": [text] if text else [],
                "questions": [],
            }
        return Review(
            reviewer_id=self._agent_id,
            target_id=target_id,
            target_title=contribution.title,
            strengths=data.get("strengths", []),
            concerns=data.get("concerns", []),
            questions=data.get("questions", []),
        )

    async def consolidate(
        self,
        topic: str,
        contributions: list[Contribution],
        reviews: list[Review],
    ) -> DeliberationState:
        """Leader consolidates contributions and reviews into a state.

        Uses cascade resolution: InteractionStrategy -> YAML -> default.
        """
        self._check_closed()

        contrib_summary = "\n".join(
            f"- {c.participant_id}: {c.title}" for c in contributions
        )
        review_summary = "\n".join(
            f"- {r.reviewer_id} on {r.target_id}: strengths={r.strengths}, concerns={r.concerns}"
            for r in reviews
        )

        prompt = await resolve_prompt(
            action="consolidate",
            context={
                "topic": topic,
                "contributions": contributions,
                "reviews": reviews,
                "contributions_summary": contrib_summary,
                "reviews_summary": review_summary,
                "role": self._agent_id,
            },
            strategy=self._interaction_strategy,
            flow_prompts=self._flow_prompts,
            default_prompt=build_default_consolidate_prompt(
                topic=topic, contributions=contributions, reviews=reviews
            ),
        )
        result_text = await self.execute(prompt)

        # Use InteractionStrategy.parse_response() when available
        if self._interaction_strategy is not None:
            parsed = await self._interaction_strategy.parse_response("consolidate", result_text)
            return DeliberationState(
                review_cycle=1,
                accepted_facts=parsed.get("accepted_facts", []),
                open_conflicts=parsed.get("open_conflicts", []),
                pending_gaps=parsed.get("pending_gaps", []),
                leader_decision=parsed.get("leader_decision"),
                is_sufficient=parsed.get("is_sufficient", True),
                rejection_reasons=parsed.get("rejection_reasons", []),
            )

        # Default JSON parsing fallback (with fence extraction)
        data = self._extract_json(result_text)
        if data is None:
            return DeliberationState(
                review_cycle=1,
                is_sufficient=True,
                leader_decision=result_text or "Approved",
            )
        return DeliberationState(
            review_cycle=1,
            accepted_facts=data.get("accepted_facts", []),
            open_conflicts=data.get("open_conflicts", []),
            pending_gaps=data.get("pending_gaps", []),
            leader_decision=data.get("leader_decision"),
            is_sufficient=data.get("is_sufficient", True),
            rejection_reasons=data.get("rejection_reasons", []),
        )

    async def produce_final_document(
        self,
        state: DeliberationState,
        contributions: list[Contribution],
    ) -> FinalDocument:
        """Leader produces the final consolidated document.

        Uses cascade resolution: InteractionStrategy -> YAML -> default.
        """
        self._check_closed()

        contrib_text = "\n".join(
            f"- {c.participant_id}: {json.dumps(c.content)[:500]}"
            for c in contributions
        )

        prompt = await resolve_prompt(
            action="produce_final_document",
            context={
                "state": state,
                "contributions": contributions,
                "contributions_summary": contrib_text,
                "role": self._agent_id,
            },
            strategy=self._interaction_strategy,
            flow_prompts=self._flow_prompts,
            default_prompt=build_default_final_document_prompt(
                state=state, contributions=contributions
            ),
        )
        result_text = await self.execute(prompt)

        # Use InteractionStrategy.parse_response() when available
        if self._interaction_strategy is not None:
            parsed = await self._interaction_strategy.parse_response(
                "produce_final_document", result_text
            )
            return FinalDocument(
                executive_summary=parsed.get("executive_summary", ""),
                accepted_facts=parsed.get("accepted_facts", []),
                open_conflicts=parsed.get("open_conflicts", []),
                pending_decisions=parsed.get("pending_decisions", []),
                recommendations=parsed.get("recommendations", []),
                decision_summary=parsed.get("decision_summary", ""),
                body_markdown=parsed.get("body_markdown", ""),
            )

        # Default JSON parsing fallback (with fence extraction)
        data = self._extract_json(result_text)
        if data is None:
            return FinalDocument(
                executive_summary=result_text or "Deliberation complete.",
                decision_summary=state.leader_decision or "Approved",
                body_markdown=result_text or "",
            )
        return FinalDocument(
            executive_summary=data.get("executive_summary", ""),
            accepted_facts=data.get("accepted_facts", []),
            open_conflicts=data.get("open_conflicts", []),
            pending_decisions=data.get("pending_decisions", []),
            recommendations=data.get("recommendations", []),
            decision_summary=data.get("decision_summary", ""),
            body_markdown=data.get("body_markdown", ""),
        )

    # ------------------------------------------------------------------
    # Internal: turn execution
    # ------------------------------------------------------------------

    async def _execute_turn(
        self, messages: list[dict[str, Any]]
    ) -> TurnResult:
        """Core turn execution pipeline.

        1. Emit AGENT_TURN_STARTED
        2. Run before_turn hooks (waterfall)
        3. Enrich with memory context
        4. Enrich with tool definitions
        5. driver.send_turn() — collect events, extract text
        6. Save turn to memory
        7. Run after_event hooks
        8. Emit AGENT_TURN_COMPLETED
        """
        self._check_closed()
        assert self._session_id is not None, "Must call initialize() first"

        # 0. Verify prompt integrity (Fix 6)
        if self._prompt_hash and self._system_prompt:
            current_hash = hashlib.sha256(
                self._system_prompt.encode()
            ).hexdigest()
            if current_hash != self._prompt_hash:
                raise AgentSecurityError("Prompt integrity violation")

        # 1. Emit turn started
        await self._emit(
            EventType.AGENT_TURN_STARTED,
            {"agent_id": self._agent_id, "session_id": self._session_id},
        )

        # 2. Run before_turn hooks (waterfall)
        for hook in self._hooks:
            messages = await hook.before_turn(messages, self._run_context)

        # 3. Enrich with memory context
        if self._memory is not None:
            memory_msgs = await self._memory.get_context(
                self._agent_id,
                self._run_context,
            )
            messages = memory_msgs + messages

        # 4. Enrich with tool definitions
        if self._tool_registry is not None:
            tool_defs = self._tool_registry.list_tools()
            if tool_defs:
                tools_desc = "\n".join(
                    f"- {t.name}: {t.description}" for t in tool_defs
                )
                messages.insert(
                    0,
                    {
                        "role": "system",
                        "content": f"Available tools:\n{tools_desc}",
                    },
                )

        # 5. Send turn to driver and collect events
        request = SendTurnRequest(
            session_id=self._session_id,
            messages=messages,
        )

        collected_text_parts: list[str] = []
        driver_events: list[AgentEvent] = []

        async for event in self._driver.send_turn(request):
            driver_events.append(event)
            # Extract text from message_completed events
            if event.type == "message_completed":
                text = event.payload.get("text", "")
                if text:
                    collected_text_parts.append(text)
            elif event.type == "message_delta":
                text = event.payload.get("text", "")
                if text:
                    collected_text_parts.append(text)

        full_text = "".join(collected_text_parts)

        # 5b. Process tool call requests from driver events (Fix 1)
        executed_tool_calls: list[ToolCall] = []
        if self._tool_registry is not None:
            for event in driver_events:
                if event.type == "tool_call_requested":
                    tool_name = event.payload.get("tool_name", "")
                    call_id = event.payload.get("call_id", "")
                    params = event.payload.get("params", {})
                    if tool_name and self._tool_registry.has_tool(tool_name):
                        call = ToolCall(
                            tool_name=tool_name,
                            call_id=call_id,
                            params=params,
                        )
                        tool_result = await self._tool_registry.execute_tool(
                            call
                        )
                        executed_tool_calls.append(call)
                        await self._emit(
                            EventType.AGENT_TOOL_INVOKED,
                            {
                                "agent_id": self._agent_id,
                                "tool_name": tool_name,
                                "call_id": call_id,
                                "success": tool_result.success,
                            },
                        )

        result = TurnResult(
            output=full_text,
            text=full_text,
            messages=messages,
            tool_calls=executed_tool_calls,
        )

        # 6. Save turn to memory (Fix 9: no AGENT_MEMORY_SAVED here)
        if self._memory is not None:
            turn_messages = messages + [
                {"role": "assistant", "content": full_text}
            ]
            await self._memory.save_turn(turn_messages, self._run_context)

        # 7. Run after_event hooks
        completed_event = ExecutionEvent(
            type=EventType.AGENT_TURN_COMPLETED.value,
            run_id=self._run_context.run_id,
            correlation_id=self._run_context.correlation_id,
            payload={
                "agent_id": self._agent_id,
                "text": full_text,
            },
        )
        for hook in self._hooks:
            completed_event = await hook.after_event(
                completed_event, self._run_context
            )

        # 8. Emit turn completed
        await self._event_sink.publish(completed_event)

        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _check_closed(self) -> None:
        """Raise AgentClosedError if the runtime has been closed."""
        if self._closed:
            raise AgentClosedError(
                f"Agent '{self._agent_id}' has been closed"
            )

    def _extract_json(self, text: str) -> dict[str, Any] | None:
        """Extract JSON from text, handling markdown code fences.

        Tries to parse JSON from within ```json ... ``` fences first,
        then falls back to parsing the raw text. Returns None if parsing fails.
        """
        text = text or ""
        fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        raw = fence_match.group(1).strip() if fence_match else text
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError, ValueError):
            return None

    def _build_messages(self, user_content: str) -> list[dict[str, Any]]:
        """Build a simple message list from user content."""
        messages: list[dict[str, Any]] = []
        if self._system_prompt:
            messages.append(
                {"role": "system", "content": self._system_prompt}
            )
        messages.append({"role": "user", "content": user_content})
        return messages

    async def _emit(
        self, event_type: EventType, payload: dict[str, Any]
    ) -> None:
        """Emit an ExecutionEvent through the event sink."""
        event = ExecutionEvent(
            type=event_type.value,
            run_id=self._run_context.run_id,
            correlation_id=self._run_context.correlation_id,
            payload=payload,
        )
        await self._event_sink.publish(event)
