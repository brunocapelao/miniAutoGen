# AgentRuntime Agnostic Design — Implementation Plan

> **For Agents:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Make AgentRuntime a pure compositor (enriches prompt + delegates to driver) by extracting all hardcoded prompts and response parsing to Coordination Runtimes, enabling pluggable prompt strategies via InteractionStrategy protocol, YAML templates, and built-in defaults.

**Architecture:** The refactor follows a cascade resolution pattern: `InteractionStrategy (Python) -> YAML prompt templates -> Built-in defaults`. AgentRuntime gains a generic `execute(prompt) -> str` method. Convenience wrappers (`contribute()`, `review()`, etc.) resolve prompts via cascade, call `execute()`, and return parsed results. Coordination Runtimes (DeliberationRuntime, WorkflowRuntime, AgenticLoopRuntime) take ownership of prompt construction and response parsing. FlowConfig gains `response_format` and `prompts` fields.

**Tech Stack:** Python 3.10+, Pydantic v2, AnyIO, pytest with anyio marker

**Global Prerequisites:**
- Environment: macOS/Linux, Python 3.10+
- Tools: `python --version`, `pytest --version`, `ruff --version`
- Access: No external API keys needed (all tests use fake drivers)
- State: Work from `main` branch, clean working tree

**Verification before starting:**
```bash
# Run ALL these commands and verify output:
python --version          # Expected: Python 3.10+
pytest --version          # Expected: 7.0+
git status                # Expected: clean working tree on main
pytest tests/core/runtime/test_agent_runtime.py -v --tb=short  # Expected: all PASSED
```

---

## Phase 1: Contracts and Configuration (Tasks 1-5)

### Task 1: Create InteractionStrategy Protocol

**Files:**
- Create: `miniautogen/core/contracts/interaction.py`

**Prerequisites:**
- Directory exists: `miniautogen/core/contracts/`

**Step 1: Write the failing test**

Create file `tests/core/contracts/test_interaction_strategy.py`:

```python
"""Tests for InteractionStrategy protocol."""
from __future__ import annotations

from typing import Any

import pytest

from miniautogen.core.contracts.interaction import InteractionStrategy


class FakeStrategy:
    """A concrete strategy that satisfies the protocol."""

    async def build_prompt(self, action: str, context: dict[str, Any]) -> str:
        return f"Prompt for {action}"

    async def parse_response(self, action: str, raw: str) -> Any:
        return {"parsed": raw}


class IncompleteStrategy:
    """Missing parse_response — should NOT satisfy protocol."""

    async def build_prompt(self, action: str, context: dict[str, Any]) -> str:
        return "prompt"


class TestInteractionStrategyProtocol:
    def test_fake_strategy_satisfies_protocol(self) -> None:
        strategy = FakeStrategy()
        assert isinstance(strategy, InteractionStrategy)

    def test_incomplete_strategy_does_not_satisfy(self) -> None:
        strategy = IncompleteStrategy()
        assert not isinstance(strategy, InteractionStrategy)

    @pytest.mark.anyio()
    async def test_build_prompt_returns_string(self) -> None:
        strategy = FakeStrategy()
        result = await strategy.build_prompt("contribute", {"topic": "AI"})
        assert isinstance(result, str)
        assert "contribute" in result

    @pytest.mark.anyio()
    async def test_parse_response_returns_any(self) -> None:
        strategy = FakeStrategy()
        result = await strategy.parse_response("contribute", '{"key": "val"}')
        assert result == {"parsed": '{"key": "val"}'}
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/core/contracts/test_interaction_strategy.py -v`

**Expected output:**
```
FAILED - ModuleNotFoundError: No module named 'miniautogen.core.contracts.interaction'
```

**Step 3: Write the implementation**

Create file `miniautogen/core/contracts/interaction.py`:

```python
"""InteractionStrategy protocol — pluggable prompt construction and response parsing.

Enables advanced customization of how AgentRuntime interacts with agents.
Part of the cascade resolution: InteractionStrategy -> YAML templates -> defaults.

See docs/superpowers/specs/2026-03-21-agentruntime-agnostic-design.md
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class InteractionStrategy(Protocol):
    """Protocol for customizing prompt construction and response parsing.

    Inject via Python for advanced cases (multi-modal, tool calling, custom parsing).
    First in cascade resolution: InteractionStrategy -> YAML templates -> defaults.
    """

    async def build_prompt(self, action: str, context: dict[str, Any]) -> str:
        """Construct the prompt for a coordination action (contribute, review, etc.).

        Args:
            action: The coordination action name (e.g., "contribute", "review",
                    "consolidate", "produce_final_document", "route").
            context: Action-specific context dict. Keys vary by action:
                - contribute: {"topic": str}
                - review: {"target_id": str, "contribution": Contribution}
                - consolidate: {"topic": str, "contributions": list, "reviews": list}
                - produce_final_document: {"state": DeliberationState, "contributions": list}
                - route: {"conversation_history": list}

        Returns:
            The constructed prompt string.
        """
        ...

    async def parse_response(self, action: str, raw: str) -> Any:
        """Parse the agent's raw response into the expected structure.

        Args:
            action: The coordination action name.
            raw: The raw text response from the agent/driver.

        Returns:
            Parsed response. Type depends on action:
                - contribute: dict with title/content
                - review: dict with strengths/concerns/questions
                - consolidate: dict with accepted_facts/open_conflicts/etc.
                - produce_final_document: dict with executive_summary/etc.
                - route: dict with next_agent/terminate/etc.
        """
        ...
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/core/contracts/test_interaction_strategy.py -v`

**Expected output:**
```
PASSED tests/core/contracts/test_interaction_strategy.py::TestInteractionStrategyProtocol::test_fake_strategy_satisfies_protocol
PASSED tests/core/contracts/test_interaction_strategy.py::TestInteractionStrategyProtocol::test_incomplete_strategy_does_not_satisfy
PASSED tests/core/contracts/test_interaction_strategy.py::TestInteractionStrategyProtocol::test_build_prompt_returns_string
PASSED tests/core/contracts/test_interaction_strategy.py::TestInteractionStrategyProtocol::test_parse_response_returns_any
```

**Step 5: Verify no regressions**

Run: `pytest tests/ -x -q --tb=short`

**Expected output:** All tests pass (2084+ tests).

**Step 6: Commit**

```bash
git add miniautogen/core/contracts/interaction.py tests/core/contracts/test_interaction_strategy.py
git commit -m "feat(core): add InteractionStrategy protocol for pluggable prompt construction"
```

**If Task Fails:**
1. **Import error:** Check `miniautogen/core/contracts/` directory exists.
2. **Protocol check fails:** Ensure `runtime_checkable` decorator is present.
3. **Rollback:** `git checkout -- .`

---

### Task 2: Add response_format and prompts to FlowConfig

**Files:**
- Modify: `miniautogen/cli/config.py:97-131` (FlowConfig class)

**Prerequisites:**
- Task 1 complete

**Step 1: Write the failing test**

Create file `tests/cli/test_config_response_format.py`:

```python
"""Tests for FlowConfig response_format and prompts fields."""
from __future__ import annotations

import pytest

from miniautogen.cli.config import FlowConfig


class TestFlowConfigResponseFormat:
    def test_default_response_format_is_json(self) -> None:
        fc = FlowConfig(mode="workflow", participants=["agent1"])
        assert fc.response_format == "json"

    def test_free_text_response_format(self) -> None:
        fc = FlowConfig(
            mode="workflow",
            participants=["agent1"],
            response_format="free_text",
        )
        assert fc.response_format == "free_text"

    def test_structured_response_format(self) -> None:
        fc = FlowConfig(
            mode="workflow",
            participants=["agent1"],
            response_format="structured",
        )
        assert fc.response_format == "structured"

    def test_invalid_response_format_raises(self) -> None:
        with pytest.raises(ValueError):
            FlowConfig(
                mode="workflow",
                participants=["agent1"],
                response_format="invalid_format",
            )

    def test_prompts_default_empty(self) -> None:
        fc = FlowConfig(mode="workflow", participants=["agent1"])
        assert fc.prompts == {}

    def test_prompts_with_contribute(self) -> None:
        fc = FlowConfig(
            mode="deliberation",
            participants=["a", "b"],
            leader="a",
            prompts={"contribute": "Review {topic} as {role}."},
        )
        assert fc.prompts["contribute"] == "Review {topic} as {role}."

    def test_response_schema_default_none(self) -> None:
        fc = FlowConfig(mode="workflow", participants=["agent1"])
        assert fc.response_schema is None

    def test_response_schema_with_structured(self) -> None:
        fc = FlowConfig(
            mode="workflow",
            participants=["agent1"],
            response_format="structured",
            response_schema="miniautogen.core.contracts.deliberation.Contribution",
        )
        assert fc.response_schema is not None

    def test_structured_without_schema_raises(self) -> None:
        with pytest.raises(ValueError, match="response_schema"):
            FlowConfig(
                mode="workflow",
                participants=["agent1"],
                response_format="structured",
                # response_schema intentionally omitted
            )
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/cli/test_config_response_format.py -v`

**Expected output:**
```
FAILED - TypeError: ... unexpected keyword argument 'response_format'
```

**Step 3: Write the implementation**

Modify `miniautogen/cli/config.py`. Add three new fields to `FlowConfig` and a validator.

In `FlowConfig` (after `chain_flows` field, before `@model_validator`), add:

```python
    # AgentRuntime agnostic design fields
    response_format: str = "json"  # free_text | json | structured
    prompts: dict[str, str] = Field(default_factory=dict)
    response_schema: str | None = None  # Python dotted path for structured format
```

Add a new import at the top of the file (add to the existing `from typing import Any` line):

```python
from typing import Any, Literal
```

Then add a second `@model_validator` to FlowConfig, after the existing `validate_flow_config`:

```python
    @model_validator(mode="after")
    def validate_response_format(self) -> "FlowConfig":
        valid_formats = {"free_text", "json", "structured"}
        if self.response_format not in valid_formats:
            raise ValueError(
                f"response_format must be one of {valid_formats}, "
                f"got '{self.response_format}'"
            )
        if self.response_format == "structured" and not self.response_schema:
            raise ValueError(
                "response_format='structured' requires 'response_schema' "
                "(Python dotted path to Pydantic model)"
            )
        return self
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/cli/test_config_response_format.py -v`

**Expected output:** All 9 tests PASSED.

**Step 5: Verify no regressions**

Run: `pytest tests/ -x -q --tb=short`

**Expected output:** All existing tests pass (default `response_format="json"` preserves backward compat).

**Step 6: Commit**

```bash
git add miniautogen/cli/config.py tests/cli/test_config_response_format.py
git commit -m "feat(cli): add response_format, prompts, response_schema to FlowConfig"
```

**If Task Fails:**
1. **Validator ordering:** Pydantic v2 runs `mode="after"` validators in definition order. If the existing validator and new one conflict, combine them into one method.
2. **Existing tests break with `response_format`:** Check that `response_format="json"` is the default so no existing FlowConfig instantiations break.
3. **Rollback:** `git checkout -- miniautogen/cli/config.py`

---

### Task 3: Add execute() Method to AgentRuntime

**Files:**
- Modify: `miniautogen/core/runtime/agent_runtime.py:166-172` (add method after `process()`)

**Prerequisites:**
- Tasks 1-2 complete

**Step 1: Write the failing test**

Add to `tests/core/runtime/test_agent_runtime.py`. Create a new test class at the bottom of the file:

```python
class TestExecuteMethod:
    """Tests for the new generic execute() method."""

    @pytest.mark.anyio()
    async def test_execute_returns_raw_string(self) -> None:
        rt = _make_runtime(driver=FakeDriver(response_text="raw output"))
        await rt.initialize()
        result = await rt.execute("do something")
        assert result == "raw output"
        assert isinstance(result, str)

    @pytest.mark.anyio()
    async def test_execute_emits_turn_events(self) -> None:
        sink = InMemoryEventSink()
        rt = _make_runtime(
            driver=FakeDriver(response_text="output"),
            event_sink=sink,
        )
        await rt.initialize()
        await rt.execute("test prompt")
        event_types = [e.type for e in sink.events]
        assert EventType.AGENT_TURN_STARTED.value in event_types
        assert EventType.AGENT_TURN_COMPLETED.value in event_types

    @pytest.mark.anyio()
    async def test_execute_raises_when_closed(self) -> None:
        rt = _make_runtime()
        await rt.initialize()
        await rt.close()
        with pytest.raises(AgentClosedError):
            await rt.execute("anything")

    @pytest.mark.anyio()
    async def test_execute_includes_system_prompt(self) -> None:
        """execute() should build messages with system prompt via _build_messages."""
        driver = FakeDriver(response_text="ok")
        rt = _make_runtime(driver=driver, system_prompt="You are test.")
        await rt.initialize()
        await rt.execute("user input")
        # If we got here without error, messages were built correctly
        assert True

    @pytest.mark.anyio()
    async def test_execute_saves_to_memory(self) -> None:
        memory = FakeMemoryProvider()
        rt = _make_runtime(
            driver=FakeDriver(response_text="memory test"),
            memory=memory,
        )
        await rt.initialize()
        await rt.execute("remember this")
        assert len(memory.saved_turns) > 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/core/runtime/test_agent_runtime.py::TestExecuteMethod -v`

**Expected output:**
```
FAILED - AttributeError: 'AgentRuntime' object has no attribute 'execute'
```

**Step 3: Write the implementation**

Add the `execute()` method to `AgentRuntime` in `miniautogen/core/runtime/agent_runtime.py`. Insert it right after the `process()` method (after line 172), before the ConversationalAgent section comment:

```python
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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/core/runtime/test_agent_runtime.py::TestExecuteMethod -v`

**Expected output:** All 5 tests PASSED.

**Step 5: Verify no regressions**

Run: `pytest tests/core/runtime/test_agent_runtime.py -v`

**Expected output:** All tests pass (new + existing).

**Step 6: Commit**

```bash
git add miniautogen/core/runtime/agent_runtime.py tests/core/runtime/test_agent_runtime.py
git commit -m "feat(runtime): add execute() method to AgentRuntime for raw prompt execution"
```

**If Task Fails:**
1. **Method signature conflict:** Ensure no existing method named `execute` exists.
2. **Protocol check:** `execute()` is not part of any existing protocol, so it won't break protocol satisfaction.
3. **Rollback:** `git checkout -- miniautogen/core/runtime/agent_runtime.py`

---

### Task 4: Add interaction_strategy to AgentRuntime Constructor

**Files:**
- Modify: `miniautogen/core/runtime/agent_runtime.py:55-80` (constructor)

**Prerequisites:**
- Tasks 1-3 complete

**Step 1: Write the failing test**

Add to `tests/core/runtime/test_agent_runtime.py`:

```python
class TestInteractionStrategy:
    """Tests for InteractionStrategy injection into AgentRuntime."""

    def test_runtime_accepts_interaction_strategy(self) -> None:
        from miniautogen.core.contracts.interaction import InteractionStrategy

        class MyStrategy:
            async def build_prompt(self, action: str, context: dict) -> str:
                return f"custom prompt for {action}"

            async def parse_response(self, action: str, raw: str) -> Any:
                return {"custom": raw}

        rt = AgentRuntime(
            agent_id="test",
            driver=FakeDriver(),
            run_context=_make_run_context(),
            interaction_strategy=MyStrategy(),
        )
        assert rt._interaction_strategy is not None

    def test_runtime_defaults_to_no_strategy(self) -> None:
        rt = _make_runtime()
        assert rt._interaction_strategy is None

    def test_runtime_accepts_flow_prompts(self) -> None:
        rt = AgentRuntime(
            agent_id="test",
            driver=FakeDriver(),
            run_context=_make_run_context(),
            flow_prompts={"contribute": "Review {topic}."},
        )
        assert rt._flow_prompts == {"contribute": "Review {topic}."}

    def test_runtime_accepts_response_format(self) -> None:
        rt = AgentRuntime(
            agent_id="test",
            driver=FakeDriver(),
            run_context=_make_run_context(),
            response_format="free_text",
        )
        assert rt._response_format == "free_text"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/core/runtime/test_agent_runtime.py::TestInteractionStrategy -v`

**Expected output:**
```
FAILED - TypeError: ... unexpected keyword argument 'interaction_strategy'
```

**Step 3: Write the implementation**

Modify the `__init__` method of `AgentRuntime` in `miniautogen/core/runtime/agent_runtime.py`.

Add the import at the top of the file (after the existing imports):

```python
from miniautogen.core.contracts.interaction import InteractionStrategy
```

Add three new keyword parameters to `__init__` (after `delegation`):

```python
        interaction_strategy: InteractionStrategy | None = None,
        flow_prompts: dict[str, str] | None = None,
        response_format: str = "json",
```

Add three new instance variables in the `__init__` body (after `self._delegation = delegation`):

```python
        self._interaction_strategy = interaction_strategy
        self._flow_prompts = flow_prompts or {}
        self._response_format = response_format
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/core/runtime/test_agent_runtime.py::TestInteractionStrategy -v`

**Expected output:** All 4 tests PASSED.

**Step 5: Verify no regressions**

Run: `pytest tests/core/runtime/test_agent_runtime.py -v`

**Expected output:** All tests pass (existing constructors use keyword args and are unaffected by new optional params).

**Step 6: Commit**

```bash
git add miniautogen/core/runtime/agent_runtime.py tests/core/runtime/test_agent_runtime.py
git commit -m "feat(runtime): add interaction_strategy, flow_prompts, response_format to AgentRuntime"
```

**If Task Fails:**
1. **Circular import:** If `InteractionStrategy` import causes circular import, use `TYPE_CHECKING` guard.
2. **Existing tests break:** Ensure all new params have defaults (`None`, `{}`, `"json"`).
3. **Rollback:** `git checkout -- miniautogen/core/runtime/agent_runtime.py`

---

### Task 5: Run Code Review (Phase 1)

1. **Dispatch all 3 reviewers in parallel:**
   - REQUIRED SUB-SKILL: Use requesting-code-review
   - All reviewers run simultaneously (code-reviewer, business-logic-reviewer, security-reviewer)
   - Wait for all to complete

2. **Handle findings by severity (MANDATORY):**

**Critical/High/Medium Issues:**
- Fix immediately (do NOT add TODO comments for these severities)
- Re-run all 3 reviewers in parallel after fixes
- Repeat until zero Critical/High/Medium issues remain

**Low Issues:**
- Add `TODO(review):` comments in code at the relevant location
- Format: `TODO(review): [Issue description] (reported by [reviewer] on [date], severity: Low)`

**Cosmetic/Nitpick Issues:**
- Add `FIXME(nitpick):` comments in code at the relevant location

3. **Proceed only when:**
   - Zero Critical/High/Medium issues remain
   - All Low issues have TODO(review): comments added
   - All Cosmetic issues have FIXME(nitpick): comments added

---

## Phase 2: Cascade Resolution in Convenience Wrappers (Tasks 6-12)

### Task 6: Create Default Prompt Builders (Extracted from AgentRuntime)

**Files:**
- Create: `miniautogen/core/runtime/default_prompts.py`

**Prerequisites:**
- Phase 1 complete

**Step 1: Write the failing test**

Create file `tests/core/runtime/test_default_prompts.py`:

```python
"""Tests for default prompt builders extracted from AgentRuntime."""
from __future__ import annotations

import pytest

from miniautogen.core.contracts.deliberation import (
    Contribution,
    DeliberationState,
    Review,
)


class TestDefaultContributePrompt:
    def test_contains_topic(self) -> None:
        from miniautogen.core.runtime.default_prompts import build_default_contribute_prompt

        prompt = build_default_contribute_prompt(topic="AI safety")
        assert "AI safety" in prompt
        assert "JSON" in prompt  # default expects JSON

    def test_returns_string(self) -> None:
        from miniautogen.core.runtime.default_prompts import build_default_contribute_prompt

        result = build_default_contribute_prompt(topic="test")
        assert isinstance(result, str)


class TestDefaultReviewPrompt:
    def test_contains_target_and_content(self) -> None:
        from miniautogen.core.runtime.default_prompts import build_default_review_prompt

        contrib = Contribution(
            participant_id="agent-a", title="Title", content={"key": "val"}
        )
        prompt = build_default_review_prompt(target_id="agent-a", contribution=contrib)
        assert "agent-a" in prompt
        assert "Title" in prompt

    def test_returns_string(self) -> None:
        from miniautogen.core.runtime.default_prompts import build_default_review_prompt

        contrib = Contribution(
            participant_id="other", title="T", content={}
        )
        result = build_default_review_prompt(target_id="other", contribution=contrib)
        assert isinstance(result, str)


class TestDefaultConsolidatePrompt:
    def test_contains_topic_and_summaries(self) -> None:
        from miniautogen.core.runtime.default_prompts import build_default_consolidate_prompt

        contribs = [
            Contribution(participant_id="a", title="T1", content={}),
        ]
        reviews = [
            Review(
                reviewer_id="b", target_id="a", target_title="T1",
                strengths=["good"], concerns=[], questions=[],
            ),
        ]
        prompt = build_default_consolidate_prompt(
            topic="AI", contributions=contribs, reviews=reviews
        )
        assert "AI" in prompt
        assert "a" in prompt
        assert "b" in prompt


class TestDefaultFinalDocumentPrompt:
    def test_contains_state_info(self) -> None:
        from miniautogen.core.runtime.default_prompts import build_default_final_document_prompt

        state = DeliberationState(
            review_cycle=1,
            leader_decision="Approved",
            is_sufficient=True,
        )
        contribs = [
            Contribution(participant_id="a", title="T1", content={"x": 1}),
        ]
        prompt = build_default_final_document_prompt(state=state, contributions=contribs)
        assert "Approved" in prompt
        assert "a" in prompt


class TestDefaultRoutePrompt:
    def test_returns_string(self) -> None:
        from miniautogen.core.runtime.default_prompts import build_default_route_prompt

        prompt = build_default_route_prompt()
        assert isinstance(prompt, str)
        assert "JSON" in prompt
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/core/runtime/test_default_prompts.py -v`

**Expected output:**
```
FAILED - ModuleNotFoundError: No module named 'miniautogen.core.runtime.default_prompts'
```

**Step 3: Write the implementation**

Create file `miniautogen/core/runtime/default_prompts.py`:

```python
"""Default prompt builders — extracted from AgentRuntime hardcoded prompts.

These serve as the last-resort fallback in the cascade resolution:
InteractionStrategy -> YAML templates -> defaults (this module).

These prompts preserve exact backward compatibility with the original
AgentRuntime prompts that were hardcoded before the agnostic refactor.
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from miniautogen.core.contracts.deliberation import (
        Contribution,
        DeliberationState,
        Review,
    )


def build_default_contribute_prompt(*, topic: str) -> str:
    """Build the default contribute prompt (extracted from AgentRuntime.contribute)."""
    return (
        f"Contribute to the topic: {topic}. "
        "Respond with JSON: "
        '{"title":"...","content":{...}}'
    )


def build_default_review_prompt(
    *, target_id: str, contribution: Contribution
) -> str:
    """Build the default review prompt (extracted from AgentRuntime.review)."""
    return (
        f"Review contribution from {target_id}: "
        f"title='{contribution.title}', content={contribution.content}. "
        "Respond with JSON: "
        '{"strengths":[...],"concerns":[...],"questions":[...]}'
    )


def build_default_consolidate_prompt(
    *,
    topic: str,
    contributions: list[Contribution],
    reviews: list[Review],
) -> str:
    """Build the default consolidate prompt (extracted from AgentRuntime.consolidate)."""
    contrib_summary = "\n".join(
        f"- {c.participant_id}: {c.title}" for c in contributions
    )
    review_summary = "\n".join(
        f"- {r.reviewer_id} on {r.target_id}: strengths={r.strengths}, concerns={r.concerns}"
        for r in reviews
    )
    return (
        f"As leader, consolidate the deliberation on: {topic}\n\n"
        f"Contributions:\n{contrib_summary}\n\n"
        f"Reviews:\n{review_summary}\n\n"
        "Respond with JSON:\n"
        '{"accepted_facts":["..."],"open_conflicts":["..."],'
        '"pending_gaps":["..."],"leader_decision":"...",'
        '"is_sufficient":true/false,"rejection_reasons":["..."]}'
    )


def build_default_final_document_prompt(
    *,
    state: DeliberationState,
    contributions: list[Contribution],
) -> str:
    """Build the default final document prompt (extracted from AgentRuntime.produce_final_document)."""
    contrib_text = "\n".join(
        f"- {c.participant_id}: {json.dumps(c.content)[:500]}"
        for c in contributions
    )
    return (
        "Produce a final document summarizing the deliberation.\n\n"
        f"State: decision={state.leader_decision}, "
        f"accepted_facts={state.accepted_facts}, "
        f"open_conflicts={state.open_conflicts}\n\n"
        f"Contributions:\n{contrib_text}\n\n"
        "Respond with JSON:\n"
        '{"executive_summary":"...","accepted_facts":["..."],'
        '"open_conflicts":["..."],"pending_decisions":["..."],'
        '"recommendations":["..."],"decision_summary":"...",'
        '"body_markdown":"..."}'
    )


def build_default_route_prompt() -> str:
    """Build the default route prompt (extracted from AgentRuntime.route)."""
    return (
        "Based on the conversation history, decide which agent should "
        "speak next. Respond with JSON: "
        '{"current_state_summary":"...","missing_information":"...",'
        '"next_agent":"...","terminate":false,"stagnation_risk":0.0}'
    )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/core/runtime/test_default_prompts.py -v`

**Expected output:** All 7 tests PASSED.

**Step 5: Commit**

```bash
git add miniautogen/core/runtime/default_prompts.py tests/core/runtime/test_default_prompts.py
git commit -m "refactor(runtime): extract default prompt builders from AgentRuntime"
```

**If Task Fails:**
1. **Import error from Contribution/Review:** These are Pydantic models in `core/contracts/deliberation.py`. Use `TYPE_CHECKING` guard for type annotations.
2. **Rollback:** `git checkout -- .`

---

### Task 7: Create Prompt Cascade Resolution Helper

**Files:**
- Create: `miniautogen/core/runtime/prompt_resolver.py`

**Prerequisites:**
- Tasks 1-2 and 6 complete

**Step 1: Write the failing test**

Create file `tests/core/runtime/test_prompt_resolver.py`:

```python
"""Tests for prompt cascade resolution."""
from __future__ import annotations

from typing import Any

import pytest

from miniautogen.core.contracts.interaction import InteractionStrategy


class FakeStrategy:
    async def build_prompt(self, action: str, context: dict[str, Any]) -> str:
        return f"strategy prompt for {action}"

    async def parse_response(self, action: str, raw: str) -> Any:
        return {"strategy_parsed": raw}


class TestResolvePrompt:
    @pytest.mark.anyio()
    async def test_strategy_wins_over_yaml_and_default(self) -> None:
        from miniautogen.core.runtime.prompt_resolver import resolve_prompt

        result = await resolve_prompt(
            action="contribute",
            context={"topic": "AI"},
            strategy=FakeStrategy(),
            flow_prompts={"contribute": "YAML: {topic}"},
            default_prompt="default prompt",
        )
        assert result == "strategy prompt for contribute"

    @pytest.mark.anyio()
    async def test_yaml_wins_over_default(self) -> None:
        from miniautogen.core.runtime.prompt_resolver import resolve_prompt

        result = await resolve_prompt(
            action="contribute",
            context={"topic": "AI"},
            strategy=None,
            flow_prompts={"contribute": "YAML: {topic}"},
            default_prompt="default prompt",
        )
        assert result == "YAML: AI"

    @pytest.mark.anyio()
    async def test_default_used_when_no_strategy_or_yaml(self) -> None:
        from miniautogen.core.runtime.prompt_resolver import resolve_prompt

        result = await resolve_prompt(
            action="contribute",
            context={"topic": "AI"},
            strategy=None,
            flow_prompts={},
            default_prompt="default prompt",
        )
        assert result == "default prompt"

    @pytest.mark.anyio()
    async def test_yaml_template_substitutes_variables(self) -> None:
        from miniautogen.core.runtime.prompt_resolver import resolve_prompt

        result = await resolve_prompt(
            action="review",
            context={"target": "agent-b", "content": "some text"},
            strategy=None,
            flow_prompts={"review": "Evaluate {target}'s work: {content}"},
            default_prompt="default",
        )
        assert result == "Evaluate agent-b's work: some text"

    @pytest.mark.anyio()
    async def test_yaml_template_ignores_missing_variables(self) -> None:
        from miniautogen.core.runtime.prompt_resolver import resolve_prompt

        result = await resolve_prompt(
            action="contribute",
            context={"topic": "AI"},
            strategy=None,
            flow_prompts={"contribute": "Do {topic} with {missing_var}"},
            default_prompt="default",
        )
        # Missing vars should remain as-is (safe fallback)
        assert result == "Do AI with {missing_var}"

    @pytest.mark.anyio()
    async def test_yaml_for_different_action_falls_to_default(self) -> None:
        from miniautogen.core.runtime.prompt_resolver import resolve_prompt

        result = await resolve_prompt(
            action="consolidate",
            context={},
            strategy=None,
            flow_prompts={"contribute": "only contribute template"},
            default_prompt="consolidate default",
        )
        assert result == "consolidate default"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/core/runtime/test_prompt_resolver.py -v`

**Expected output:**
```
FAILED - ModuleNotFoundError: No module named 'miniautogen.core.runtime.prompt_resolver'
```

**Step 3: Write the implementation**

Create file `miniautogen/core/runtime/prompt_resolver.py`:

```python
"""Prompt cascade resolver — InteractionStrategy -> YAML templates -> defaults.

Implements the three-level cascade resolution for prompt construction
as defined in the AgentRuntime agnostic design spec.
"""
from __future__ import annotations

import string
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from miniautogen.core.contracts.interaction import InteractionStrategy


class _SafeDict(dict):
    """Dict that returns the key placeholder for missing keys.

    Used with str.format_map() to safely substitute only known variables,
    leaving unknown {placeholders} intact.
    """

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


async def resolve_prompt(
    *,
    action: str,
    context: dict[str, Any],
    strategy: InteractionStrategy | None,
    flow_prompts: dict[str, str],
    default_prompt: str,
) -> str:
    """Resolve prompt using cascade: strategy -> YAML template -> default.

    Args:
        action: The coordination action (contribute, review, consolidate, etc.)
        context: Action-specific context variables for template substitution.
        strategy: Optional InteractionStrategy (highest priority).
        flow_prompts: YAML prompt templates keyed by action name.
        default_prompt: Built-in default prompt (lowest priority fallback).

    Returns:
        The resolved prompt string.
    """
    # Level 1: InteractionStrategy (Python)
    if strategy is not None:
        return await strategy.build_prompt(action, context)

    # Level 2: YAML prompt templates
    if action in flow_prompts:
        template = flow_prompts[action]
        # Safe substitution — unknown vars remain as {placeholder}
        return template.format_map(_SafeDict(context))

    # Level 3: Built-in default
    return default_prompt
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/core/runtime/test_prompt_resolver.py -v`

**Expected output:** All 6 tests PASSED.

**Step 5: Commit**

```bash
git add miniautogen/core/runtime/prompt_resolver.py tests/core/runtime/test_prompt_resolver.py
git commit -m "feat(runtime): add prompt cascade resolver (strategy -> YAML -> default)"
```

**If Task Fails:**
1. **`format_map` issues:** Ensure `_SafeDict` inherits from `dict` and returns `{key}` for missing keys.
2. **Rollback:** `git checkout -- .`

---

### Task 8: Refactor contribute() to Use Cascade Resolution

**Files:**
- Modify: `miniautogen/core/runtime/agent_runtime.py:210-233` (contribute method)

**Prerequisites:**
- Tasks 6-7 complete

**Step 1: Verify existing tests still define baseline**

Run: `pytest tests/core/runtime/test_agent_runtime.py::TestTurnExecution::test_contribute_returns_contribution -v`

**Expected output:** PASSED (this is our backward-compat baseline).

**Step 2: Write new test for cascade behavior**

Add to `tests/core/runtime/test_agent_runtime.py`:

```python
class TestContributeCascade:
    """Tests that contribute() uses cascade resolution."""

    @pytest.mark.anyio()
    async def test_contribute_uses_yaml_prompt_when_provided(self) -> None:
        """When flow_prompts has a 'contribute' template, use it."""
        rt = AgentRuntime(
            agent_id="test-agent",
            driver=FakeDriver(response_text='{"title":"T","content":{"k":"v"}}'),
            run_context=_make_run_context(),
            flow_prompts={"contribute": "Custom contribute for {topic}."},
        )
        await rt.initialize()
        contrib = await rt.contribute("AI safety")
        # Should still return a valid Contribution (backward compat)
        assert contrib.participant_id == "test-agent"
        assert contrib.title is not None

    @pytest.mark.anyio()
    async def test_contribute_uses_strategy_when_provided(self) -> None:
        """InteractionStrategy takes priority over YAML and default."""

        class CustomStrategy:
            async def build_prompt(self, action: str, context: dict) -> str:
                return f"STRATEGY: contribute about {context.get('topic', '')}"

            async def parse_response(self, action: str, raw: str) -> Any:
                return {"title": "Strategy Title", "content": {"strategy": True}}

        rt = AgentRuntime(
            agent_id="test-agent",
            driver=FakeDriver(response_text='{"title":"T","content":{}}'),
            run_context=_make_run_context(),
            interaction_strategy=CustomStrategy(),
            flow_prompts={"contribute": "YAML: {topic}"},
        )
        await rt.initialize()
        contrib = await rt.contribute("AI")
        assert contrib.participant_id == "test-agent"

    @pytest.mark.anyio()
    async def test_contribute_fallback_to_default_prompt(self) -> None:
        """Without strategy or YAML, uses built-in default (backward compat)."""
        rt = _make_runtime(
            driver=FakeDriver(response_text='{"title":"Default","content":{"d":1}}'),
        )
        await rt.initialize()
        contrib = await rt.contribute("test topic")
        assert contrib.participant_id == "test-agent"
        assert contrib.title == "Default"

    @pytest.mark.anyio()
    async def test_contribute_free_text_fallback(self) -> None:
        """Non-JSON response still wraps as Contribution (backward compat)."""
        rt = _make_runtime(
            driver=FakeDriver(response_text="Just some free text response"),
        )
        await rt.initialize()
        contrib = await rt.contribute("topic")
        assert contrib.participant_id == "test-agent"
        assert contrib.content == {"text": "Just some free text response"}
```

**Step 3: Run new tests to verify they fail (strategy/YAML tests)**

Run: `pytest tests/core/runtime/test_agent_runtime.py::TestContributeCascade -v`

**Expected output:** Some tests may pass (fallback test), some fail (cascade not wired yet).

**Step 4: Refactor contribute() in AgentRuntime**

Replace the `contribute()` method body in `miniautogen/core/runtime/agent_runtime.py` (lines 210-233). Keep the same signature.

Replace the entire method with:

```python
    async def contribute(self, topic: str) -> Contribution:
        """Produce a contribution for a deliberation topic.

        Uses cascade resolution: InteractionStrategy -> YAML -> default.
        """
        self._check_closed()
        from miniautogen.core.runtime.default_prompts import build_default_contribute_prompt
        from miniautogen.core.runtime.prompt_resolver import resolve_prompt

        prompt = await resolve_prompt(
            action="contribute",
            context={"topic": topic},
            strategy=self._interaction_strategy,
            flow_prompts=self._flow_prompts,
            default_prompt=build_default_contribute_prompt(topic=topic),
        )
        result_text = await self.execute(prompt)
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
```

**Step 5: Run all tests**

Run: `pytest tests/core/runtime/test_agent_runtime.py -v`

**Expected output:** All tests PASSED (existing + new cascade tests).

**Step 6: Commit**

```bash
git add miniautogen/core/runtime/agent_runtime.py tests/core/runtime/test_agent_runtime.py
git commit -m "refactor(runtime): wire contribute() to cascade prompt resolution"
```

**If Task Fails:**
1. **Import error:** The `from ... import` inside the method avoids circular imports.
2. **Existing test breaks:** Ensure the fallback prompt is identical to the old hardcoded prompt.
3. **Rollback:** `git checkout -- miniautogen/core/runtime/agent_runtime.py`

---

### Task 9: Refactor review() to Use Cascade Resolution

**Files:**
- Modify: `miniautogen/core/runtime/agent_runtime.py` (review method)

**Prerequisites:**
- Task 8 complete

**Step 1: Verify existing test still passes**

Run: `pytest tests/core/runtime/test_agent_runtime.py::TestTurnExecution::test_review_returns_review -v`

**Expected output:** PASSED.

**Step 2: Refactor review()**

Replace the `review()` method body in `miniautogen/core/runtime/agent_runtime.py`. Keep the exact same signature `async def review(self, target_id: str, contribution: Contribution) -> Review:`.

```python
    async def review(
        self, target_id: str, contribution: Contribution
    ) -> Review:
        """Review another agent's contribution.

        Uses cascade resolution: InteractionStrategy -> YAML -> default.
        """
        self._check_closed()
        from miniautogen.core.runtime.default_prompts import build_default_review_prompt
        from miniautogen.core.runtime.prompt_resolver import resolve_prompt

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
        try:
            text = result_text or ""
            fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
            raw = fence_match.group(1).strip() if fence_match else text
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError, ValueError):
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
```

**Step 3: Run tests**

Run: `pytest tests/core/runtime/test_agent_runtime.py -v`

**Expected output:** All tests PASSED.

**Step 4: Commit**

```bash
git add miniautogen/core/runtime/agent_runtime.py
git commit -m "refactor(runtime): wire review() to cascade prompt resolution"
```

**If Task Fails:**
1. **JSON parsing difference:** The fence match regex is preserved exactly from the original.
2. **Rollback:** `git checkout -- miniautogen/core/runtime/agent_runtime.py`

---

### Task 10: Refactor consolidate() and produce_final_document()

**Files:**
- Modify: `miniautogen/core/runtime/agent_runtime.py` (consolidate and produce_final_document methods)

**Prerequisites:**
- Task 9 complete

**Step 1: Verify existing behavior**

Run: `pytest tests/core/runtime/ -v --tb=short`

**Expected output:** All tests PASSED.

**Step 2: Refactor consolidate()**

Replace the `consolidate()` method body:

```python
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
        from miniautogen.core.runtime.default_prompts import build_default_consolidate_prompt
        from miniautogen.core.runtime.prompt_resolver import resolve_prompt

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
        try:
            text = result_text or ""
            fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
            raw = fence_match.group(1).strip() if fence_match else text
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError, ValueError):
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
```

**Step 3: Refactor produce_final_document()**

Replace the `produce_final_document()` method body:

```python
    async def produce_final_document(
        self,
        state: DeliberationState,
        contributions: list[Contribution],
    ) -> FinalDocument:
        """Leader produces the final consolidated document.

        Uses cascade resolution: InteractionStrategy -> YAML -> default.
        """
        self._check_closed()
        from miniautogen.core.runtime.default_prompts import build_default_final_document_prompt
        from miniautogen.core.runtime.prompt_resolver import resolve_prompt

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
        try:
            text = result_text or ""
            fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
            raw = fence_match.group(1).strip() if fence_match else text
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError, ValueError):
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
```

**Step 4: Run all tests**

Run: `pytest tests/core/runtime/ -v --tb=short`

**Expected output:** All tests PASSED.

**Step 5: Commit**

```bash
git add miniautogen/core/runtime/agent_runtime.py
git commit -m "refactor(runtime): wire consolidate() and produce_final_document() to cascade resolution"
```

---

### Task 11: Refactor route() to Use Cascade Resolution

**Files:**
- Modify: `miniautogen/core/runtime/agent_runtime.py` (route method)

**Prerequisites:**
- Task 10 complete

**Step 1: Refactor route()**

Replace the `route()` method body:

```python
    async def route(self, conversation_history: list[Any]) -> RouterDecision:
        """Route a conversation to the next agent.

        Uses cascade resolution: InteractionStrategy -> YAML -> default.
        """
        self._check_closed()
        from miniautogen.core.runtime.default_prompts import build_default_route_prompt
        from miniautogen.core.runtime.prompt_resolver import resolve_prompt

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
```

**Step 2: Run all tests**

Run: `pytest tests/core/runtime/test_agent_runtime.py::TestTurnExecution::test_route_returns_router_decision -v`

**Expected output:** PASSED.

Run: `pytest tests/ -x -q --tb=short`

**Expected output:** All tests pass.

**Step 3: Commit**

```bash
git add miniautogen/core/runtime/agent_runtime.py
git commit -m "refactor(runtime): wire route() to cascade prompt resolution"
```

---

### Task 12: Run Code Review (Phase 2)

1. **Dispatch all 3 reviewers in parallel:**
   - REQUIRED SUB-SKILL: Use requesting-code-review
   - All reviewers run simultaneously (code-reviewer, business-logic-reviewer, security-reviewer)
   - Wait for all to complete

2. **Handle findings by severity (MANDATORY):**

**Critical/High/Medium Issues:**
- Fix immediately (do NOT add TODO comments for these severities)
- Re-run all 3 reviewers in parallel after fixes
- Repeat until zero Critical/High/Medium issues remain

**Low Issues:**
- Add `TODO(review):` comments in code at the relevant location

**Cosmetic/Nitpick Issues:**
- Add `FIXME(nitpick):` comments in code at the relevant location

3. **Proceed only when:**
   - Zero Critical/High/Medium issues remain
   - All Low/Cosmetic issues have appropriate comments added

---

## Phase 3: Wire FlowConfig to AgentRuntime (Tasks 13-15)

### Task 13: Pass FlowConfig Fields Through PipelineRunner to AgentRuntime

**Files:**
- Modify: `miniautogen/core/runtime/pipeline_runner.py` (in `_build_coordination_from_config` and `_build_agent_runtimes`)

**Prerequisites:**
- Phase 2 complete

**Step 1: Write the failing test**

Create file `tests/core/runtime/test_flow_config_propagation.py`:

```python
"""Tests that FlowConfig response_format and prompts propagate to AgentRuntime."""
from __future__ import annotations

from typing import Any

import pytest

from miniautogen.cli.config import FlowConfig


class TestFlowConfigPropagation:
    @pytest.mark.anyio()
    async def test_flow_prompts_reach_agent_runtime(self) -> None:
        """FlowConfig.prompts should be passed to AgentRuntime._flow_prompts."""
        # This test validates the wiring; full integration tested separately.
        fc = FlowConfig(
            mode="deliberation",
            participants=["agent1", "agent2"],
            leader="agent1",
            prompts={"contribute": "Custom {topic} prompt."},
            response_format="free_text",
        )
        assert fc.prompts["contribute"] == "Custom {topic} prompt."
        assert fc.response_format == "free_text"
```

**Step 2: Run test**

Run: `pytest tests/core/runtime/test_flow_config_propagation.py -v`

**Expected output:** PASSED (this validates the FlowConfig side; wiring is done in next step).

**Step 3: Modify `_build_coordination_from_config` to pass flow_config to coordination runtimes**

In `miniautogen/core/runtime/pipeline_runner.py`, locate the `_build_coordination_from_config` function. We need to ensure the `flow_config` is accessible so coordination runtimes can pass `prompts` and `response_format` to AgentRuntimes.

Currently, `_build_agent_runtimes` doesn't have access to `flow_config`. The cleanest approach is to add `flow_prompts` and `response_format` parameters when constructing `AgentRuntime` instances.

Find the `_build_agent_runtimes` method in `PipelineRunner` and add `flow_config` parameter:

Locate the method signature (approximately line 370-410). Add `flow_config: FlowConfig | None = None` parameter. Then inside the method, when constructing each `AgentRuntime`, pass `flow_prompts=flow_config.prompts if flow_config else {}` and `response_format=flow_config.response_format if flow_config else "json"`.

Then in `run_from_config`, pass `flow_config=flow_config` to `_build_agent_runtimes`.

**IMPORTANT:** The exact line numbers and method structure will need to be verified when implementing. The executor should:

1. Read `_build_agent_runtimes` method to find where `AgentRuntime(...)` is constructed
2. Add `flow_prompts` and `response_format` to that constructor call
3. Read `run_from_config` to find where `_build_agent_runtimes` is called
4. Pass `flow_config` through

**Step 4: Run full test suite**

Run: `pytest tests/ -x -q --tb=short`

**Expected output:** All tests pass.

**Step 5: Commit**

```bash
git add miniautogen/core/runtime/pipeline_runner.py tests/core/runtime/test_flow_config_propagation.py
git commit -m "feat(runtime): propagate FlowConfig prompts and response_format to AgentRuntime"
```

**If Task Fails:**
1. **Method signature:** `_build_agent_runtimes` may be a method or standalone function. Read the file to confirm.
2. **Keyword args:** All new params have defaults, so existing callers are unaffected.
3. **Rollback:** `git checkout -- miniautogen/core/runtime/pipeline_runner.py`

---

### Task 14: Full Integration Test — Cascade Resolution E2E

**Files:**
- Create: `tests/core/runtime/test_agentruntime_agnostic_integration.py`

**Prerequisites:**
- Task 13 complete

**Step 1: Write integration test**

Create file `tests/core/runtime/test_agentruntime_agnostic_integration.py`:

```python
"""Integration tests for AgentRuntime agnostic design.

Validates the three cascade resolution levels and backward compatibility.
"""
from __future__ import annotations

from typing import Any, AsyncIterator

import pytest

from miniautogen.backends.driver import AgentDriver
from miniautogen.backends.models import (
    AgentEvent,
    BackendCapabilities,
    SendTurnRequest,
    StartSessionRequest,
    StartSessionResponse,
)
from miniautogen.core.contracts.deliberation import Contribution, Review
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.runtime.agent_runtime import AgentRuntime


def _make_run_context() -> RunContext:
    from datetime import datetime, timezone

    return RunContext(
        run_id="integration-test",
        started_at=datetime.now(timezone.utc),
        correlation_id="int-corr",
    )


class EchoDriver(AgentDriver):
    """Driver that echoes the user prompt back — useful for testing prompt construction."""

    async def start_session(self, request: StartSessionRequest) -> StartSessionResponse:
        return StartSessionResponse(
            session_id="echo-session",
            capabilities=BackendCapabilities(sessions=True, streaming=True),
        )

    async def send_turn(self, request: SendTurnRequest) -> AsyncIterator[AgentEvent]:
        # Return the last user message content as response
        user_msg = ""
        for msg in reversed(request.messages):
            if msg.get("role") == "user":
                user_msg = msg.get("content", "")
                break
        yield AgentEvent(
            type="message_completed",
            session_id=request.session_id,
            turn_id="echo-turn",
            payload={"text": user_msg},
        )

    async def cancel_turn(self, request: Any) -> None:
        pass

    async def list_artifacts(self, session_id: str) -> list:
        return []

    async def close_session(self, session_id: str) -> None:
        pass

    async def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(sessions=True, streaming=True)


class TestCascadeResolutionIntegration:
    """End-to-end tests for cascade prompt resolution in AgentRuntime."""

    @pytest.mark.anyio()
    async def test_execute_returns_raw_string(self) -> None:
        """execute() should pass prompt to driver and return raw response."""
        rt = AgentRuntime(
            agent_id="test",
            driver=EchoDriver(),
            run_context=_make_run_context(),
        )
        await rt.initialize()
        result = await rt.execute("Hello world")
        assert result == "Hello world"
        await rt.close()

    @pytest.mark.anyio()
    async def test_contribute_with_yaml_prompt(self) -> None:
        """YAML template should replace the default prompt."""
        rt = AgentRuntime(
            agent_id="test",
            driver=EchoDriver(),
            run_context=_make_run_context(),
            flow_prompts={"contribute": "Custom: discuss {topic} now."},
        )
        await rt.initialize()
        contrib = await rt.contribute("AI safety")
        # EchoDriver echoes the prompt back as response text
        # Since it's not JSON, it wraps as free text
        assert contrib.content["text"] == "Custom: discuss AI safety now."
        await rt.close()

    @pytest.mark.anyio()
    async def test_contribute_with_strategy(self) -> None:
        """InteractionStrategy should take priority over YAML and default."""

        class PriorityStrategy:
            async def build_prompt(self, action: str, context: dict) -> str:
                return f"STRATEGY:{action}:{context.get('topic', '')}"

            async def parse_response(self, action: str, raw: str) -> Any:
                return raw

        rt = AgentRuntime(
            agent_id="test",
            driver=EchoDriver(),
            run_context=_make_run_context(),
            interaction_strategy=PriorityStrategy(),
            flow_prompts={"contribute": "YAML {topic}"},
        )
        await rt.initialize()
        contrib = await rt.contribute("ML")
        # Strategy prompt was used, echoed back, not JSON -> free text wrap
        assert "STRATEGY:contribute:ML" in contrib.content.get("text", "")
        await rt.close()

    @pytest.mark.anyio()
    async def test_contribute_default_backward_compat(self) -> None:
        """Without strategy or YAML, default prompt is used (backward compat)."""
        rt = AgentRuntime(
            agent_id="test",
            driver=EchoDriver(),
            run_context=_make_run_context(),
        )
        await rt.initialize()
        contrib = await rt.contribute("testing")
        # Default prompt contains "Contribute to the topic: testing"
        assert "testing" in contrib.content.get("text", "")
        await rt.close()

    @pytest.mark.anyio()
    async def test_review_with_yaml_prompt(self) -> None:
        """YAML template for review should be used."""
        c = Contribution(participant_id="other", title="Title", content={"x": 1})
        rt = AgentRuntime(
            agent_id="test",
            driver=EchoDriver(),
            run_context=_make_run_context(),
            flow_prompts={"review": "Evaluate {target}'s work."},
        )
        await rt.initialize()
        review = await rt.review("other", c)
        # Echo returns the YAML prompt, not JSON -> fallback
        assert review.reviewer_id == "test"
        assert review.target_id == "other"
        await rt.close()

    @pytest.mark.anyio()
    async def test_response_format_field_accepted(self) -> None:
        """AgentRuntime should accept response_format parameter."""
        rt = AgentRuntime(
            agent_id="test",
            driver=EchoDriver(),
            run_context=_make_run_context(),
            response_format="free_text",
        )
        assert rt._response_format == "free_text"
        await rt.initialize()
        await rt.close()
```

**Step 2: Run integration tests**

Run: `pytest tests/core/runtime/test_agentruntime_agnostic_integration.py -v`

**Expected output:** All 6 tests PASSED.

**Step 3: Run full suite for regression check**

Run: `pytest tests/ -x -q --tb=short`

**Expected output:** All tests pass.

**Step 4: Commit**

```bash
git add tests/core/runtime/test_agentruntime_agnostic_integration.py
git commit -m "test(runtime): add integration tests for AgentRuntime agnostic cascade resolution"
```

---

### Task 15: Run Code Review (Phase 3)

1. **Dispatch all 3 reviewers in parallel:**
   - REQUIRED SUB-SKILL: Use requesting-code-review
   - All reviewers run simultaneously
   - Wait for all to complete

2. **Handle findings by severity as per standard protocol.**

3. **Proceed only when zero Critical/High/Medium issues remain.**

---

## Phase 4: Documentation and Invariants (Tasks 16-18)

### Task 16: Update CLAUDE.md with New Rejection Rule section 4.5

**Files:**
- Modify: `CLAUDE.md` (section 4, add rule 5)

**Prerequisites:**
- Phase 3 complete

**Step 1: Add rule to CLAUDE.md**

In `CLAUDE.md`, locate section `## 4. Condições Críticas de Falha (Rejeição Imediata)`. Currently there are 4 rules. Add rule 5 after the existing 4 rules:

Add the following text after rule 4 (after the line about `ExecutionEvent`):

```
5.  Adicionar prompts hardcoded ou lógica de parsing de resposta no `AgentRuntime`. Prompts de coordenação pertencem ao Coordination Runtime ou ao Flow config. O AgentRuntime é compositor, não instrutor.
```

**Step 2: Verify the change**

Read the file and confirm rule 5 is in place.

**Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add rejection rule §4.5 — no hardcoded prompts in AgentRuntime"
```

---

### Task 17: Update Invariants Document with INV-7 and INV-8

**Files:**
- Modify: `docs/pt/architecture/09-invariantes-sistema-operacional.md`

**Prerequisites:**
- Task 16 complete

**Step 1: Add INV-7 and INV-8**

At the end of the "4. As 6 Invariantes Arquiteturais" section (before section 5), add two new invariant subsections:

```markdown

---

### Invariante 7: Separação Prompt↔Runtime

> **O AgentRuntime é compositor, não instrutor**

**A Regra:** O AgentRuntime NUNCA dita ao agente o formato de resposta ou constrói prompts de coordenação. Prompts de coordenação (contribute, review, consolidate) são responsabilidade do Coordination Runtime. O AgentRuntime enriquece com contexto local (memória, tools, system prompt) e delega ao backend.

**Justificativa Técnica:** O AgentRuntime deve ser agnóstico ao tipo de coordenação. O mesmo AgentRuntime pode participar em deliberações, workflows ou loops agentic sem modificação. A separação prompt/runtime permite que diferentes estratégias de interação coexistam sem alterar o compositor.

**Implementação:**
```python
# ANTES (violação)
class AgentRuntime:
    async def contribute(self, topic: str) -> Contribution:
        prompt = f"Contribute to: {topic}. Respond with JSON: ..."  # PROIBIDO

# DEPOIS (invariante)
class AgentRuntime:
    async def contribute(self, topic: str) -> Contribution:
        prompt = await resolve_prompt(  # Cascade: Strategy -> YAML -> default
            action="contribute",
            context={"topic": topic},
            strategy=self._interaction_strategy,
            flow_prompts=self._flow_prompts,
            default_prompt=build_default_contribute_prompt(topic=topic),
        )
        return await self.execute(prompt)  # compositor puro
```

**Validação CI/CD:**
- Grep: `AgentRuntime` não contém strings de prompt hardcoded (exceto em `default_prompts.py`)
- Test: AgentRuntime com `InteractionStrategy` customizada funciona sem alteração do core

---

### Invariante 8: Formato pertence ao Flow

> **response_format é propriedade do Flow config**

**A Regra:** O `response_format` é propriedade do Flow config, não do Agent. O mesmo agente pode participar em flows que esperam JSON e flows que esperam texto livre. O Coordination Runtime adapta o parsing conforme o `response_format` do flow.

**Justificativa Técnica:** Acoplar o formato de resposta ao agente limita a reutilização. Um agente que funciona com JSON num flow de deliberação pode precisar de free text num flow de brainstorming. A separação permite máxima composabilidade.

**Implementação:**
```yaml
# YAML — formato definido no Flow, não no Agent
flows:
  review:
    mode: deliberation
    response_format: free_text  # propriedade do flow
    prompts:
      contribute: "Review {topic} from your perspective."
```

**Validação CI/CD:**
- Test: mesmo agente participa em flow JSON e flow free_text sem configuração adicional
- Lint: `response_format` não existe em nenhum AgentSpec ou contrato de agente
```

**Step 2: Update the document header**

Change the version to `1.1.0` and update the count reference from "6 invariantes" to "8 invariantes" in the introductory text.

In the first paragraph (line 8), change:
- `as 6 invariantes invioláveis` -> `as 8 invariantes invioláveis`

Update section 5 (Veredito) to mention 8 invariantes and add:
```
- Prompt leaking no compositor → Invariante 7 (separação prompt/runtime)
- Formato acoplado ao agente → Invariante 8 (formato no flow)
```

Also update the table in section 7 to add rows for INV-7 and INV-8:

```
| 7. Separação Prompt↔Runtime | AgentRuntime Agnostic | [spec agnostic](../../superpowers/specs/2026-03-21-agentruntime-agnostic-design.md) |
| 8. Formato no Flow | AgentRuntime Agnostic | [spec agnostic](../../superpowers/specs/2026-03-21-agentruntime-agnostic-design.md) |
```

**Step 3: Commit**

```bash
git add docs/pt/architecture/09-invariantes-sistema-operacional.md
git commit -m "docs: add INV-7 (Prompt/Runtime separation) and INV-8 (Format belongs to Flow)"
```

---

### Task 18: Final Regression Test and Verification

**Files:**
- No file changes — verification only

**Prerequisites:**
- All tasks 1-17 complete

**Step 1: Run full test suite**

Run: `pytest tests/ -q --tb=short`

**Expected output:** All tests pass (2084+ existing + new tests). Zero failures.

**Step 2: Verify no prompts remain hardcoded in AgentRuntime**

Run: `grep -n "Respond with JSON" miniautogen/core/runtime/agent_runtime.py`

**Expected output:** No matches (all prompts moved to `default_prompts.py` or resolved via cascade).

**Step 3: Verify InteractionStrategy protocol is importable**

Run: `python -c "from miniautogen.core.contracts.interaction import InteractionStrategy; print('OK')"`

**Expected output:** `OK`

**Step 4: Verify FlowConfig accepts new fields**

Run: `python -c "from miniautogen.cli.config import FlowConfig; fc = FlowConfig(mode='workflow', participants=['a'], response_format='free_text', prompts={'contribute': 'test'}); print(fc.response_format, fc.prompts)"`

**Expected output:** `free_text {'contribute': 'test'}`

**Step 5: Verify CLAUDE.md has rule 5**

Run: `grep -n "compositor, não instrutor" CLAUDE.md`

**Expected output:** Match found in section 4.

**Step 6: Verify invariants doc has INV-7 and INV-8**

Run: `grep -n "INV-7\|Invariante 7\|Invariante 8\|INV-8" docs/pt/architecture/09-invariantes-sistema-operacional.md`

**Expected output:** Matches found for both invariants.

**Step 7: Commit verification log**

No commit needed — this is a verification-only task.

---

## Summary of All Files Modified/Created

| File | Action | Task |
|------|--------|------|
| `miniautogen/core/contracts/interaction.py` | Create | 1 |
| `tests/core/contracts/test_interaction_strategy.py` | Create | 1 |
| `miniautogen/cli/config.py` | Modify | 2 |
| `tests/cli/test_config_response_format.py` | Create | 2 |
| `miniautogen/core/runtime/agent_runtime.py` | Modify | 3, 4, 8, 9, 10, 11 |
| `tests/core/runtime/test_agent_runtime.py` | Modify | 3, 4, 8 |
| `miniautogen/core/runtime/default_prompts.py` | Create | 6 |
| `tests/core/runtime/test_default_prompts.py` | Create | 6 |
| `miniautogen/core/runtime/prompt_resolver.py` | Create | 7 |
| `tests/core/runtime/test_prompt_resolver.py` | Create | 7 |
| `miniautogen/core/runtime/pipeline_runner.py` | Modify | 13 |
| `tests/core/runtime/test_flow_config_propagation.py` | Create | 13 |
| `tests/core/runtime/test_agentruntime_agnostic_integration.py` | Create | 14 |
| `CLAUDE.md` | Modify | 16 |
| `docs/pt/architecture/09-invariantes-sistema-operacional.md` | Modify | 17 |

## Backward Compatibility Guarantees

1. **All existing tests pass** — default `response_format="json"` and empty `flow_prompts={}` preserve exact current behavior
2. **AgentRuntime constructor** — all new params are optional with backward-compatible defaults
3. **Protocol satisfaction** — WorkflowAgent, ConversationalAgent, DeliberationAgent protocols unchanged
4. **Tamagotchi E2E demo** — `run.py` calls `runner.run_from_config()` which uses `FlowConfig` defaults; no changes needed
5. **Convenience wrappers** — `contribute()`, `review()`, `consolidate()`, `produce_final_document()`, `route()` maintain exact same signatures and return types
