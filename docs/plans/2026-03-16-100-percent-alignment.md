# MiniAutoGen 100% Architectural Alignment Implementation Plan

> **Status:** Concluído. Ver commits recentes.

> **For Agents:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Close all 8 architectural gaps to bring MiniAutoGen from ~75% to 100% alignment with its Side C specification.

**Architecture:** The system is a multi-agent coordination microkernel. Coordination modes (Workflow, Deliberation, AgenticLoop) implement a `CoordinationMode[PlanT]` protocol and are executed by `PipelineRunner`. Modes compose via `CompositeRuntime`. Contracts use Pydantic `BaseModel` for data and `Protocol` for behavior. Policies are frozen dataclasses. Events flow through `EventSink`.

**Tech Stack:** Python 3.11, Pydantic v2, Protocol + @runtime_checkable, pytest + pytest-asyncio, structlog, anyio, tenacity

**Global Prerequisites:**
- Environment: macOS / Python 3.11+
- Tools: pytest, pytest-asyncio, structlog, anyio, tenacity, pydantic v2
- State: Branch from `main` (commit `f0f77cb`), clean working tree

**Verification before starting:**
```bash
cd /Users/brunocapelao/Projects/miniAutoGen
python --version        # Expected: Python 3.11+
pytest --version        # Expected: pytest 7.0+
git status              # Expected: clean working tree on main
pytest -x -q            # Expected: 171 tests passed, 0 failed
```

---

## Phase 1: Generalize Deliberation Contracts (GAP 2)

### Task 1.1: Create General Deliberation Contracts

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/contracts/deliberation.py`

**Prerequisites:**
- All 171 existing tests pass

**Step 1: Write the failing test**

Create file `/Users/brunocapelao/Projects/miniAutoGen/tests/core/contracts/test_general_deliberation.py`:

```python
"""Tests for generalized deliberation contracts."""

from miniautogen.core.contracts.deliberation import (
    Contribution,
    Review,
    ResearchOutput,
    PeerReview,
)


def test_contribution_base_model_has_required_fields() -> None:
    contrib = Contribution(
        participant_id="analyst",
        title="Market Analysis",
        content={"findings": ["finding-1"], "recommendation": "proceed"},
    )
    assert contrib.participant_id == "analyst"
    assert contrib.title == "Market Analysis"
    assert contrib.content["findings"] == ["finding-1"]


def test_review_base_model_has_required_fields() -> None:
    review = Review(
        reviewer_id="critic",
        target_id="analyst",
        target_title="Market Analysis",
        strengths=["solid methodology"],
        concerns=["missing data"],
        questions=["what about Q4?"],
    )
    assert review.reviewer_id == "critic"
    assert review.target_id == "analyst"
    assert len(review.concerns) == 1


def test_research_output_is_subclass_of_contribution() -> None:
    ro = ResearchOutput(
        role_name="analyst",
        section_title="Findings",
        findings=["f1"],
        facts=["fact1"],
        recommendation="proceed",
    )
    assert isinstance(ro, Contribution)
    assert ro.participant_id == "analyst"
    assert ro.title == "Findings"


def test_peer_review_is_subclass_of_review() -> None:
    pr = PeerReview(
        reviewer_role="critic",
        target_role="analyst",
        target_section_title="Findings",
        strengths=["good"],
        concerns=["bad"],
        questions=["why?"],
    )
    assert isinstance(pr, Review)
    assert pr.reviewer_id == "critic"
    assert pr.target_id == "analyst"
    assert pr.target_title == "Findings"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/core/contracts/test_general_deliberation.py -v`

**Expected output:**
```
FAILED - ImportError: cannot import name 'Contribution' from 'miniautogen.core.contracts.deliberation'
```

**Step 3: Implement general contracts**

Modify `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/contracts/deliberation.py`. Add the general base classes ABOVE the existing ones, then make `ResearchOutput` and `PeerReview` inherit from them:

```python
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# --- General deliberation contracts ---


class Contribution(BaseModel):
    """General-purpose contribution in a deliberation cycle.

    Any participant can produce a Contribution. Specialized forms
    (e.g., ResearchOutput) extend this base.
    """

    participant_id: str
    title: str
    content: dict[str, Any] = Field(default_factory=dict)


class Review(BaseModel):
    """General-purpose review of another participant's contribution.

    Specialized forms (e.g., PeerReview) extend this base.
    """

    reviewer_id: str
    target_id: str
    target_title: str
    strengths: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)


# --- Research-specific deliberation contracts (backward-compatible) ---


class ResearchOutput(Contribution):
    """Structured output produced by a specialist research agent.

    Extends Contribution with research-specific fields.
    ``participant_id`` is aliased from ``role_name``.
    ``title`` is aliased from ``section_title``.
    """

    role_name: str
    section_title: str
    findings: list[str] = Field(default_factory=list)
    facts: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    inferences: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    recommendation: str
    next_tests: list[str] = Field(default_factory=list)

    def model_post_init(self, __context: Any) -> None:
        # Sync base fields from specialized fields
        if not self.participant_id:
            object.__setattr__(self, "participant_id", self.role_name)
        if not self.title:
            object.__setattr__(self, "title", self.section_title)

    @property
    def participant_id(self) -> str:  # type: ignore[override]
        return self.role_name

    @participant_id.setter
    def participant_id(self, value: str) -> None:
        pass  # Derived from role_name

    @property
    def title(self) -> str:  # type: ignore[override]
        return self.section_title

    @title.setter
    def title(self, value: str) -> None:
        pass  # Derived from section_title


class PeerReview(Review):
    """Cross-review emitted by one specialist about another specialist output.

    Extends Review with research-specific naming.
    ``reviewer_id`` is aliased from ``reviewer_role``.
    ``target_id`` is aliased from ``target_role``.
    ``target_title`` is aliased from ``target_section_title``.
    """

    reviewer_role: str
    target_role: str
    target_section_title: str

    def model_post_init(self, __context: Any) -> None:
        if not self.reviewer_id:
            object.__setattr__(self, "reviewer_id", self.reviewer_role)
        if not self.target_id:
            object.__setattr__(self, "target_id", self.target_role)
        if not self.target_title:
            object.__setattr__(self, "target_title", self.target_section_title)

    @property
    def reviewer_id(self) -> str:  # type: ignore[override]
        return self.reviewer_role

    @reviewer_id.setter
    def reviewer_id(self, value: str) -> None:
        pass

    @property
    def target_id(self) -> str:  # type: ignore[override]
        return self.target_role

    @target_id.setter
    def target_id(self, value: str) -> None:
        pass

    @property
    def target_title(self) -> str:  # type: ignore[override]
        return self.target_section_title

    @target_title.setter
    def target_title(self, value: str) -> None:
        pass


class DeliberationState(BaseModel):
    """Aggregated state of a deliberative research workflow."""

    review_cycle: int = 0
    accepted_facts: list[str] = Field(default_factory=list)
    open_conflicts: list[str] = Field(default_factory=list)
    pending_gaps: list[str] = Field(default_factory=list)
    leader_decision: str | None = None
    is_sufficient: bool = False
    rejection_reasons: list[str] = Field(default_factory=list)


class FinalDocument(BaseModel):
    """Structured envelope for the final decision-oriented document."""

    executive_summary: str
    accepted_facts: list[str] = Field(default_factory=list)
    open_conflicts: list[str] = Field(default_factory=list)
    pending_decisions: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    decision_summary: str
    body_markdown: str
```

**IMPORTANT NOTE ON IMPLEMENTATION:** The property-based approach above for syncing base fields with specialized fields may have Pydantic v2 complications. An alternative approach that is simpler and more Pydantic-friendly is to use `model_validator`:

```python
class ResearchOutput(Contribution):
    role_name: str
    section_title: str
    findings: list[str] = Field(default_factory=list)
    facts: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    inferences: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    recommendation: str
    next_tests: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def sync_base_fields(cls, data: dict) -> dict:
        if isinstance(data, dict):
            if "participant_id" not in data and "role_name" in data:
                data["participant_id"] = data["role_name"]
            if "title" not in data and "section_title" in data:
                data["title"] = data["section_title"]
        return data
```

Use whichever approach passes the tests. The `model_validator` approach is recommended because it works cleanly with Pydantic v2 serialization. Apply the same pattern for `PeerReview`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/core/contracts/test_general_deliberation.py -v`

**Expected output:**
```
PASSED tests/core/contracts/test_general_deliberation.py::test_contribution_base_model_has_required_fields
PASSED tests/core/contracts/test_general_deliberation.py::test_review_base_model_has_required_fields
PASSED tests/core/contracts/test_general_deliberation.py::test_research_output_is_subclass_of_contribution
PASSED tests/core/contracts/test_general_deliberation.py::test_peer_review_is_subclass_of_review
```

**Step 5: Run ALL existing tests to verify backward compatibility**

Run: `pytest -x -q`

**Expected output:**
```
175 passed
```

All 171 original tests plus 4 new ones must pass. If any existing deliberation tests fail, the inheritance bridge between `ResearchOutput`/`Contribution` and `PeerReview`/`Review` needs adjustment. The key constraint: `ResearchOutput(role_name="x", section_title="y", ...)` must still work identically to before.

**Step 6: Commit**

```bash
git add miniautogen/core/contracts/deliberation.py tests/core/contracts/test_general_deliberation.py
git commit -m "feat: add general Contribution and Review contracts for deliberation (DA-3)"
```

**If Task Fails:**

1. **Pydantic inheritance issue with properties:**
   - Switch to `model_validator(mode="before")` approach described above
   - Pydantic v2 does not support Python property descriptors on model fields

2. **Existing deliberation tests break:**
   - Run: `pytest tests/core/contracts/test_deliberation.py tests/core/runtime/test_deliberation_runtime.py -v`
   - Check: Are `ResearchOutput` and `PeerReview` constructors still the same?
   - The `model_validator(mode="before")` approach should default `participant_id`/`title` from `role_name`/`section_title`, making old constructor calls work

3. **Can't recover:**
   - `git checkout -- miniautogen/core/contracts/deliberation.py`
   - Document what broke and return to human partner

---

### Task 1.2: Export General Contracts from `__init__.py`

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/contracts/__init__.py`

**Prerequisites:**
- Task 1.1 complete, all tests pass

**Step 1: Write the failing test**

Create file `/Users/brunocapelao/Projects/miniAutoGen/tests/core/contracts/test_general_deliberation_exports.py`:

```python
"""Test that general deliberation contracts are exported from the contracts package."""


def test_contribution_importable_from_contracts() -> None:
    from miniautogen.core.contracts import Contribution
    assert Contribution is not None


def test_review_importable_from_contracts() -> None:
    from miniautogen.core.contracts import Review
    assert Review is not None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/core/contracts/test_general_deliberation_exports.py -v`

**Expected output:**
```
FAILED - ImportError: cannot import name 'Contribution'
```

**Step 3: Update the contracts `__init__.py`**

In `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/contracts/__init__.py`, add `Contribution` and `Review` to the imports from `.deliberation` and to `__all__`:

Change this line:
```python
from .deliberation import DeliberationState, FinalDocument, PeerReview, ResearchOutput
```
To:
```python
from .deliberation import Contribution, DeliberationState, FinalDocument, PeerReview, ResearchOutput, Review
```

And add `"Contribution"` and `"Review"` to `__all__` (in alphabetical order after `"CoordinationPlan"` and before `"RouterDecision"` respectively).

**Step 4: Run test to verify it passes**

Run: `pytest tests/core/contracts/test_general_deliberation_exports.py -v`

**Expected output:**
```
PASSED tests/core/contracts/test_general_deliberation_exports.py::test_contribution_importable_from_contracts
PASSED tests/core/contracts/test_general_deliberation_exports.py::test_review_importable_from_contracts
```

**Step 5: Run all tests**

Run: `pytest -x -q`

**Expected output:** All tests pass (177 total).

**Step 6: Commit**

```bash
git add miniautogen/core/contracts/__init__.py tests/core/contracts/test_general_deliberation_exports.py
git commit -m "feat: export Contribution and Review from contracts package"
```

**If Task Fails:**

1. **Import conflict:** Check alphabetical ordering in `__all__`. Verify no circular imports.
2. **Rollback:** `git checkout -- miniautogen/core/contracts/__init__.py`

---

### Task 1.3: Code Review Checkpoint (Phase 1)

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

3. **Proceed only when:** Zero Critical/High/Medium issues remain.

---

## Phase 2: Agent Protocols (GAP 3)

### Task 2.1: Define Agent Capability Protocols

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/contracts/agent.py`

**Prerequisites:**
- Phase 1 complete, all tests pass

**Step 1: Write the failing test**

Create file `/Users/brunocapelao/Projects/miniAutoGen/tests/core/contracts/test_agent_protocols.py`:

```python
"""Tests for agent capability protocols."""

from __future__ import annotations

from typing import Any, runtime_checkable

import pytest

from miniautogen.core.contracts.agent import (
    ConversationalAgent,
    DeliberationAgent,
    WorkflowAgent,
)
from miniautogen.core.contracts.agentic_loop import RouterDecision
from miniautogen.core.contracts.deliberation import (
    Contribution,
    DeliberationState,
    FinalDocument,
    Review,
)


# --- Concrete test implementations ---


class MyWorkflowAgent:
    async def process(self, input_data: Any) -> Any:
        return f"processed-{input_data}"


class MyDeliberationAgent:
    async def contribute(self, topic: str) -> Contribution:
        return Contribution(participant_id="me", title="analysis", content={"data": topic})

    async def review(self, target_id: str, contribution: Contribution) -> Review:
        return Review(
            reviewer_id="me",
            target_id=target_id,
            target_title=contribution.title,
            strengths=["good"],
        )

    async def consolidate(
        self,
        topic: str,
        contributions: list[Contribution],
        reviews: list[Review],
    ) -> DeliberationState:
        return DeliberationState(is_sufficient=True)

    async def produce_final_document(
        self,
        state: DeliberationState,
        contributions: list[Contribution],
    ) -> FinalDocument:
        return FinalDocument(
            executive_summary="done",
            decision_summary="proceed",
            body_markdown="# Done",
        )


class MyConversationalAgent:
    async def reply(self, message: str, context: dict[str, Any]) -> str:
        return f"reply to: {message}"


# --- Tests ---


def test_workflow_agent_protocol_check() -> None:
    agent = MyWorkflowAgent()
    assert isinstance(agent, WorkflowAgent)


def test_deliberation_agent_protocol_check() -> None:
    agent = MyDeliberationAgent()
    assert isinstance(agent, DeliberationAgent)


def test_conversational_agent_protocol_check() -> None:
    agent = MyConversationalAgent()
    assert isinstance(agent, ConversationalAgent)


def test_plain_object_is_not_workflow_agent() -> None:
    assert not isinstance(object(), WorkflowAgent)


def test_plain_object_is_not_deliberation_agent() -> None:
    assert not isinstance(object(), DeliberationAgent)


def test_plain_object_is_not_conversational_agent() -> None:
    assert not isinstance(object(), ConversationalAgent)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/core/contracts/test_agent_protocols.py -v`

**Expected output:**
```
FAILED - ModuleNotFoundError: No module named 'miniautogen.core.contracts.agent'
```

**Step 3: Implement agent protocols**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/contracts/agent.py`:

```python
"""Agent capability protocols for MiniAutoGen coordination modes.

Each protocol defines the minimum interface an agent must satisfy to
participate in a given coordination mode.  Agents can implement multiple
protocols (e.g., both WorkflowAgent and ConversationalAgent).

Usage:
    isinstance(my_agent, WorkflowAgent)  # True if duck-typing matches
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from miniautogen.core.contracts.deliberation import (
    Contribution,
    DeliberationState,
    FinalDocument,
    Review,
)


@runtime_checkable
class WorkflowAgent(Protocol):
    """Agent capable of participating in a WorkflowRuntime step.

    Must accept arbitrary input and produce arbitrary output.
    """

    async def process(self, input_data: Any) -> Any: ...


@runtime_checkable
class DeliberationAgent(Protocol):
    """Agent capable of participating in a DeliberationRuntime cycle.

    Must support: contribute, review, consolidate, produce_final_document.
    """

    async def contribute(self, topic: str) -> Contribution: ...

    async def review(
        self, target_id: str, contribution: Contribution
    ) -> Review: ...

    async def consolidate(
        self,
        topic: str,
        contributions: list[Contribution],
        reviews: list[Review],
    ) -> DeliberationState: ...

    async def produce_final_document(
        self,
        state: DeliberationState,
        contributions: list[Contribution],
    ) -> FinalDocument: ...


@runtime_checkable
class ConversationalAgent(Protocol):
    """Agent capable of participating in an AgenticLoop conversation.

    Must accept a message and conversation context and produce a reply.
    """

    async def reply(self, message: str, context: dict[str, Any]) -> str: ...
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/core/contracts/test_agent_protocols.py -v`

**Expected output:**
```
PASSED tests/core/contracts/test_agent_protocols.py::test_workflow_agent_protocol_check
PASSED tests/core/contracts/test_agent_protocols.py::test_deliberation_agent_protocol_check
PASSED tests/core/contracts/test_agent_protocols.py::test_conversational_agent_protocol_check
PASSED tests/core/contracts/test_agent_protocols.py::test_plain_object_is_not_workflow_agent
PASSED tests/core/contracts/test_agent_protocols.py::test_plain_object_is_not_deliberation_agent
PASSED tests/core/contracts/test_agent_protocols.py::test_plain_object_is_not_conversational_agent
```

**Step 5: Run all tests**

Run: `pytest -x -q`

**Expected output:** All tests pass.

**Step 6: Commit**

```bash
git add miniautogen/core/contracts/agent.py tests/core/contracts/test_agent_protocols.py
git commit -m "feat: add WorkflowAgent, DeliberationAgent, ConversationalAgent protocols"
```

**If Task Fails:**

1. **`@runtime_checkable` isinstance check fails:**
   - Verify each concrete class has ALL methods required by the Protocol
   - Method signatures must match exactly (parameter names and types)
   - Pydantic models in return types must match

2. **Import error from deliberation:**
   - Verify `Contribution` and `Review` are importable from `miniautogen.core.contracts.deliberation`
   - This depends on Phase 1 being complete

3. **Rollback:** `rm miniautogen/core/contracts/agent.py`

---

### Task 2.2: Export Agent Protocols from Contracts Package

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/contracts/__init__.py`

**Prerequisites:**
- Task 2.1 complete

**Step 1: Write the failing test**

Create file `/Users/brunocapelao/Projects/miniAutoGen/tests/core/contracts/test_agent_protocol_exports.py`:

```python
"""Test that agent protocols are exported from contracts package."""


def test_agent_protocols_importable_from_contracts() -> None:
    from miniautogen.core.contracts import (
        ConversationalAgent,
        DeliberationAgent,
        WorkflowAgent,
    )
    assert WorkflowAgent is not None
    assert DeliberationAgent is not None
    assert ConversationalAgent is not None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/core/contracts/test_agent_protocol_exports.py -v`

**Expected output:**
```
FAILED - ImportError: cannot import name 'WorkflowAgent'
```

**Step 3: Update `__init__.py`**

In `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/contracts/__init__.py`, add:

```python
from .agent import ConversationalAgent, DeliberationAgent, WorkflowAgent
```

And add these three names to `__all__` in alphabetical order.

**Step 4: Run test to verify it passes**

Run: `pytest tests/core/contracts/test_agent_protocol_exports.py -v`

**Expected output:** All PASSED.

**Step 5: Run all tests**

Run: `pytest -x -q`

**Expected output:** All tests pass.

**Step 6: Commit**

```bash
git add miniautogen/core/contracts/__init__.py tests/core/contracts/test_agent_protocol_exports.py
git commit -m "feat: export agent protocols from contracts package"
```

**If Task Fails:**

1. **Circular import:** The agent module imports from deliberation. Ensure no reverse dependency.
2. **Rollback:** `git checkout -- miniautogen/core/contracts/__init__.py`

---

## Phase 3: Conversation Contract (GAP 6)

### Task 3.1: Create Conversation Model

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/contracts/conversation.py`

**Prerequisites:**
- Phase 2 complete, all tests pass

**Step 1: Write the failing test**

Create file `/Users/brunocapelao/Projects/miniAutoGen/tests/core/contracts/test_conversation.py`:

```python
"""Tests for the Conversation contract."""

from datetime import datetime

from miniautogen.core.contracts.conversation import Conversation
from miniautogen.core.contracts.message import Message


def test_empty_conversation() -> None:
    convo = Conversation(conversation_id="conv-1")
    assert convo.conversation_id == "conv-1"
    assert convo.messages == []
    assert convo.metadata == {}


def test_conversation_with_messages() -> None:
    msgs = [
        Message(sender_id="agent-a", content="hello"),
        Message(sender_id="agent-b", content="world"),
    ]
    convo = Conversation(conversation_id="conv-2", messages=msgs)
    assert len(convo.messages) == 2
    assert convo.messages[0].sender_id == "agent-a"
    assert convo.messages[1].content == "world"


def test_append_message() -> None:
    convo = Conversation(conversation_id="conv-3")
    new_convo = convo.append(Message(sender_id="user", content="hi"))
    # Original is unchanged (immutable pattern)
    assert len(convo.messages) == 0
    assert len(new_convo.messages) == 1
    assert new_convo.messages[0].content == "hi"


def test_last_message() -> None:
    convo = Conversation(
        conversation_id="conv-4",
        messages=[
            Message(sender_id="a", content="first"),
            Message(sender_id="b", content="second"),
        ],
    )
    assert convo.last_message is not None
    assert convo.last_message.content == "second"


def test_last_message_empty_returns_none() -> None:
    convo = Conversation(conversation_id="conv-5")
    assert convo.last_message is None


def test_conversation_participant_ids() -> None:
    convo = Conversation(
        conversation_id="conv-6",
        messages=[
            Message(sender_id="a", content="x"),
            Message(sender_id="b", content="y"),
            Message(sender_id="a", content="z"),
        ],
    )
    assert convo.participant_ids == {"a", "b"}
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/core/contracts/test_conversation.py -v`

**Expected output:**
```
FAILED - ModuleNotFoundError: No module named 'miniautogen.core.contracts.conversation'
```

**Step 3: Implement Conversation model**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/contracts/conversation.py`:

```python
"""Conversation contract — typed conversation history for MiniAutoGen.

Provides an immutable-style conversation model usable by AgenticLoopComponent
and potentially by DeliberationRuntime.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from miniautogen.core.contracts.message import Message


class Conversation(BaseModel):
    """A typed conversation history.

    Immutable-style: ``append()`` returns a new Conversation with the
    added message rather than mutating in place.
    """

    conversation_id: str
    messages: list[Message] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def append(self, message: Message) -> "Conversation":
        """Return a new Conversation with the message appended."""
        return self.model_copy(
            update={"messages": [*self.messages, message]},
        )

    @property
    def last_message(self) -> Message | None:
        """Return the most recent message, or None if empty."""
        return self.messages[-1] if self.messages else None

    @property
    def participant_ids(self) -> set[str]:
        """Return the set of unique sender_ids in this conversation."""
        return {m.sender_id for m in self.messages}
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/core/contracts/test_conversation.py -v`

**Expected output:**
```
PASSED tests/core/contracts/test_conversation.py::test_empty_conversation
PASSED tests/core/contracts/test_conversation.py::test_conversation_with_messages
PASSED tests/core/contracts/test_conversation.py::test_append_message
PASSED tests/core/contracts/test_conversation.py::test_last_message
PASSED tests/core/contracts/test_conversation.py::test_last_message_empty_returns_none
PASSED tests/core/contracts/test_conversation.py::test_conversation_participant_ids
```

**Step 5: Run all tests**

Run: `pytest -x -q`

**Expected output:** All tests pass.

**Step 6: Commit**

```bash
git add miniautogen/core/contracts/conversation.py tests/core/contracts/test_conversation.py
git commit -m "feat: add Conversation contract for typed conversation history"
```

**If Task Fails:**

1. **`model_copy` issue:** Pydantic v2 uses `model_copy(update={...})`. If using Pydantic v1, use `.copy(update={...})` instead.
2. **Rollback:** `rm miniautogen/core/contracts/conversation.py`

---

### Task 3.2: Export Conversation from Contracts Package

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/contracts/__init__.py`

**Prerequisites:**
- Task 3.1 complete

**Step 1: Write the failing test**

Create file `/Users/brunocapelao/Projects/miniAutoGen/tests/core/contracts/test_conversation_exports.py`:

```python
"""Test Conversation is exported from contracts package."""


def test_conversation_importable_from_contracts() -> None:
    from miniautogen.core.contracts import Conversation
    assert Conversation is not None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/core/contracts/test_conversation_exports.py -v`

**Expected output:**
```
FAILED - ImportError: cannot import name 'Conversation'
```

**Step 3: Update `__init__.py`**

In `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/contracts/__init__.py`, add:

```python
from .conversation import Conversation
```

And add `"Conversation"` to `__all__`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/core/contracts/test_conversation_exports.py -v`

**Expected output:** PASSED.

**Step 5: Commit**

```bash
git add miniautogen/core/contracts/__init__.py tests/core/contracts/test_conversation_exports.py
git commit -m "feat: export Conversation from contracts package"
```

---

### Task 3.3: Code Review Checkpoint (Phases 2-3)

1. **Dispatch all 3 reviewers in parallel:**
   - REQUIRED SUB-SKILL: Use requesting-code-review
   - Review all changes since Phase 1 checkpoint

2. **Handle findings by severity** as described in Task 1.3.

3. **Proceed only when:** Zero Critical/High/Medium issues remain.

---

## Phase 4: AgenticLoopComponent (GAP 1) — MAIN DELIVERABLE

### Task 4.1: Add AgenticLoop Event Types to EventType Enum

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/events/types.py`

**Prerequisites:**
- Phases 1-3 complete

**Step 1: Write the failing test**

Create file `/Users/brunocapelao/Projects/miniAutoGen/tests/core/events/test_agentic_loop_event_types.py`:

```python
"""Test that agentic loop event types exist in the EventType enum."""

from miniautogen.core.events.types import EventType


def test_agentic_loop_started_in_enum() -> None:
    assert EventType.AGENTIC_LOOP_STARTED.value == "agentic_loop_started"


def test_router_decision_emitted_in_enum() -> None:
    assert EventType.ROUTER_DECISION_EMITTED.value == "router_decision_emitted"


def test_agent_reply_recorded_in_enum() -> None:
    assert EventType.AGENT_REPLY_RECORDED.value == "agent_reply_recorded"


def test_agentic_loop_stopped_in_enum() -> None:
    assert EventType.AGENTIC_LOOP_STOPPED.value == "agentic_loop_stopped"


def test_stagnation_detected_in_enum() -> None:
    assert EventType.STAGNATION_DETECTED.value == "stagnation_detected"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/core/events/test_agentic_loop_event_types.py -v`

**Expected output:**
```
FAILED - AttributeError: 'AGENTIC_LOOP_STARTED' is not a member of 'EventType'
```

**Step 3: Add event types to enum**

In `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/events/types.py`, add these members to the `EventType` enum (before the closing of the class, after `BUDGET_EXCEEDED`):

```python
    AGENTIC_LOOP_STARTED = "agentic_loop_started"
    ROUTER_DECISION_EMITTED = "router_decision_emitted"
    AGENT_REPLY_RECORDED = "agent_reply_recorded"
    AGENTIC_LOOP_STOPPED = "agentic_loop_stopped"
    STAGNATION_DETECTED = "stagnation_detected"
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/core/events/test_agentic_loop_event_types.py -v`

**Expected output:** All 5 PASSED.

**Step 5: Run all tests**

Run: `pytest -x -q`

**Expected output:** All tests pass. Check specifically:
```
pytest tests/core/events/ -v
```
The existing `test_agentic_loop_events.py` uses the `AGENTIC_LOOP_EVENT_TYPES` set constant, which should still work because those are string literals, not enum members.

**Step 6: Commit**

```bash
git add miniautogen/core/events/types.py tests/core/events/test_agentic_loop_event_types.py
git commit -m "feat: add agentic loop event types to EventType enum"
```

**If Task Fails:**

1. **Existing event tests break:** The `AGENTIC_LOOP_EVENT_TYPES` set at the bottom of `types.py` uses raw strings, not enum values. It should still work. If not, update the set to use `EventType.AGENTIC_LOOP_STARTED.value` etc.
2. **Rollback:** `git checkout -- miniautogen/core/events/types.py`

---

### Task 4.2: Create AgenticLoopPlan Contract

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/contracts/coordination.py`

**Prerequisites:**
- Task 4.1 complete

**Step 1: Write the failing test**

Create file `/Users/brunocapelao/Projects/miniAutoGen/tests/core/contracts/test_agentic_loop_plan.py`:

```python
"""Tests for AgenticLoopPlan contract."""

from miniautogen.core.contracts.coordination import (
    AgenticLoopPlan,
    CoordinationKind,
    CoordinationPlan,
)
from miniautogen.core.contracts.agentic_loop import ConversationPolicy


def test_agentic_loop_plan_is_coordination_plan() -> None:
    plan = AgenticLoopPlan(
        participants=["agent-a", "agent-b"],
        router_agent="router",
    )
    assert isinstance(plan, CoordinationPlan)


def test_agentic_loop_plan_defaults() -> None:
    plan = AgenticLoopPlan(
        participants=["a"],
        router_agent="r",
    )
    assert plan.policy.max_turns == 8
    assert plan.initial_message == ""


def test_agentic_loop_plan_custom_policy() -> None:
    policy = ConversationPolicy(max_turns=20, timeout_seconds=300.0)
    plan = AgenticLoopPlan(
        participants=["a", "b"],
        router_agent="r",
        policy=policy,
        initial_message="Start the discussion",
    )
    assert plan.policy.max_turns == 20
    assert plan.initial_message == "Start the discussion"
    assert len(plan.participants) == 2


def test_coordination_kind_has_agentic_loop() -> None:
    assert CoordinationKind.AGENTIC_LOOP.value == "agentic_loop"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/core/contracts/test_agentic_loop_plan.py -v`

**Expected output:**
```
FAILED - ImportError: cannot import name 'AgenticLoopPlan'
```

**Step 3: Implement AgenticLoopPlan**

In `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/contracts/coordination.py`:

1. Add `AGENTIC_LOOP = "agentic_loop"` to the `CoordinationKind` enum.

2. Add at the end of the file:

```python
# --- Agentic Loop contracts ---


class AgenticLoopPlan(CoordinationPlan):
    """Execution plan for AgenticLoopRuntime.

    Models a contained conversational loop where a router agent
    selects which participant speaks next, until a stopping condition
    is met (max turns, stagnation, or router termination).
    """

    participants: list[str] = Field(min_length=1)
    router_agent: str
    policy: ConversationPolicy = Field(default_factory=ConversationPolicy)
    initial_message: str = ""
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/core/contracts/test_agentic_loop_plan.py -v`

**Expected output:** All 4 PASSED.

**Step 5: Run all tests**

Run: `pytest -x -q`

**Expected output:** All tests pass. Pay special attention to `tests/core/contracts/test_coordination.py`.

**Step 6: Commit**

```bash
git add miniautogen/core/contracts/coordination.py tests/core/contracts/test_agentic_loop_plan.py
git commit -m "feat: add AgenticLoopPlan contract and AGENTIC_LOOP coordination kind"
```

**If Task Fails:**

1. **Existing coordination tests break:** Adding enum members should not break existing tests. If `CoordinationKind` iteration tests exist, they may need updating.
2. **Rollback:** `git checkout -- miniautogen/core/contracts/coordination.py`

---

### Task 4.3: Implement AgenticLoopRuntime

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/runtime/agentic_loop_runtime.py`

**Prerequisites:**
- Tasks 4.1 and 4.2 complete

This is the largest task. It implements the core agentic loop coordination mode.

**Step 1: Write the failing test**

Create file `/Users/brunocapelao/Projects/miniAutoGen/tests/core/runtime/test_agentic_loop_runtime_full.py`:

```python
"""Tests for AgenticLoopRuntime — the full agentic loop coordination mode."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from miniautogen.core.contracts.agentic_loop import (
    ConversationPolicy,
    RouterDecision,
)
from miniautogen.core.contracts.coordination import (
    AgenticLoopPlan,
    CoordinationKind,
    CoordinationMode,
)
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.run_result import RunResult
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.runtime.agentic_loop_runtime import AgenticLoopRuntime
from miniautogen.core.runtime.pipeline_runner import PipelineRunner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context(run_id: str = "run-1", input_payload: Any = None) -> RunContext:
    return RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id="corr-1",
        input_payload=input_payload or "initial-prompt",
    )


class FakeRouter:
    """Router agent that returns predetermined decisions."""

    def __init__(self, decisions: list[RouterDecision]) -> None:
        self._decisions = list(decisions)
        self._call_count = 0

    async def route(
        self, conversation_history: list[dict[str, str]]
    ) -> RouterDecision:
        if self._call_count < len(self._decisions):
            decision = self._decisions[self._call_count]
        else:
            decision = RouterDecision(
                current_state_summary="done",
                missing_information="none",
                terminate=True,
                stagnation_risk=0.0,
            )
        self._call_count += 1
        return decision


class FakeConversationalAgent:
    """Agent that replies with a predictable message."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.reply_calls: list[tuple[str, dict[str, Any]]] = []

    async def reply(self, message: str, context: dict[str, Any]) -> str:
        self.reply_calls.append((message, context))
        return f"{self.name}-reply-to-{message}"


class FailingConversationalAgent:
    """Agent whose reply always raises."""

    async def reply(self, message: str, context: dict[str, Any]) -> str:
        raise RuntimeError("agent crashed")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_agentic_loop_runtime_satisfies_protocol() -> None:
    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)
    runtime = AgenticLoopRuntime(runner=runner)
    assert isinstance(runtime, CoordinationMode)
    assert runtime.kind == CoordinationKind.AGENTIC_LOOP


@pytest.mark.asyncio
async def test_simple_2_turn_conversation() -> None:
    """Router selects agent-a, then agent-b, then terminates."""
    agent_a = FakeConversationalAgent("a")
    agent_b = FakeConversationalAgent("b")
    router = FakeRouter([
        RouterDecision(
            current_state_summary="start",
            missing_information="need a's input",
            next_agent="a",
            stagnation_risk=0.0,
        ),
        RouterDecision(
            current_state_summary="got a's input",
            missing_information="need b's input",
            next_agent="b",
            stagnation_risk=0.0,
        ),
        RouterDecision(
            current_state_summary="complete",
            missing_information="none",
            terminate=True,
            stagnation_risk=0.0,
        ),
    ])

    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)
    runtime = AgenticLoopRuntime(
        runner=runner,
        agent_registry={"a": agent_a, "b": agent_b, "router": router},
    )

    plan = AgenticLoopPlan(
        participants=["a", "b"],
        router_agent="router",
        initial_message="discuss topic X",
    )
    ctx = _make_context()
    result = await runtime.run(agents=[], context=ctx, plan=plan)

    assert result.status == "finished"
    assert result.run_id == ctx.run_id
    # Both agents should have replied once
    assert len(agent_a.reply_calls) == 1
    assert len(agent_b.reply_calls) == 1


@pytest.mark.asyncio
async def test_max_turns_enforcement() -> None:
    """Loop stops at max_turns even if router never terminates."""
    agent_a = FakeConversationalAgent("a")
    # Router always selects agent-a, never terminates
    always_a = RouterDecision(
        current_state_summary="looping",
        missing_information="still need more",
        next_agent="a",
        stagnation_risk=0.1,
    )
    router = FakeRouter([always_a] * 100)  # More than enough

    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)
    runtime = AgenticLoopRuntime(
        runner=runner,
        agent_registry={"a": agent_a, "router": router},
    )

    plan = AgenticLoopPlan(
        participants=["a"],
        router_agent="router",
        policy=ConversationPolicy(max_turns=3),
        initial_message="go",
    )
    ctx = _make_context()
    result = await runtime.run(agents=[], context=ctx, plan=plan)

    assert result.status == "finished"
    assert len(agent_a.reply_calls) == 3
    assert result.metadata.get("stop_reason") == "max_turns"


@pytest.mark.asyncio
async def test_stagnation_detection_stops_loop() -> None:
    """Loop stops when stagnation is detected."""
    agent_a = FakeConversationalAgent("a")
    # Same decision repeated => stagnation
    stagnant = RouterDecision(
        current_state_summary="stuck",
        missing_information="same info",
        next_agent="a",
        stagnation_risk=0.8,
    )
    router = FakeRouter([stagnant] * 20)

    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)
    runtime = AgenticLoopRuntime(
        runner=runner,
        agent_registry={"a": agent_a, "router": router},
    )

    plan = AgenticLoopPlan(
        participants=["a"],
        router_agent="router",
        policy=ConversationPolicy(max_turns=10, stagnation_window=2),
        initial_message="go",
    )
    ctx = _make_context()
    result = await runtime.run(agents=[], context=ctx, plan=plan)

    assert result.status == "finished"
    assert result.metadata.get("stop_reason") == "stagnation"
    # Should have stopped after stagnation_window turns (2)
    assert len(agent_a.reply_calls) <= 3  # At most window + 1


@pytest.mark.asyncio
async def test_router_terminates_immediately() -> None:
    """Router says terminate on first call, no agents invoked."""
    agent_a = FakeConversationalAgent("a")
    router = FakeRouter([
        RouterDecision(
            current_state_summary="done",
            missing_information="none",
            terminate=True,
            stagnation_risk=0.0,
        ),
    ])

    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)
    runtime = AgenticLoopRuntime(
        runner=runner,
        agent_registry={"a": agent_a, "router": router},
    )

    plan = AgenticLoopPlan(
        participants=["a"],
        router_agent="router",
    )
    ctx = _make_context()
    result = await runtime.run(agents=[], context=ctx, plan=plan)

    assert result.status == "finished"
    assert len(agent_a.reply_calls) == 0
    assert result.metadata.get("stop_reason") == "router_terminated"


@pytest.mark.asyncio
async def test_unknown_participant_returns_error() -> None:
    """Referencing an unknown participant returns failed."""
    router = FakeRouter([])
    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)
    runtime = AgenticLoopRuntime(
        runner=runner,
        agent_registry={"router": router},
    )

    plan = AgenticLoopPlan(
        participants=["nonexistent"],
        router_agent="router",
    )
    ctx = _make_context()
    result = await runtime.run(agents=[], context=ctx, plan=plan)

    assert result.status == "failed"
    assert "nonexistent" in result.error


@pytest.mark.asyncio
async def test_unknown_router_returns_error() -> None:
    """Referencing an unknown router returns failed."""
    agent_a = FakeConversationalAgent("a")
    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)
    runtime = AgenticLoopRuntime(
        runner=runner,
        agent_registry={"a": agent_a},
    )

    plan = AgenticLoopPlan(
        participants=["a"],
        router_agent="missing_router",
    )
    ctx = _make_context()
    result = await runtime.run(agents=[], context=ctx, plan=plan)

    assert result.status == "failed"
    assert "missing_router" in result.error


@pytest.mark.asyncio
async def test_agent_failure_returns_error() -> None:
    """When an agent raises, the loop returns failed."""
    failing = FailingConversationalAgent()
    router = FakeRouter([
        RouterDecision(
            current_state_summary="start",
            missing_information="need input",
            next_agent="fail",
            stagnation_risk=0.0,
        ),
    ])

    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)
    runtime = AgenticLoopRuntime(
        runner=runner,
        agent_registry={"fail": failing, "router": router},
    )

    plan = AgenticLoopPlan(
        participants=["fail"],
        router_agent="router",
        initial_message="go",
    )
    ctx = _make_context()
    result = await runtime.run(agents=[], context=ctx, plan=plan)

    assert result.status == "failed"
    assert "agent crashed" in result.error


@pytest.mark.asyncio
async def test_events_emitted_during_loop() -> None:
    """Verify lifecycle events are emitted."""
    agent_a = FakeConversationalAgent("a")
    router = FakeRouter([
        RouterDecision(
            current_state_summary="start",
            missing_information="need a",
            next_agent="a",
            stagnation_risk=0.0,
        ),
        RouterDecision(
            current_state_summary="done",
            missing_information="none",
            terminate=True,
            stagnation_risk=0.0,
        ),
    ])

    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)
    runtime = AgenticLoopRuntime(
        runner=runner,
        agent_registry={"a": agent_a, "router": router},
    )

    plan = AgenticLoopPlan(
        participants=["a"],
        router_agent="router",
        initial_message="go",
    )
    ctx = _make_context()
    await runtime.run(agents=[], context=ctx, plan=plan)

    event_types = [e.type for e in sink.events]
    assert "agentic_loop_started" in event_types
    assert "router_decision_emitted" in event_types
    assert "agent_reply_recorded" in event_types
    assert "agentic_loop_stopped" in event_types


@pytest.mark.asyncio
async def test_conversation_history_passed_to_router() -> None:
    """Router receives the growing conversation history."""
    call_log: list[list[dict[str, str]]] = []

    class SpyRouter:
        async def route(self, conversation_history: list[dict[str, str]]) -> RouterDecision:
            call_log.append(list(conversation_history))
            if len(conversation_history) >= 2:
                return RouterDecision(
                    current_state_summary="done",
                    missing_information="none",
                    terminate=True,
                    stagnation_risk=0.0,
                )
            return RouterDecision(
                current_state_summary="continue",
                missing_information="more",
                next_agent="a",
                stagnation_risk=0.0,
            )

    agent_a = FakeConversationalAgent("a")

    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)
    runtime = AgenticLoopRuntime(
        runner=runner,
        agent_registry={"a": agent_a, "router": SpyRouter()},
    )

    plan = AgenticLoopPlan(
        participants=["a"],
        router_agent="router",
        initial_message="start",
    )
    ctx = _make_context()
    await runtime.run(agents=[], context=ctx, plan=plan)

    # First call: router gets initial message only
    assert len(call_log[0]) == 1
    assert call_log[0][0]["content"] == "start"
    # Second call: router gets initial + agent reply
    assert len(call_log[1]) == 2


@pytest.mark.asyncio
async def test_result_contains_conversation_history() -> None:
    """RunResult output contains the full conversation."""
    agent_a = FakeConversationalAgent("a")
    router = FakeRouter([
        RouterDecision(
            current_state_summary="start",
            missing_information="need a",
            next_agent="a",
            stagnation_risk=0.0,
        ),
        RouterDecision(
            current_state_summary="done",
            missing_information="none",
            terminate=True,
            stagnation_risk=0.0,
        ),
    ])

    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)
    runtime = AgenticLoopRuntime(
        runner=runner,
        agent_registry={"a": agent_a, "router": router},
    )

    plan = AgenticLoopPlan(
        participants=["a"],
        router_agent="router",
        initial_message="hello",
    )
    ctx = _make_context()
    result = await runtime.run(agents=[], context=ctx, plan=plan)

    assert result.status == "finished"
    # Output should be the conversation history
    assert isinstance(result.output, list)
    assert len(result.output) >= 2  # initial message + agent reply
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/core/runtime/test_agentic_loop_runtime_full.py -v`

**Expected output:**
```
FAILED - ModuleNotFoundError: No module named 'miniautogen.core.runtime.agentic_loop_runtime'
```

**Step 3: Implement AgenticLoopRuntime**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/runtime/agentic_loop_runtime.py`:

```python
"""AgenticLoopRuntime — contained conversational loop coordination mode.

Implements a router-driven conversation where:
1. A router agent examines conversation history and picks the next speaker
2. The selected agent replies
3. The loop continues until: router terminates, max_turns, or stagnation

This is TRANSVERSAL (usable within both workflow and deliberation contexts)
but NOT SOVEREIGN (does not control global execution).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from miniautogen.core.contracts.agentic_loop import (
    AgenticLoopState,
    ConversationPolicy,
    RouterDecision,
)
from miniautogen.core.contracts.coordination import (
    AgenticLoopPlan,
    CoordinationKind,
)
from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.run_result import RunResult
from miniautogen.core.events.types import EventType
from miniautogen.core.runtime.agentic_loop import detect_stagnation, should_stop_loop
from miniautogen.core.runtime.pipeline_runner import PipelineRunner
from miniautogen.observability import get_logger

_SCOPE = "agentic_loop_runtime"


class AgenticLoopRuntime:
    """Coordination mode for contained conversational loops.

    The router agent decides who speaks next. The loop enforces turn limits,
    stagnation detection, and emits events for observability.
    """

    kind: CoordinationKind = CoordinationKind.AGENTIC_LOOP

    def __init__(
        self,
        runner: PipelineRunner,
        agent_registry: dict[str, Any] | None = None,
    ) -> None:
        self._runner = runner
        self._registry: dict[str, Any] = agent_registry or {}
        self._logger = get_logger(__name__)

    async def run(
        self,
        agents: list[Any],
        context: RunContext,
        plan: AgenticLoopPlan,
    ) -> RunResult:
        """Execute an agentic loop and return a RunResult."""
        correlation_id = context.correlation_id or str(uuid4())
        logger = self._logger.bind(
            run_id=context.run_id,
            correlation_id=correlation_id,
            scope=_SCOPE,
        )

        # --- Validate ---
        validation_error = self._validate_plan(plan)
        if validation_error is not None:
            logger.error("agentic_loop_validation_failed", error=validation_error)
            return RunResult(
                run_id=context.run_id,
                status="failed",
                error=validation_error,
            )

        # --- Emit started ---
        await self._emit(
            event_type=EventType.AGENTIC_LOOP_STARTED.value,
            run_id=context.run_id,
            correlation_id=correlation_id,
            payload={
                "participants": plan.participants,
                "router": plan.router_agent,
                "max_turns": plan.policy.max_turns,
            },
        )
        logger.info(
            "agentic_loop_started",
            participants=plan.participants,
            router=plan.router_agent,
        )

        # --- Initialize conversation ---
        conversation_history: list[dict[str, str]] = []
        if plan.initial_message:
            conversation_history.append({
                "sender": "system",
                "content": plan.initial_message,
            })

        router_agent = self._registry[plan.router_agent]
        state = AgenticLoopState()
        routing_history: list[RouterDecision] = []
        stop_reason: str | None = None

        # --- Main loop ---
        for turn in range(plan.policy.max_turns):
            # Check max_turns via helper
            check_state = AgenticLoopState(
                active_agent=state.active_agent,
                turn_count=turn,
            )
            should_stop, reason = should_stop_loop(check_state, plan.policy)
            if should_stop:
                stop_reason = reason
                logger.info("loop_stopped", reason=reason, turn=turn)
                break

            # Ask router for next agent
            try:
                decision = await router_agent.route(conversation_history)
            except Exception as exc:
                error_msg = f"Router agent failed: {exc}"
                logger.error("router_failed", error=str(exc))
                await self._emit(
                    event_type=EventType.AGENTIC_LOOP_STOPPED.value,
                    run_id=context.run_id,
                    correlation_id=correlation_id,
                    payload={"error": error_msg},
                )
                return RunResult(
                    run_id=context.run_id,
                    status="failed",
                    error=error_msg,
                )

            routing_history.append(decision)

            await self._emit(
                event_type=EventType.ROUTER_DECISION_EMITTED.value,
                run_id=context.run_id,
                correlation_id=correlation_id,
                payload={
                    "next_agent": decision.next_agent,
                    "terminate": decision.terminate,
                    "turn": turn,
                },
            )

            # Check termination
            if decision.terminate:
                stop_reason = "router_terminated"
                logger.info("router_terminated", turn=turn)
                break

            # Check stagnation
            if detect_stagnation(routing_history, plan.policy.stagnation_window):
                stop_reason = "stagnation"
                logger.info("stagnation_detected", turn=turn)
                await self._emit(
                    event_type=EventType.STAGNATION_DETECTED.value,
                    run_id=context.run_id,
                    correlation_id=correlation_id,
                    payload={"turn": turn, "window": plan.policy.stagnation_window},
                )
                break

            # Invoke selected agent
            agent_id = decision.next_agent
            agent = self._registry.get(agent_id)
            if agent is None:
                error_msg = f"Router selected unknown agent '{agent_id}'"
                logger.error("agent_not_found", agent_id=agent_id)
                return RunResult(
                    run_id=context.run_id,
                    status="failed",
                    error=error_msg,
                )

            last_message = conversation_history[-1]["content"] if conversation_history else ""
            agent_context = {
                "turn": turn,
                "run_id": context.run_id,
                "conversation_length": len(conversation_history),
            }

            try:
                reply_text = await agent.reply(last_message, agent_context)
            except Exception as exc:
                error_msg = f"Agent '{agent_id}' failed: {exc}"
                logger.error("agent_failed", agent_id=agent_id, error=str(exc))
                await self._emit(
                    event_type=EventType.AGENTIC_LOOP_STOPPED.value,
                    run_id=context.run_id,
                    correlation_id=correlation_id,
                    payload={"error": error_msg},
                )
                return RunResult(
                    run_id=context.run_id,
                    status="failed",
                    error=error_msg,
                )

            conversation_history.append({
                "sender": agent_id,
                "content": reply_text,
            })

            await self._emit(
                event_type=EventType.AGENT_REPLY_RECORDED.value,
                run_id=context.run_id,
                correlation_id=correlation_id,
                payload={"agent": agent_id, "turn": turn},
            )

            state = AgenticLoopState(
                active_agent=agent_id,
                turn_count=turn + 1,
                accepted_output=reply_text,
            )

            logger.info(
                "turn_completed",
                agent=agent_id,
                turn=turn,
            )

        # If we exhausted the loop without setting stop_reason
        if stop_reason is None:
            stop_reason = "max_turns"

        # --- Emit stopped ---
        await self._emit(
            event_type=EventType.AGENTIC_LOOP_STOPPED.value,
            run_id=context.run_id,
            correlation_id=correlation_id,
            payload={
                "stop_reason": stop_reason,
                "turns_completed": state.turn_count,
            },
        )
        logger.info(
            "agentic_loop_finished",
            stop_reason=stop_reason,
            turns=state.turn_count,
        )

        return RunResult(
            run_id=context.run_id,
            status="finished",
            output=conversation_history,
            metadata={
                "stop_reason": stop_reason,
                "turns_completed": state.turn_count,
                "last_agent": state.active_agent,
            },
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_plan(self, plan: AgenticLoopPlan) -> str | None:
        """Return an error message if the plan is invalid."""
        if plan.router_agent not in self._registry:
            return f"Router agent '{plan.router_agent}' not found in registry"
        missing = [p for p in plan.participants if p not in self._registry]
        if missing:
            return f"Participants not found in registry: {', '.join(missing)}"
        return None

    async def _emit(
        self,
        *,
        event_type: str,
        run_id: str,
        correlation_id: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        await self._runner.event_sink.publish(
            ExecutionEvent(
                type=event_type,
                timestamp=datetime.now(timezone.utc),
                run_id=run_id,
                correlation_id=correlation_id,
                scope=_SCOPE,
                payload=payload or {},
            )
        )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/core/runtime/test_agentic_loop_runtime_full.py -v`

**Expected output:** All 11 tests PASSED.

**Step 5: Run all tests**

Run: `pytest -x -q`

**Expected output:** All tests pass.

**Step 6: Commit**

```bash
git add miniautogen/core/runtime/agentic_loop_runtime.py tests/core/runtime/test_agentic_loop_runtime_full.py
git commit -m "feat: implement AgenticLoopRuntime coordination mode (Phase 4)"
```

**If Task Fails:**

1. **`should_stop_loop` is checked before turn 0:** The helper checks `state.turn_count >= policy.max_turns`. Since we start with `turn_count=0` and `max_turns=3`, this won't trigger at turn 0. If the test for `max_turns=3` expects exactly 3 agent replies, verify the loop runs turns 0, 1, 2 (3 iterations).

2. **Stagnation detection timing:** `detect_stagnation(history, window=2)` returns True when the last `window` routing decisions have the same `next_agent` and `missing_information`. The test expects the loop to stop after at most `window + 1` turns. Adjust the expected bound if needed.

3. **Router interface mismatch:** The runtime expects `router.route(conversation_history) -> RouterDecision`. If the test fake has a different signature, align them.

4. **Rollback:** `rm miniautogen/core/runtime/agentic_loop_runtime.py`

---

### Task 4.4: Export AgenticLoopRuntime from Runtime Package

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/runtime/__init__.py`

**Prerequisites:**
- Task 4.3 complete

**Step 1: Write the failing test**

Create file `/Users/brunocapelao/Projects/miniAutoGen/tests/core/runtime/test_agentic_loop_runtime_export.py`:

```python
"""Test AgenticLoopRuntime is exported from runtime package."""


def test_agentic_loop_runtime_importable() -> None:
    from miniautogen.core.runtime import AgenticLoopRuntime
    assert AgenticLoopRuntime is not None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/core/runtime/test_agentic_loop_runtime_export.py -v`

**Expected output:**
```
FAILED - ImportError: cannot import name 'AgenticLoopRuntime'
```

**Step 3: Update `__init__.py`**

In `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/runtime/__init__.py`, add:

```python
from .agentic_loop_runtime import AgenticLoopRuntime
```

And add `"AgenticLoopRuntime"` to `__all__`.

**Step 4: Run tests**

Run: `pytest tests/core/runtime/test_agentic_loop_runtime_export.py -v && pytest -x -q`

**Expected output:** All pass.

**Step 5: Commit**

```bash
git add miniautogen/core/runtime/__init__.py tests/core/runtime/test_agentic_loop_runtime_export.py
git commit -m "feat: export AgenticLoopRuntime from runtime package"
```

---

### Task 4.5: Update AgenticLoopComponent Shell to Delegate to Runtime

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/pipeline/components/agentic_loop.py`

**Prerequisites:**
- Task 4.4 complete

**Step 1: Write the failing test**

Create file `/Users/brunocapelao/Projects/miniAutoGen/tests/pipeline/test_agentic_loop_component_runtime.py`:

```python
"""Test AgenticLoopComponent delegates to AgenticLoopRuntime."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from miniautogen.core.contracts.agentic_loop import (
    ConversationPolicy,
    RouterDecision,
)
from miniautogen.core.contracts.coordination import AgenticLoopPlan
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.runtime.pipeline_runner import PipelineRunner
from miniautogen.pipeline.components.agentic_loop import AgenticLoopComponent


class FakeRouter:
    async def route(self, conversation_history: list[dict[str, str]]) -> RouterDecision:
        return RouterDecision(
            current_state_summary="done",
            missing_information="none",
            terminate=True,
            stagnation_risk=0.0,
        )


class FakeAgent:
    async def reply(self, message: str, context: dict[str, Any]) -> str:
        return "ok"


@pytest.mark.asyncio
async def test_component_process_executes_loop() -> None:
    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)
    registry = {"a": FakeAgent(), "router": FakeRouter()}

    component = AgenticLoopComponent(
        policy=ConversationPolicy(max_turns=5),
        runner=runner,
        agent_registry=registry,
    )

    state = {
        "plan": AgenticLoopPlan(
            participants=["a"],
            router_agent="router",
            initial_message="hi",
        ),
        "context": RunContext(
            run_id="r1",
            started_at=datetime.now(timezone.utc),
            correlation_id="c1",
        ),
    }

    result = await component.process(state)
    assert result.status == "finished"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/pipeline/test_agentic_loop_component_runtime.py -v`

**Expected output:**
```
FAILED - TypeError: AgenticLoopComponent.__init__() got an unexpected keyword argument 'runner'
```

**Step 3: Update AgenticLoopComponent**

Replace the contents of `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/pipeline/components/agentic_loop.py`:

```python
"""AgenticLoopComponent — pipeline component wrapping AgenticLoopRuntime.

This component is TRANSVERSAL: it can be embedded within a workflow step
or used standalone. It delegates to AgenticLoopRuntime for the actual
conversation loop execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from miniautogen.core.contracts.agentic_loop import ConversationPolicy
from miniautogen.core.contracts.coordination import AgenticLoopPlan
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.run_result import RunResult
from miniautogen.core.runtime.agentic_loop_runtime import AgenticLoopRuntime
from miniautogen.core.runtime.pipeline_runner import PipelineRunner


@dataclass
class AgenticLoopComponent:
    """Pipeline component that runs a contained agentic loop.

    When ``runner`` and ``agent_registry`` are provided, the component
    can execute loops via ``process()``.  Without them, it acts as a
    configuration holder (backward-compatible with existing usage).
    """

    policy: ConversationPolicy
    runner: PipelineRunner | None = None
    agent_registry: dict[str, Any] = field(default_factory=dict)

    async def process(self, state: Any) -> RunResult:
        """Execute an agentic loop from pipeline state.

        Expects ``state`` to be a dict with:
        - ``plan``: AgenticLoopPlan
        - ``context``: RunContext
        """
        if self.runner is None:
            raise RuntimeError(
                "AgenticLoopComponent requires a PipelineRunner to execute. "
                "Provide runner= at construction time."
            )

        plan: AgenticLoopPlan = state["plan"]
        context: RunContext = state["context"]

        # Override plan policy with component policy
        plan = plan.model_copy(update={"policy": self.policy})

        runtime = AgenticLoopRuntime(
            runner=self.runner,
            agent_registry=self.agent_registry,
        )

        return await runtime.run(agents=[], context=context, plan=plan)
```

**Step 4: Run new test AND existing test**

Run: `pytest tests/pipeline/test_agentic_loop_component_runtime.py tests/pipeline/test_agentic_loop_component.py -v`

**Expected output:** All PASSED (both old and new tests).

**Step 5: Run all tests**

Run: `pytest -x -q`

**Expected output:** All tests pass.

**Step 6: Commit**

```bash
git add miniautogen/pipeline/components/agentic_loop.py tests/pipeline/test_agentic_loop_component_runtime.py
git commit -m "feat: wire AgenticLoopComponent to AgenticLoopRuntime"
```

**If Task Fails:**

1. **Old test breaks:** The old test does `AgenticLoopComponent(policy=...)`. The new dataclass has `runner=None` and `agent_registry={}` as defaults, so the old constructor call should still work.
2. **Rollback:** `git checkout -- miniautogen/pipeline/components/agentic_loop.py`

---

### Task 4.6: Code Review Checkpoint (Phase 4)

1. **Dispatch all 3 reviewers in parallel:**
   - REQUIRED SUB-SKILL: Use requesting-code-review
   - Review all Phase 4 changes (the core deliverable)

2. **Handle findings by severity** as described in Task 1.3.

3. **Proceed only when:** Zero Critical/High/Medium issues remain.

---

## Phase 5: SubrunRequest Contract (GAP 5)

### Task 5.1: Create SubrunRequest Contract

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/contracts/subrun.py`

**Prerequisites:**
- Phase 4 complete

**Step 1: Write the failing test**

Create file `/Users/brunocapelao/Projects/miniAutoGen/tests/core/contracts/test_subrun.py`:

```python
"""Tests for SubrunRequest contract."""

from miniautogen.core.contracts.subrun import SubrunRequest
from miniautogen.core.contracts.coordination import (
    CoordinationKind,
    DeliberationPlan,
    WorkflowPlan,
    WorkflowStep,
)


def test_subrun_request_with_workflow_plan() -> None:
    plan = WorkflowPlan(
        steps=[WorkflowStep(component_name="s1", agent_id="a")]
    )
    req = SubrunRequest(
        kind=CoordinationKind.WORKFLOW,
        plan=plan,
        label="sub-workflow",
    )
    assert req.kind == CoordinationKind.WORKFLOW
    assert req.label == "sub-workflow"
    assert isinstance(req.plan, WorkflowPlan)


def test_subrun_request_with_deliberation_plan() -> None:
    plan = DeliberationPlan(
        topic="sub-topic",
        participants=["a"],
        max_rounds=1,
    )
    req = SubrunRequest(
        kind=CoordinationKind.DELIBERATION,
        plan=plan,
        label="sub-deliberation",
    )
    assert req.kind == CoordinationKind.DELIBERATION


def test_subrun_request_defaults() -> None:
    plan = WorkflowPlan(
        steps=[WorkflowStep(component_name="s1", agent_id="a")]
    )
    req = SubrunRequest(
        kind=CoordinationKind.WORKFLOW,
        plan=plan,
    )
    assert req.label == ""
    assert req.input_payload is None
    assert req.metadata == {}


def test_subrun_request_with_input_payload() -> None:
    plan = WorkflowPlan(
        steps=[WorkflowStep(component_name="s1", agent_id="a")]
    )
    req = SubrunRequest(
        kind=CoordinationKind.WORKFLOW,
        plan=plan,
        input_payload={"key": "value"},
    )
    assert req.input_payload == {"key": "value"}
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/core/contracts/test_subrun.py -v`

**Expected output:**
```
FAILED - ModuleNotFoundError: No module named 'miniautogen.core.contracts.subrun'
```

**Step 3: Implement SubrunRequest**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/contracts/subrun.py`:

```python
"""SubrunRequest contract — enables nested execution within composition.

A SubrunRequest is emitted by a coordination mode step when it needs to
trigger a sub-execution (e.g., a workflow step triggers a sub-deliberation).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from miniautogen.core.contracts.coordination import CoordinationKind, CoordinationPlan


class SubrunRequest(BaseModel):
    """Request to execute a nested coordination run.

    Attributes:
        kind: Which coordination mode to use for the subrun.
        plan: The typed plan for the subrun.
        label: Descriptive label for traceability.
        input_payload: Optional input data for the subrun.
        metadata: Additional metadata for the subrun context.
    """

    kind: CoordinationKind
    plan: CoordinationPlan
    label: str = ""
    input_payload: Any = None
    metadata: dict[str, Any] = Field(default_factory=dict)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/core/contracts/test_subrun.py -v`

**Expected output:** All 4 PASSED.

**Step 5: Run all tests**

Run: `pytest -x -q`

**Expected output:** All tests pass.

**Step 6: Commit**

```bash
git add miniautogen/core/contracts/subrun.py tests/core/contracts/test_subrun.py
git commit -m "feat: add SubrunRequest contract for nested coordination runs"
```

---

### Task 5.2: Export SubrunRequest from Contracts Package

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/contracts/__init__.py`

**Prerequisites:**
- Task 5.1 complete

**Step 1: Add import and export**

In `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/contracts/__init__.py`, add:

```python
from .subrun import SubrunRequest
```

And add `"SubrunRequest"` to `__all__`.

**Step 2: Run all tests**

Run: `pytest -x -q`

**Expected output:** All tests pass.

**Step 3: Commit**

```bash
git add miniautogen/core/contracts/__init__.py
git commit -m "feat: export SubrunRequest from contracts package"
```

---

## Phase 6: Policy Enforcement (GAP 4)

### Task 6.1: Implement BudgetPolicy Enforcement

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/policies/budget.py`

**Prerequisites:**
- Phase 5 complete

**Step 1: Write the failing test**

Create file `/Users/brunocapelao/Projects/miniAutoGen/tests/policies/test_budget_enforcement.py`:

```python
"""Tests for BudgetPolicy enforcement."""

import pytest

from miniautogen.policies.budget import BudgetPolicy, BudgetTracker, BudgetExceededError


def test_budget_tracker_initial_cost_is_zero() -> None:
    tracker = BudgetTracker(policy=BudgetPolicy(max_cost=10.0))
    assert tracker.current_cost == 0.0


def test_budget_tracker_record_cost() -> None:
    tracker = BudgetTracker(policy=BudgetPolicy(max_cost=10.0))
    tracker.record_cost(3.5)
    assert tracker.current_cost == 3.5
    tracker.record_cost(2.0)
    assert tracker.current_cost == 5.5


def test_budget_tracker_raises_when_exceeded() -> None:
    tracker = BudgetTracker(policy=BudgetPolicy(max_cost=5.0))
    tracker.record_cost(4.0)
    with pytest.raises(BudgetExceededError, match="Budget exceeded"):
        tracker.record_cost(2.0)


def test_budget_tracker_exact_limit_does_not_raise() -> None:
    tracker = BudgetTracker(policy=BudgetPolicy(max_cost=5.0))
    tracker.record_cost(5.0)  # Exactly at limit
    assert tracker.current_cost == 5.0


def test_budget_tracker_no_limit() -> None:
    tracker = BudgetTracker(policy=BudgetPolicy(max_cost=None))
    tracker.record_cost(999999.0)
    assert tracker.current_cost == 999999.0


def test_budget_tracker_remaining() -> None:
    tracker = BudgetTracker(policy=BudgetPolicy(max_cost=10.0))
    tracker.record_cost(3.0)
    assert tracker.remaining == 7.0


def test_budget_tracker_remaining_no_limit() -> None:
    tracker = BudgetTracker(policy=BudgetPolicy(max_cost=None))
    assert tracker.remaining is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/policies/test_budget_enforcement.py -v`

**Expected output:**
```
FAILED - ImportError: cannot import name 'BudgetTracker'
```

**Step 3: Implement BudgetTracker**

Replace contents of `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/policies/budget.py`:

```python
"""Budget policy and enforcement for cost tracking."""

from dataclasses import dataclass, field


class BudgetExceededError(RuntimeError):
    """Raised when an operation would exceed the budget limit."""

    pass


@dataclass(frozen=True)
class BudgetPolicy:
    """Immutable budget configuration."""

    max_cost: float | None = None


@dataclass
class BudgetTracker:
    """Mutable tracker that enforces a BudgetPolicy.

    Usage:
        tracker = BudgetTracker(policy=BudgetPolicy(max_cost=10.0))
        tracker.record_cost(3.5)  # OK
        tracker.record_cost(8.0)  # Raises BudgetExceededError
    """

    policy: BudgetPolicy
    current_cost: float = field(default=0.0, init=False)

    def record_cost(self, cost: float) -> None:
        """Record a cost increment. Raises BudgetExceededError if limit exceeded."""
        new_cost = self.current_cost + cost
        if self.policy.max_cost is not None and new_cost > self.policy.max_cost:
            raise BudgetExceededError(
                f"Budget exceeded: {new_cost:.2f} > {self.policy.max_cost:.2f}"
            )
        self.current_cost = new_cost

    @property
    def remaining(self) -> float | None:
        """Return remaining budget, or None if unlimited."""
        if self.policy.max_cost is None:
            return None
        return self.policy.max_cost - self.current_cost
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/policies/test_budget_enforcement.py -v`

**Expected output:** All 7 PASSED.

**Step 5: Run all tests (including existing policy tests)**

Run: `pytest -x -q`

**Expected output:** All tests pass. The existing `BudgetPolicy` constructor is unchanged, so `test_policy_categories.py` should still pass.

**Step 6: Commit**

```bash
git add miniautogen/policies/budget.py tests/policies/test_budget_enforcement.py
git commit -m "feat: implement BudgetTracker for budget policy enforcement"
```

---

### Task 6.2: Implement ValidationPolicy Enforcement

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/policies/validation.py`

**Prerequisites:**
- Task 6.1 complete

**Step 1: Write the failing test**

Create file `/Users/brunocapelao/Projects/miniAutoGen/tests/policies/test_validation_enforcement.py`:

```python
"""Tests for ValidationPolicy enforcement."""

from typing import Any

import pytest

from miniautogen.policies.validation import (
    ValidationPolicy,
    ValidationHook,
    validate_input,
    validate_output,
    ValidationError as PolicyValidationError,
)


def test_validate_input_passes_when_hook_accepts() -> None:
    def check(data: Any) -> None:
        pass  # No error means valid

    policy = ValidationPolicy(enabled=True)
    validate_input(data={"key": "value"}, hooks=[check], policy=policy)


def test_validate_input_raises_when_hook_rejects() -> None:
    def check(data: Any) -> None:
        raise ValueError("bad input")

    policy = ValidationPolicy(enabled=True)
    with pytest.raises(PolicyValidationError, match="bad input"):
        validate_input(data={"key": "value"}, hooks=[check], policy=policy)


def test_validate_input_skipped_when_disabled() -> None:
    def check(data: Any) -> None:
        raise ValueError("should not run")

    policy = ValidationPolicy(enabled=False)
    # Should not raise because validation is disabled
    validate_input(data={"key": "value"}, hooks=[check], policy=policy)


def test_validate_output_passes() -> None:
    def check(data: Any) -> None:
        if not isinstance(data, str):
            raise ValueError("must be string")

    policy = ValidationPolicy(enabled=True)
    validate_output(data="hello", hooks=[check], policy=policy)


def test_validate_output_raises() -> None:
    def check(data: Any) -> None:
        if not isinstance(data, str):
            raise ValueError("must be string")

    policy = ValidationPolicy(enabled=True)
    with pytest.raises(PolicyValidationError, match="must be string"):
        validate_output(data=123, hooks=[check], policy=policy)


def test_multiple_hooks_all_run() -> None:
    call_log: list[str] = []

    def hook_a(data: Any) -> None:
        call_log.append("a")

    def hook_b(data: Any) -> None:
        call_log.append("b")

    policy = ValidationPolicy(enabled=True)
    validate_input(data="x", hooks=[hook_a, hook_b], policy=policy)
    assert call_log == ["a", "b"]


def test_multiple_hooks_first_failure_stops() -> None:
    def hook_a(data: Any) -> None:
        raise ValueError("fail in a")

    def hook_b(data: Any) -> None:
        pass  # Should never run

    policy = ValidationPolicy(enabled=True)
    with pytest.raises(PolicyValidationError, match="fail in a"):
        validate_input(data="x", hooks=[hook_a, hook_b], policy=policy)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/policies/test_validation_enforcement.py -v`

**Expected output:**
```
FAILED - ImportError: cannot import name 'ValidationHook'
```

**Step 3: Implement validation enforcement**

Replace contents of `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/policies/validation.py`:

```python
"""Validation policy and enforcement hooks."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# Type alias for validation hook functions
ValidationHook = Callable[[Any], None]


class ValidationError(RuntimeError):
    """Raised when input/output validation fails."""

    pass


@dataclass(frozen=True)
class ValidationPolicy:
    """Immutable validation configuration."""

    enabled: bool = True


def validate_input(
    *,
    data: Any,
    hooks: list[ValidationHook],
    policy: ValidationPolicy,
) -> None:
    """Run input validation hooks if policy is enabled.

    Each hook receives the data and should raise ValueError if invalid.
    Raises ValidationError wrapping the first hook failure.
    """
    if not policy.enabled:
        return
    for hook in hooks:
        try:
            hook(data)
        except (ValueError, TypeError) as exc:
            raise ValidationError(str(exc)) from exc


def validate_output(
    *,
    data: Any,
    hooks: list[ValidationHook],
    policy: ValidationPolicy,
) -> None:
    """Run output validation hooks if policy is enabled.

    Same semantics as validate_input but for output data.
    """
    if not policy.enabled:
        return
    for hook in hooks:
        try:
            hook(data)
        except (ValueError, TypeError) as exc:
            raise ValidationError(str(exc)) from exc
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/policies/test_validation_enforcement.py -v`

**Expected output:** All 7 PASSED.

**Step 5: Run all tests**

Run: `pytest -x -q`

**Expected output:** All tests pass.

**Step 6: Commit**

```bash
git add miniautogen/policies/validation.py tests/policies/test_validation_enforcement.py
git commit -m "feat: implement ValidationPolicy enforcement with hooks"
```

---

### Task 6.3: Implement PermissionPolicy Enforcement

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/policies/permission.py`

**Prerequisites:**
- Task 6.2 complete

**Step 1: Write the failing test**

Create file `/Users/brunocapelao/Projects/miniAutoGen/tests/policies/test_permission_enforcement.py`:

```python
"""Tests for PermissionPolicy enforcement."""

import pytest

from miniautogen.policies.permission import (
    PermissionPolicy,
    check_permission,
    PermissionDeniedError,
)


def test_permission_allowed_when_action_in_list() -> None:
    policy = PermissionPolicy(allowed_actions=("read", "write"))
    check_permission(action="read", policy=policy)  # Should not raise


def test_permission_denied_when_action_not_in_list() -> None:
    policy = PermissionPolicy(allowed_actions=("read",))
    with pytest.raises(PermissionDeniedError, match="write"):
        check_permission(action="write", policy=policy)


def test_permission_empty_allows_nothing() -> None:
    policy = PermissionPolicy(allowed_actions=())
    with pytest.raises(PermissionDeniedError):
        check_permission(action="read", policy=policy)


def test_permission_with_agent_id_in_message() -> None:
    policy = PermissionPolicy(allowed_actions=("read",))
    with pytest.raises(PermissionDeniedError, match="agent-x"):
        check_permission(action="delete", policy=policy, agent_id="agent-x")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/policies/test_permission_enforcement.py -v`

**Expected output:**
```
FAILED - ImportError: cannot import name 'check_permission'
```

**Step 3: Implement permission enforcement**

Replace contents of `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/policies/permission.py`:

```python
"""Permission policy and enforcement for agent action gating."""

from __future__ import annotations

from dataclasses import dataclass


class PermissionDeniedError(RuntimeError):
    """Raised when an agent attempts a disallowed action."""

    pass


@dataclass(frozen=True)
class PermissionPolicy:
    """Immutable permission configuration.

    Attributes:
        allowed_actions: Tuple of action names that are permitted.
                         An empty tuple means nothing is allowed.
    """

    allowed_actions: tuple[str, ...] = ()


def check_permission(
    *,
    action: str,
    policy: PermissionPolicy,
    agent_id: str | None = None,
) -> None:
    """Check if an action is allowed by the policy.

    Raises PermissionDeniedError if the action is not in allowed_actions.
    """
    if action not in policy.allowed_actions:
        agent_info = f" by agent '{agent_id}'" if agent_id else ""
        raise PermissionDeniedError(
            f"Action '{action}' not permitted{agent_info}. "
            f"Allowed: {policy.allowed_actions}"
        )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/policies/test_permission_enforcement.py -v`

**Expected output:** All 4 PASSED.

**Step 5: Run all tests**

Run: `pytest -x -q`

**Expected output:** All tests pass.

**Step 6: Commit**

```bash
git add miniautogen/policies/permission.py tests/policies/test_permission_enforcement.py
git commit -m "feat: implement PermissionPolicy enforcement with action gating"
```

---

### Task 6.4: Update Policy Package Exports

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/policies/__init__.py`

**Prerequisites:**
- Tasks 6.1-6.3 complete

**Step 1: Update `__init__.py`**

Replace contents of `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/policies/__init__.py`:

```python
from miniautogen.policies.budget import BudgetExceededError, BudgetPolicy, BudgetTracker
from miniautogen.policies.execution import ExecutionPolicy
from miniautogen.policies.permission import PermissionDeniedError, PermissionPolicy, check_permission
from miniautogen.policies.retry import RetryPolicy, build_retrying_call
from miniautogen.policies.validation import (
    ValidationError,
    ValidationHook,
    ValidationPolicy,
    validate_input,
    validate_output,
)

__all__ = [
    "BudgetExceededError",
    "BudgetPolicy",
    "BudgetTracker",
    "ExecutionPolicy",
    "PermissionDeniedError",
    "PermissionPolicy",
    "RetryPolicy",
    "ValidationError",
    "ValidationHook",
    "ValidationPolicy",
    "build_retrying_call",
    "check_permission",
    "validate_input",
    "validate_output",
]
```

**Step 2: Run all tests**

Run: `pytest -x -q`

**Expected output:** All tests pass.

**Step 3: Commit**

```bash
git add miniautogen/policies/__init__.py
git commit -m "feat: export all policy enforcement types from policies package"
```

---

### Task 6.5: Code Review Checkpoint (Phases 5-6)

1. **Dispatch all 3 reviewers in parallel:**
   - REQUIRED SUB-SKILL: Use requesting-code-review
   - Review all changes since Phase 4 checkpoint

2. **Handle findings by severity** as described in Task 1.3.

3. **Proceed only when:** Zero Critical/High/Medium issues remain.

---

## Phase 7: Public API Update (GAP 7)

### Task 7.1: Update Public API with All New Exports

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/api.py`

**Prerequisites:**
- Phase 6 complete

**Step 1: Write the failing test**

Create file `/Users/brunocapelao/Projects/miniAutoGen/tests/compat/test_public_api_completeness.py`:

```python
"""Test that the public API exports all MiniAutoGen types."""


def test_agent_protocols_in_api() -> None:
    from miniautogen.api import (
        ConversationalAgent,
        DeliberationAgent,
        WorkflowAgent,
    )
    assert WorkflowAgent is not None
    assert DeliberationAgent is not None
    assert ConversationalAgent is not None


def test_conversation_in_api() -> None:
    from miniautogen.api import Conversation
    assert Conversation is not None


def test_agentic_loop_runtime_in_api() -> None:
    from miniautogen.api import AgenticLoopRuntime, AgenticLoopPlan
    assert AgenticLoopRuntime is not None
    assert AgenticLoopPlan is not None


def test_general_deliberation_contracts_in_api() -> None:
    from miniautogen.api import Contribution, Review
    assert Contribution is not None
    assert Review is not None


def test_subrun_request_in_api() -> None:
    from miniautogen.api import SubrunRequest
    assert SubrunRequest is not None


def test_agentic_loop_contracts_in_api() -> None:
    from miniautogen.api import (
        AgenticLoopState,
        ConversationPolicy,
        RouterDecision,
    )
    assert AgenticLoopState is not None
    assert ConversationPolicy is not None
    assert RouterDecision is not None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/compat/test_public_api_completeness.py -v`

**Expected output:** Multiple FAILED (ImportError).

**Step 3: Update api.py**

Replace contents of `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/api.py`:

```python
"""Public API — MiniAutoGen Side C.

Usage::

    from miniautogen.api import WorkflowRuntime, DeliberationRuntime, AgenticLoopRuntime

This module re-exports the essential types that define MiniAutoGen's
identity as a multi-agent coordination library.
"""

from miniautogen.core.contracts import (
    AgenticLoopState,
    ConversationPolicy,
    Contribution,
    Conversation,
    ConversationalAgent,
    DeliberationAgent,
    ExecutionEvent,
    Message,
    Review,
    RouterDecision,
    RunContext,
    RunResult,
    SubrunRequest,
    WorkflowAgent,
)
from miniautogen.core.contracts.coordination import (
    AgenticLoopPlan,
    CoordinationKind,
    CoordinationPlan,
    DeliberationPlan,
    WorkflowPlan,
    WorkflowStep,
)
from miniautogen.core.runtime import (
    AgenticLoopRuntime,
    CompositeRuntime,
    DeliberationRuntime,
    PipelineRunner,
    WorkflowRuntime,
)
from miniautogen.core.runtime.composite_runtime import CompositionStep
from miniautogen.pipeline.components.pipelinecomponent import PipelineComponent
from miniautogen.pipeline.pipeline import Pipeline

__all__ = [
    # Agent protocols
    "ConversationalAgent",
    "DeliberationAgent",
    "WorkflowAgent",
    # Core contracts
    "AgenticLoopPlan",
    "AgenticLoopState",
    "Conversation",
    "ConversationPolicy",
    "Contribution",
    "CoordinationKind",
    "CoordinationPlan",
    "DeliberationPlan",
    "ExecutionEvent",
    "Message",
    "Review",
    "RouterDecision",
    "RunContext",
    "RunResult",
    "SubrunRequest",
    "WorkflowPlan",
    "WorkflowStep",
    "CompositionStep",
    # Runtimes (Coordination Modes)
    "AgenticLoopRuntime",
    "CompositeRuntime",
    "DeliberationRuntime",
    "PipelineRunner",
    "WorkflowRuntime",
    # Pipeline
    "Pipeline",
    "PipelineComponent",
]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/compat/test_public_api_completeness.py -v`

**Expected output:** All 6 PASSED.

**Step 5: Run ALL tests including existing API marker tests**

Run: `pytest -x -q`

**Expected output:** All tests pass. Check specifically:
```
pytest tests/compat/test_public_api_markers.py -v
```

**Step 6: Commit**

```bash
git add miniautogen/api.py tests/compat/test_public_api_completeness.py
git commit -m "feat: update public API with all new contracts, protocols, and runtimes"
```

**If Task Fails:**

1. **Existing API marker tests break:** Read `tests/compat/test_public_api_markers.py` to see what it checks. The new `__all__` must be a superset of the old one.
2. **Import error from contracts:** Ensure `Conversation` was added to `miniautogen/core/contracts/__init__.py` in Task 3.2.
3. **Rollback:** `git checkout -- miniautogen/api.py`

---

### Task 7.2: Code Review Checkpoint (Phase 7)

1. **Dispatch all 3 reviewers in parallel:**
   - REQUIRED SUB-SKILL: Use requesting-code-review
   - Review all changes since Phase 6 checkpoint

2. **Handle findings by severity** as described in Task 1.3.

3. **Proceed only when:** Zero Critical/High/Medium issues remain.

---

## Phase 8: Documentation (GAP 8)

### Task 8.1: Create Architecture Document

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/docs/architecture.md`

**Prerequisites:**
- Phase 7 complete, all tests pass

**Step 1: Create the architecture document**

Create `/Users/brunocapelao/Projects/miniAutoGen/docs/architecture.md` with the following content:

```markdown
# MiniAutoGen Architecture

## Overview

MiniAutoGen is a multi-agent coordination microkernel. It provides three
coordination modes that can be composed together:

1. **WorkflowRuntime** — Sequential or parallel step execution
2. **DeliberationRuntime** — Multi-round contribution, review, and consolidation
3. **AgenticLoopRuntime** — Router-driven conversational loops

All modes implement the `CoordinationMode[PlanT]` protocol and are
orchestrated by `PipelineRunner`.

## Module Map

```
miniautogen/
  api.py                          # Public API (single import point)
  core/
    contracts/
      agent.py                    # Agent capability protocols
      agentic_loop.py             # RouterDecision, ConversationPolicy, AgenticLoopState
      conversation.py             # Conversation model
      coordination.py             # CoordinationMode protocol, plans (Workflow, Deliberation, AgenticLoop)
      deliberation.py             # Contribution, Review, ResearchOutput, PeerReview, DeliberationState, FinalDocument
      events.py                   # ExecutionEvent model
      message.py                  # Message model
      run_context.py              # RunContext
      run_result.py               # RunResult
      subrun.py                   # SubrunRequest
    events/
      event_sink.py               # EventSink protocol, InMemoryEventSink, NullEventSink
      types.py                    # EventType enum
    runtime/
      agentic_loop.py             # Helpers: detect_stagnation, should_stop_loop
      agentic_loop_runtime.py     # AgenticLoopRuntime coordination mode
      composite_runtime.py        # CompositeRuntime (mode composition)
      deliberation.py             # Deliberation helpers
      deliberation_runtime.py     # DeliberationRuntime coordination mode
      final_document.py           # Final document rendering
      pipeline_runner.py          # PipelineRunner (kernel executor)
      workflow_runtime.py         # WorkflowRuntime coordination mode
  pipeline/
    components/
      agentic_loop.py             # AgenticLoopComponent (pipeline wrapper)
      pipelinecomponent.py        # PipelineComponent ABC
    pipeline.py                   # Pipeline class
  policies/
    budget.py                     # BudgetPolicy, BudgetTracker, BudgetExceededError
    execution.py                  # ExecutionPolicy (timeout)
    permission.py                 # PermissionPolicy, check_permission, PermissionDeniedError
    retry.py                      # RetryPolicy, build_retrying_call
    validation.py                 # ValidationPolicy, validate_input, validate_output
  stores/                         # MessageStore, RunStore, CheckpointStore
  observability/                  # Structured logging
```

## Coordination Modes

### WorkflowRuntime
- **Plan:** `WorkflowPlan` (steps, fan_out, synthesis_agent)
- **Pattern:** Sequential or parallel step execution
- **Agent interface:** `process(input) -> output` or `__call__(input) -> output`

### DeliberationRuntime
- **Plan:** `DeliberationPlan` (topic, participants, max_rounds, leader_agent)
- **Pattern:** Contribute -> Review -> Consolidate -> Sufficiency check -> repeat or finalize
- **Agent interface:** `contribute()`, `review()`, `consolidate()`, `produce_final_document()`
- **Contracts:** General (`Contribution`, `Review`) and research-specific (`ResearchOutput`, `PeerReview`)

### AgenticLoopRuntime
- **Plan:** `AgenticLoopPlan` (participants, router_agent, policy, initial_message)
- **Pattern:** Router selects next speaker, agent replies, repeat until stop condition
- **Stop conditions:** Router termination, max_turns, stagnation detection
- **Agent interface:** `reply(message, context) -> str`
- **Router interface:** `route(conversation_history) -> RouterDecision`
- **Transversal:** Can be embedded in workflow steps or deliberation

### CompositeRuntime
- **Plan:** `list[CompositionStep]`
- **Pattern:** Sequential composition of coordination modes with input/output mapping
- **Example:** Workflow -> Deliberation -> Workflow

## Agent Protocols

Capability-based, not monolithic:

- `WorkflowAgent` — `async def process(input_data) -> output`
- `DeliberationAgent` — `async def contribute()`, `review()`, `consolidate()`, `produce_final_document()`
- `ConversationalAgent` — `async def reply(message, context) -> str`

All are `@runtime_checkable Protocol` types. Agents can implement multiple protocols.

## Policies

| Policy | Enforcement |
|--------|-------------|
| `ExecutionPolicy` | Timeout via anyio in PipelineRunner |
| `BudgetPolicy` | `BudgetTracker.record_cost()` raises `BudgetExceededError` |
| `RetryPolicy` | `build_retrying_call()` with tenacity |
| `ValidationPolicy` | `validate_input()`/`validate_output()` with hooks |
| `PermissionPolicy` | `check_permission()` raises `PermissionDeniedError` |

## Quick Reference

```python
from miniautogen.api import (
    # Create a workflow
    WorkflowRuntime, WorkflowPlan, WorkflowStep,
    # Create a deliberation
    DeliberationRuntime, DeliberationPlan,
    # Create an agentic loop
    AgenticLoopRuntime, AgenticLoopPlan, ConversationPolicy,
    # Compose modes
    CompositeRuntime, CompositionStep,
    # Core types
    RunContext, RunResult, PipelineRunner,
)
```
```

**Step 2: Verify the document renders correctly**

Run: `python -c "open('docs/architecture.md').read()" && echo "OK"`

**Expected output:** `OK`

**Step 3: Commit**

```bash
git add docs/architecture.md
git commit -m "docs: add architecture document reflecting full Side C implementation"
```

---

### Task 8.2: Final Verification

**Prerequisites:**
- All phases 1-8 complete

**Step 1: Run full test suite**

Run: `pytest -v --tb=short`

**Expected output:** All tests pass. Count should be approximately 200+ tests (171 original + ~30 new).

**Step 2: Verify all imports work from public API**

Run:
```bash
python -c "
from miniautogen.api import (
    WorkflowRuntime, DeliberationRuntime, AgenticLoopRuntime,
    CompositeRuntime, PipelineRunner,
    WorkflowPlan, DeliberationPlan, AgenticLoopPlan,
    WorkflowStep, CompositionStep,
    RunContext, RunResult, ExecutionEvent, Message,
    Contribution, Review, Conversation, SubrunRequest,
    WorkflowAgent, DeliberationAgent, ConversationalAgent,
    RouterDecision, ConversationPolicy, AgenticLoopState,
    CoordinationKind, CoordinationPlan,
)
print('All imports successful')
print(f'CoordinationKind members: {[k.value for k in CoordinationKind]}')
"
```

**Expected output:**
```
All imports successful
CoordinationKind members: ['workflow', 'deliberation', 'agentic_loop']
```

**Step 3: Verify protocol checks work**

Run:
```bash
python -c "
from miniautogen.api import WorkflowAgent, DeliberationAgent, ConversationalAgent

class W:
    async def process(self, input_data): return input_data

class D:
    async def contribute(self, topic): pass
    async def review(self, target_id, contribution): pass
    async def consolidate(self, topic, contributions, reviews): pass
    async def produce_final_document(self, state, contributions): pass

class C:
    async def reply(self, message, context): return message

print(f'WorkflowAgent check: {isinstance(W(), WorkflowAgent)}')
print(f'DeliberationAgent check: {isinstance(D(), DeliberationAgent)}')
print(f'ConversationalAgent check: {isinstance(C(), ConversationalAgent)}')
"
```

**Expected output:**
```
WorkflowAgent check: True
DeliberationAgent check: True
ConversationalAgent check: True
```

**Step 4: Commit (if any final adjustments were needed)**

```bash
git status  # Check for uncommitted changes
```

---

### Task 8.3: Final Code Review

1. **Dispatch all 3 reviewers in parallel:**
   - REQUIRED SUB-SKILL: Use requesting-code-review
   - Full review of all changes across all phases

2. **Handle findings by severity** as described in Task 1.3.

3. **Proceed only when:** Zero Critical/High/Medium issues remain.

---

## Summary

| Phase | GAP | Tasks | Key Deliverables |
|-------|-----|-------|------------------|
| 1 | GAP 2: General Deliberation | 1.1-1.3 | `Contribution`, `Review` base models |
| 2 | GAP 3: Agent Protocols | 2.1-2.2 | `WorkflowAgent`, `DeliberationAgent`, `ConversationalAgent` |
| 3 | GAP 6: Conversation | 3.1-3.3 | `Conversation` model |
| 4 | GAP 1: AgenticLoop | 4.1-4.6 | `AgenticLoopRuntime`, `AgenticLoopPlan`, events, component wiring |
| 5 | GAP 5: SubrunRequest | 5.1-5.2 | `SubrunRequest` contract |
| 6 | GAP 4: Policies | 6.1-6.5 | `BudgetTracker`, `validate_input/output`, `check_permission` |
| 7 | GAP 7: Public API | 7.1-7.2 | Updated `api.py` with all new exports |
| 8 | GAP 8: Documentation | 8.1-8.3 | Architecture doc, final verification |

**Total tasks:** 25 (including code review checkpoints)
**Estimated time per task:** 2-5 minutes
**Total estimated time:** ~75-125 minutes

**Architectural constraints honored:**
- DA-1: PipelineRunner stays as kernel executor
- DA-2: Modes implement Protocol, no rigid base class
- DA-3: Deliberation contracts generalized (Contribution/Review)
- DA-4: AgenticLoopComponent is transversal, not sovereign
- DA-5: Composition between modes is explicit (CompositeRuntime)
- DA-6: Legacy coexists, no breaking changes
- DA-7: Public API preserves multiagent identity
- DA-8: Memory layers untouched (future work)
