# MiniAutoGen Architecture Execution Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform the approved target architecture into an executable, low-risk engineering backlog that incrementally evolves MiniAutoGen from the current async chat implementation to the new microkernel-oriented structure.

**Architecture:** The implementation preserves the current pipeline-based behavior while introducing typed contracts, a dedicated runner, compatibility facades, explicit stores, policies, and observability in controlled phases. Work is staged so that current public behavior is frozen first, then new abstractions are added in parallel, and only later do legacy internals get cut over.

**Tech Stack:** Python 3.10+, Pydantic v2, pytest, pytest-asyncio, Ruff, MyPy, AnyIO, HTTPX, LiteLLM, SQLAlchemy 2.x, structlog

---

## Execution Rules

- Keep the current public behavior working until the relevant compatibility-cut task is complete.
- Prefer additive changes first, replacement second, removal last.
- Do not expose AnyIO directly in the public API before the runner compatibility tasks are complete.
- All new contracts must be covered by direct unit tests before integration wiring.
- All deprecations must be documented in the compatibility layer and release notes before removal.

## Backlog Structure

- Phase 0: safety net
- Phase 1: contracts
- Phase 2: runtime
- Phase 3: adapters
- Phase 4: stores
- Phase 5: events and policies
- Phase 6: hardening

### Task 1: Establish Phase 0 Safety Net

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/regression/test_chat_flow_regression.py`
- Create: `tests/regression/test_agent_reply_regression.py`
- Create: `tests/regression/test_chatadmin_regression.py`
- Create: `tests/regression/test_repository_regression.py`

**Step 1: Write failing regression tests for current behavior**

```python
import pytest

from miniautogen.agent.agent import Agent
from miniautogen.chat.chat import Chat
from miniautogen.chat.chatadmin import ChatAdmin
from miniautogen.pipeline.pipeline import Pipeline
from miniautogen.pipeline.components.components import (
    NextAgentSelectorComponent,
    AgentReplyComponent,
    TerminateChatComponent,
)
from miniautogen.storage.in_memory_repository import InMemoryChatRepository


@pytest.mark.asyncio
async def test_current_chat_add_message_persists_and_returns_message():
    chat = Chat(repository=InMemoryChatRepository())
    message = await chat.add_message("user", "hello")
    messages = await chat.get_messages()

    assert message.sender_id == "user"
    assert message.content == "hello"
    assert len(messages) == 1


@pytest.mark.asyncio
async def test_current_chatadmin_pipeline_executes_round_trip():
    class StaticPipeline(Pipeline):
        pass

    agent = Agent("assistant", "Assistant", "helper", pipeline=None)
    chat = Chat(repository=InMemoryChatRepository())
    chat.add_agent(agent)
    await chat.add_message("user", "hello")

    admin = ChatAdmin(
        "admin",
        "Admin",
        "orchestrator",
        Pipeline([
            NextAgentSelectorComponent(),
            AgentReplyComponent(),
            TerminateChatComponent(),
        ]),
        chat,
        "goal",
        1,
    )

    await admin.run()
    assert admin.round == 1
```

**Step 2: Run regression tests to verify baseline**

Run: `PYTHONPATH=. pytest tests/regression -q`
Expected: FAIL initially because new regression files do not exist yet.

**Step 3: Add minimal test scaffolding and Ruff configuration**

```toml
[tool.ruff]
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I"]
```

**Step 4: Run regression tests and existing tests**

Run: `PYTHONPATH=. pytest tests/test_core.py tests/regression -q`
Expected: PASS after regression coverage is added and baseline behavior is captured.

**Step 5: Commit**

```bash
git add pyproject.toml tests/regression
git commit -m "test: freeze current runtime behavior with regression coverage"
```

### Task 2: Introduce Core Contract Package

**Files:**
- Create: `miniautogen/core/contracts/__init__.py`
- Create: `miniautogen/core/contracts/message.py`
- Create: `miniautogen/core/contracts/run_context.py`
- Create: `miniautogen/core/contracts/run_result.py`
- Create: `miniautogen/core/contracts/events.py`
- Modify: `miniautogen/schemas.py`
- Create: `tests/core/contracts/test_run_context.py`
- Create: `tests/core/contracts/test_run_result.py`
- Create: `tests/core/contracts/test_events.py`

**Step 1: Write failing tests for new contract invariants**

```python
from datetime import datetime

import pytest
from pydantic import ValidationError

from miniautogen.core.contracts.run_context import RunContext


def test_run_context_requires_core_operational_fields():
    ctx = RunContext(
        run_id="run-1",
        started_at=datetime.utcnow(),
        correlation_id="corr-1",
        execution_state={},
        input_payload={"message": "hello"},
    )

    assert ctx.run_id == "run-1"
    assert ctx.correlation_id == "corr-1"


def test_run_context_rejects_missing_run_id():
    with pytest.raises(ValidationError):
        RunContext(
            started_at=datetime.utcnow(),
            correlation_id="corr-1",
            execution_state={},
            input_payload={},
        )
```

**Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. pytest tests/core/contracts/test_run_context.py -q`
Expected: FAIL with import errors for missing contract modules.

**Step 3: Implement minimal contract models**

```python
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RunContext(BaseModel):
    run_id: str
    started_at: datetime
    correlation_id: str
    execution_state: dict[str, Any] = Field(default_factory=dict)
    input_payload: Any = None
    timeout_seconds: float | None = None
    namespace: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
```

**Step 4: Re-export and bridge current schemas**

```python
from .message import Message
```

Add bridge exports in `miniautogen/schemas.py` so old imports continue working during migration.

**Step 5: Run contract tests**

Run: `PYTHONPATH=. pytest tests/core/contracts -q`
Expected: PASS

**Step 6: Commit**

```bash
git add miniautogen/core miniautogen/schemas.py tests/core/contracts
git commit -m "feat: add typed execution contracts for core runtime"
```

### Task 3: Add Event Taxonomy and Event Sink

**Files:**
- Create: `miniautogen/core/events/__init__.py`
- Create: `miniautogen/core/events/event_sink.py`
- Create: `miniautogen/core/events/types.py`
- Create: `tests/core/events/test_event_types.py`
- Create: `tests/core/events/test_event_sink.py`

**Step 1: Write failing tests for canonical event types**

```python
from miniautogen.core.events.types import EventType


def test_event_type_contains_terminal_run_events():
    assert EventType.RUN_CANCELLED.value == "run_cancelled"
    assert EventType.RUN_TIMED_OUT.value == "run_timed_out"
```

**Step 2: Run tests**

Run: `PYTHONPATH=. pytest tests/core/events -q`
Expected: FAIL because event modules are missing.

**Step 3: Implement minimal event taxonomy**

```python
from enum import Enum


class EventType(str, Enum):
    RUN_STARTED = "run_started"
    RUN_FINISHED = "run_finished"
    RUN_CANCELLED = "run_cancelled"
    RUN_TIMED_OUT = "run_timed_out"
    COMPONENT_STARTED = "component_started"
    COMPONENT_FINISHED = "component_finished"
```

Add an `EventSink` protocol-like base with `publish(event)` and a no-op sink.

**Step 4: Run tests**

Run: `PYTHONPATH=. pytest tests/core/events -q`
Expected: PASS

**Step 5: Commit**

```bash
git add miniautogen/core/events tests/core/events
git commit -m "feat: add canonical execution event taxonomy"
```

### Task 4: Introduce PipelineRunner Behind Compatibility Layer

**Files:**
- Create: `miniautogen/core/runtime/__init__.py`
- Create: `miniautogen/core/runtime/pipeline_runner.py`
- Create: `miniautogen/compat/__init__.py`
- Create: `miniautogen/compat/state_bridge.py`
- Modify: `miniautogen/pipeline/pipeline.py`
- Modify: `miniautogen/chat/chatadmin.py`
- Create: `tests/core/runtime/test_pipeline_runner.py`
- Create: `tests/compat/test_state_bridge.py`

**Step 1: Write failing runner tests**

```python
import pytest

from miniautogen.core.runtime.pipeline_runner import PipelineRunner
from miniautogen.pipeline.pipeline import Pipeline
from miniautogen.pipeline.components.pipelinecomponent import PipelineComponent


class MarkerComponent(PipelineComponent):
    async def process(self, state):
        state["visited"] = True
        return state


@pytest.mark.asyncio
async def test_pipeline_runner_executes_existing_pipeline_shape():
    runner = PipelineRunner()
    pipeline = Pipeline([MarkerComponent()])
    result = await runner.run_pipeline(pipeline, {"visited": False})

    assert result["visited"] is True
```

**Step 2: Run runner tests**

Run: `PYTHONPATH=. pytest tests/core/runtime/test_pipeline_runner.py -q`
Expected: FAIL because runner does not exist.

**Step 3: Implement minimal runner and bridge**

```python
class PipelineRunner:
    async def run_pipeline(self, pipeline, state):
        current = state
        for component in pipeline.components:
            current = await component.process(current)
        return current
```

Add a compatibility bridge that converts `ChatPipelineState` to the new internal execution context shape without changing callers yet.

**Step 4: Delegate `ChatAdmin.run()` to the runner without changing its public signature**

```python
self._runner = PipelineRunner()
state = ChatPipelineState(group_chat=self.group_chat, chat_admin=self)
while self.round < self.max_rounds and self.running:
    state = await self._runner.run_pipeline(self.pipeline, state)
    self.round += 1
```

**Step 5: Run runtime, compatibility, and regression tests**

Run: `PYTHONPATH=. pytest tests/core/runtime tests/compat tests/regression -q`
Expected: PASS

**Step 6: Commit**

```bash
git add miniautogen/core/runtime miniautogen/compat miniautogen/chat/chatadmin.py miniautogen/pipeline/pipeline.py tests/core/runtime tests/compat
git commit -m "feat: introduce pipeline runner under compatibility facade"
```

### Task 5: Introduce Store Family Alongside ChatRepository

**Files:**
- Create: `miniautogen/stores/__init__.py`
- Create: `miniautogen/stores/message_store.py`
- Create: `miniautogen/stores/run_store.py`
- Create: `miniautogen/stores/checkpoint_store.py`
- Create: `miniautogen/stores/memory/message_store.py`
- Modify: `miniautogen/storage/repository.py`
- Create: `tests/stores/test_message_store.py`

**Step 1: Write failing tests for message store contract**

```python
import pytest

from miniautogen.core.contracts.message import Message
from miniautogen.stores.memory.message_store import InMemoryMessageStore


@pytest.mark.asyncio
async def test_in_memory_message_store_is_append_only():
    store = InMemoryMessageStore()
    await store.append(Message(sender_id="user", content="hello"))
    await store.append(Message(sender_id="assistant", content="world"))

    items = await store.list_messages()
    assert [item.content for item in items] == ["hello", "world"]
```

**Step 2: Run tests**

Run: `PYTHONPATH=. pytest tests/stores/test_message_store.py -q`
Expected: FAIL because store package does not exist.

**Step 3: Implement minimal store contracts and memory adapter**

```python
class InMemoryMessageStore:
    def __init__(self):
        self._items = []

    async def append(self, message):
        self._items.append(message)

    async def list_messages(self):
        return list(self._items)
```

Bridge `ChatRepository` to the new message store contract where practical, without removing the old abstraction yet.

**Step 4: Run store and regression tests**

Run: `PYTHONPATH=. pytest tests/stores tests/regression -q`
Expected: PASS

**Step 5: Commit**

```bash
git add miniautogen/stores miniautogen/storage/repository.py tests/stores
git commit -m "feat: add store family with in-memory message store"
```

### Task 6: Formalize Adapter Protocols

**Files:**
- Create: `miniautogen/adapters/__init__.py`
- Create: `miniautogen/adapters/llm/__init__.py`
- Create: `miniautogen/adapters/llm/protocol.py`
- Create: `miniautogen/adapters/templates/__init__.py`
- Create: `miniautogen/adapters/templates/protocol.py`
- Modify: `miniautogen/llms/llm_client.py`
- Create: `tests/adapters/llm/test_llm_protocol.py`

**Step 1: Write failing tests for provider-neutral LLM adapter contract**

```python
from miniautogen.adapters.llm.protocol import LLMProviderProtocol


def test_llm_provider_protocol_name_is_stable():
    assert LLMProviderProtocol.__name__ == "LLMProviderProtocol"
```

**Step 2: Run adapter tests**

Run: `PYTHONPATH=. pytest tests/adapters/llm/test_llm_protocol.py -q`
Expected: FAIL because protocol module does not exist.

**Step 3: Implement thin protocols and adapt LiteLLM client**

```python
from typing import Protocol, Any


class LLMProviderProtocol(Protocol):
    async def complete(self, prompt: Any, *, model: str | None = None) -> str:
        ...
```

Add a compatibility wrapper around the current LiteLLM client instead of leaking current method names into the new core contracts.

**Step 4: Run adapter and regression tests**

Run: `PYTHONPATH=. pytest tests/adapters tests/regression -q`
Expected: PASS

**Step 5: Commit**

```bash
git add miniautogen/adapters miniautogen/llms/llm_client.py tests/adapters
git commit -m "feat: formalize provider-neutral adapter protocols"
```

### Task 7: Add Policy Categories Without Creating a Policy Blob

**Files:**
- Create: `miniautogen/policies/__init__.py`
- Create: `miniautogen/policies/execution.py`
- Create: `miniautogen/policies/retry.py`
- Create: `miniautogen/policies/validation.py`
- Create: `tests/policies/test_execution_policy.py`

**Step 1: Write failing tests for policy boundaries**

```python
from miniautogen.policies.execution import ExecutionPolicy


def test_execution_policy_exposes_timeout_configuration():
    policy = ExecutionPolicy(timeout_seconds=5)
    assert policy.timeout_seconds == 5
```

**Step 2: Run policy tests**

Run: `PYTHONPATH=. pytest tests/policies/test_execution_policy.py -q`
Expected: FAIL because policy package does not exist.

**Step 3: Implement minimal policy dataclasses or models**

```python
from dataclasses import dataclass


@dataclass
class ExecutionPolicy:
    timeout_seconds: float | None = None
```

Keep policies declarative at first. Do not wire them deeply into runtime behavior until contract tests exist.

**Step 4: Run policy tests**

Run: `PYTHONPATH=. pytest tests/policies -q`
Expected: PASS

**Step 5: Commit**

```bash
git add miniautogen/policies tests/policies
git commit -m "feat: add explicit policy categories for runtime controls"
```

### Task 8: Introduce Structured Logging and Event Publishing

**Files:**
- Create: `miniautogen/observability/__init__.py`
- Create: `miniautogen/observability/logging.py`
- Modify: `miniautogen/chat/chatadmin.py`
- Modify: `miniautogen/pipeline/components/components.py`
- Create: `tests/observability/test_event_logging.py`

**Step 1: Write failing tests for event publication**

```python
import pytest

from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.events.types import EventType


@pytest.mark.asyncio
async def test_in_memory_event_sink_records_events():
    sink = InMemoryEventSink()
    await sink.publish({"type": EventType.RUN_STARTED.value})
    assert sink.events[0]["type"] == EventType.RUN_STARTED.value
```

**Step 2: Run observability tests**

Run: `PYTHONPATH=. pytest tests/observability/test_event_logging.py -q`
Expected: FAIL if sink implementation is incomplete.

**Step 3: Implement minimal in-memory sink and structured logger wiring**

```python
class InMemoryEventSink:
    def __init__(self):
        self.events = []

    async def publish(self, event):
        self.events.append(event)
```

Wire runner or ChatAdmin start/finish to publish canonical events before adding OpenTelemetry.

**Step 4: Run observability and regression tests**

Run: `PYTHONPATH=. pytest tests/observability tests/regression -q`
Expected: PASS

**Step 5: Commit**

```bash
git add miniautogen/observability miniautogen/chat/chatadmin.py miniautogen/pipeline/components/components.py tests/observability
git commit -m "feat: add event sink and structured logging baseline"
```

### Task 9: Add Compatibility Governance Markers in Public API

**Files:**
- Modify: `miniautogen/__init__.py`
- Create: `miniautogen/compat/public_api.py`
- Create: `tests/compat/test_public_api_markers.py`
- Modify: `docs/pt/target-architecture/09-governanca-compatibilidade.md`

**Step 1: Write failing tests for API stability markers**

```python
from miniautogen.compat.public_api import STABILITY_STABLE, STABILITY_EXPERIMENTAL


def test_stability_markers_are_defined():
    assert STABILITY_STABLE == "stable"
    assert STABILITY_EXPERIMENTAL == "experimental"
```

**Step 2: Run tests**

Run: `PYTHONPATH=. pytest tests/compat/test_public_api_markers.py -q`
Expected: FAIL because markers are missing.

**Step 3: Implement simple compatibility markers**

```python
STABILITY_STABLE = "stable"
STABILITY_EXPERIMENTAL = "experimental"
STABILITY_INTERNAL = "internal"
```

Expose them only as metadata helpers initially.

**Step 4: Run compatibility tests**

Run: `PYTHONPATH=. pytest tests/compat -q`
Expected: PASS

**Step 5: Commit**

```bash
git add miniautogen/__init__.py miniautogen/compat/public_api.py tests/compat docs/pt/target-architecture/09-governanca-compatibilidade.md
git commit -m "feat: add public stability markers for compatibility governance"
```

### Task 10: Convert Roadmap to Trackable Engineering Backlog

**Files:**
- Create: `docs/plans/backlog/phase-0-safety-net.md`
- Create: `docs/plans/backlog/phase-1-contracts.md`
- Create: `docs/plans/backlog/phase-2-runtime.md`
- Create: `docs/plans/backlog/phase-3-adapters.md`
- Create: `docs/plans/backlog/phase-4-stores.md`
- Create: `docs/plans/backlog/phase-5-events-policies.md`
- Create: `docs/plans/backlog/phase-6-hardening.md`

**Step 1: Create backlog templates with definition of done**

```md
# Phase 1 Contracts

- Epic: typed execution contracts
- Packages: `miniautogen/core/contracts`, `miniautogen/core/events`
- Done when:
  - `RunContext`, `RunResult`, `ExecutionEvent` exist with tests
  - provider/store/tool protocols exist
  - regression suite remains green
```

**Step 2: Run a documentation link check by grep**

Run: `rg -n "Done when|Epic:|Packages:" docs/plans/backlog`
Expected: PASS with one or more entries per phase file.

**Step 3: Commit**

```bash
git add docs/plans/backlog
git commit -m "docs: derive phased engineering backlog from architecture roadmap"
```

## Verification Sweep

After completing all tasks above, run:

```bash
PYTHONPATH=. pytest -q
PYTHONPATH=. pytest tests/regression tests/core tests/stores tests/adapters tests/policies tests/observability -q
```

Expected:

- current behavior preserved;
- new typed contracts covered;
- runner compatibility verified;
- phased backlog documented.

## Recommended Execution Order

1. Task 1
2. Task 2
3. Task 3
4. Task 4
5. Task 5
6. Task 6
7. Task 7
8. Task 8
9. Task 9
10. Task 10
