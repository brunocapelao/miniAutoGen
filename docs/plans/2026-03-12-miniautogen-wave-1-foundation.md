# MiniAutoGen Wave 1 Foundation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the Wave 1 foundation for MiniAutoGen by freezing current behavior with an engineering safety net and introducing the first typed execution contracts without breaking the existing public flow.

**Architecture:** This wave deliberately avoids runtime rewrites and focuses on two things: preserving the current behavior through regression coverage, and adding a typed contract layer that can coexist with the current `schemas.py` and `ChatPipelineState` model. The implementation is additive-first: tests and compatibility bridges land before any deeper runtime change.

**Tech Stack:** Python 3.10+, pytest, pytest-asyncio, Ruff, MyPy, Pydantic v2

---

## Scope

This wave covers:

- Phase 0: engineering safety net
- Phase 1: contracts-first foundation

This wave does not cover:

- `PipelineRunner`
- AnyIO introduction
- adapter protocols beyond contract placeholders
- store family migration
- event sinks, policies, or observability wiring

## Acceptance Criteria

Wave 1 is complete only when all of the following are true:

1. The current behavior of `Chat`, `Agent`, `ChatAdmin`, and the in-memory repository is protected by regression tests.
2. Ruff is configured and runnable in CI/local workflow.
3. `RunContext`, `RunResult`, and `ExecutionEvent` exist as typed contracts with direct tests.
4. Legacy imports through `miniautogen.schemas` continue to work during the transition.
5. The new contract layer is additive and does not break the current async chat example or current tests.

## Task Sequence

### Task 1: Add Regression Test Folder and Freeze Chat Behavior

**Files:**
- Create: `tests/regression/test_chat_regression.py`
- Create: `tests/regression/test_repository_regression.py`
- Test: `tests/test_core.py`

**Step 1: Write the failing test for current message persistence behavior**

```python
import pytest

from miniautogen.chat.chat import Chat
from miniautogen.storage.in_memory_repository import InMemoryChatRepository


@pytest.mark.asyncio
async def test_chat_add_message_returns_message_and_persists_it():
    chat = Chat(repository=InMemoryChatRepository())

    message = await chat.add_message("user", "hello")
    messages = await chat.get_messages()

    assert message.sender_id == "user"
    assert message.content == "hello"
    assert len(messages) == 1
    assert messages[0].content == "hello"
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/regression/test_chat_regression.py -q`
Expected: FAIL with "file or directory not found" before the file exists.

**Step 3: Write the failing test for in-memory repository append ordering**

```python
import pytest

from miniautogen.schemas import Message
from miniautogen.storage.in_memory_repository import InMemoryChatRepository


@pytest.mark.asyncio
async def test_in_memory_repository_keeps_append_order():
    repo = InMemoryChatRepository()

    await repo.add_message(Message(sender_id="user", content="first"))
    await repo.add_message(Message(sender_id="assistant", content="second"))

    items = await repo.get_messages()

    assert [item.content for item in items] == ["first", "second"]
```

**Step 4: Run regression tests to verify they pass**

Run: `PYTHONPATH=. pytest tests/regression/test_chat_regression.py tests/regression/test_repository_regression.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/regression/test_chat_regression.py tests/regression/test_repository_regression.py
git commit -m "test: freeze chat and repository baseline behavior"
```

### Task 2: Freeze Agent and ChatAdmin Baseline Behavior

**Files:**
- Create: `tests/regression/test_agent_regression.py`
- Create: `tests/regression/test_chatadmin_regression.py`
- Test: `examples/async_chat_example.py`

**Step 1: Write the failing test for agent fallback without pipeline**

```python
import pytest

from miniautogen.agent.agent import Agent
from miniautogen.pipeline.pipeline import ChatPipelineState


@pytest.mark.asyncio
async def test_agent_without_pipeline_returns_default_message():
    agent = Agent("a1", "Assistant", "helper")
    reply = await agent.generate_reply(ChatPipelineState())

    assert "don't have a pipeline" in reply.lower()
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/regression/test_agent_regression.py -q`
Expected: FAIL before the file exists.

**Step 3: Write the failing test for ChatAdmin round progression**

```python
import pytest

from miniautogen.agent.agent import Agent
from miniautogen.chat.chat import Chat
from miniautogen.chat.chatadmin import ChatAdmin
from miniautogen.pipeline.pipeline import Pipeline
from miniautogen.pipeline.components.components import (
    AgentReplyComponent,
    NextAgentSelectorComponent,
    TerminateChatComponent,
)
from miniautogen.storage.in_memory_repository import InMemoryChatRepository


@pytest.mark.asyncio
async def test_chatadmin_increments_round_for_one_iteration():
    chat = Chat(repository=InMemoryChatRepository())
    chat.add_agent(Agent("assistant", "Assistant", "helper"))
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

**Step 4: Run regression tests and current suite**

Run: `PYTHONPATH=. pytest tests/test_core.py tests/regression/test_agent_regression.py tests/regression/test_chatadmin_regression.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/regression/test_agent_regression.py tests/regression/test_chatadmin_regression.py
git commit -m "test: freeze agent and chatadmin baseline behavior"
```

### Task 3: Add Ruff Baseline to Project Configuration

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add failing lint command to plan**

Run: `ruff check .`
Expected: FAIL because Ruff is not configured yet and may not be installed in the workflow.

**Step 2: Add minimal Ruff configuration**

```toml
[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I"]
```

**Step 3: Run Ruff on the current package and tests**

Run: `ruff check miniautogen tests`
Expected: PASS, or surface a small cleanup list to fix immediately before moving on.

**Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "build: add ruff baseline for wave 1"
```

### Task 4: Create Core Contract Package Skeleton

**Files:**
- Create: `miniautogen/core/__init__.py`
- Create: `miniautogen/core/contracts/__init__.py`
- Create: `tests/core/contracts/test_contract_imports.py`

**Step 1: Write the failing test for new contract package imports**

```python
def test_core_contract_package_is_importable():
    from miniautogen.core.contracts import __all__

    assert isinstance(__all__, list)
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/core/contracts/test_contract_imports.py -q`
Expected: FAIL with import error because the package does not exist.

**Step 3: Implement minimal package skeleton**

```python
__all__ = []
```

**Step 4: Run import test**

Run: `PYTHONPATH=. pytest tests/core/contracts/test_contract_imports.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add miniautogen/core tests/core/contracts/test_contract_imports.py
git commit -m "feat: add core contract package skeleton"
```

### Task 5: Introduce Typed `RunContext`

**Files:**
- Create: `miniautogen/core/contracts/run_context.py`
- Modify: `miniautogen/core/contracts/__init__.py`
- Create: `tests/core/contracts/test_run_context.py`

**Step 1: Write the failing test for required fields**

```python
from datetime import datetime

import pytest
from pydantic import ValidationError

from miniautogen.core.contracts.run_context import RunContext


def test_run_context_requires_operational_fields():
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

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/core/contracts/test_run_context.py -q`
Expected: FAIL because `RunContext` is not implemented yet.

**Step 3: Implement minimal `RunContext` model**

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

**Step 4: Re-export from contract package**

```python
from .run_context import RunContext

__all__ = ["RunContext"]
```

**Step 5: Run contract tests**

Run: `PYTHONPATH=. pytest tests/core/contracts/test_run_context.py -q`
Expected: PASS

**Step 6: Commit**

```bash
git add miniautogen/core/contracts/run_context.py miniautogen/core/contracts/__init__.py tests/core/contracts/test_run_context.py
git commit -m "feat: add typed run context contract"
```

### Task 6: Introduce Typed `RunResult`

**Files:**
- Create: `miniautogen/core/contracts/run_result.py`
- Modify: `miniautogen/core/contracts/__init__.py`
- Create: `tests/core/contracts/test_run_result.py`

**Step 1: Write the failing test for terminal state semantics**

```python
from miniautogen.core.contracts.run_result import RunResult


def test_run_result_tracks_terminal_status():
    result = RunResult(run_id="run-1", status="success", output="ok")

    assert result.run_id == "run-1"
    assert result.status == "success"
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/core/contracts/test_run_result.py -q`
Expected: FAIL because `RunResult` is missing.

**Step 3: Implement minimal `RunResult`**

```python
from typing import Any

from pydantic import BaseModel


class RunResult(BaseModel):
    run_id: str
    status: str
    output: Any = None
    error: str | None = None
```

**Step 4: Run contract tests**

Run: `PYTHONPATH=. pytest tests/core/contracts/test_run_result.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add miniautogen/core/contracts/run_result.py miniautogen/core/contracts/__init__.py tests/core/contracts/test_run_result.py
git commit -m "feat: add typed run result contract"
```

### Task 7: Introduce Typed `ExecutionEvent`

**Files:**
- Create: `miniautogen/core/contracts/events.py`
- Modify: `miniautogen/core/contracts/__init__.py`
- Create: `tests/core/contracts/test_events.py`

**Step 1: Write the failing test for canonical event payload**

```python
from datetime import datetime

from miniautogen.core.contracts.events import ExecutionEvent


def test_execution_event_captures_type_and_correlation():
    event = ExecutionEvent(
        type="run_started",
        run_id="run-1",
        timestamp=datetime.utcnow(),
        correlation_id="corr-1",
    )

    assert event.type == "run_started"
    assert event.run_id == "run-1"
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/core/contracts/test_events.py -q`
Expected: FAIL because `ExecutionEvent` is not implemented.

**Step 3: Implement minimal `ExecutionEvent`**

```python
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ExecutionEvent(BaseModel):
    type: str
    run_id: str
    timestamp: datetime
    correlation_id: str
    scope: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
```

**Step 4: Run contract tests**

Run: `PYTHONPATH=. pytest tests/core/contracts/test_events.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add miniautogen/core/contracts/events.py miniautogen/core/contracts/__init__.py tests/core/contracts/test_events.py
git commit -m "feat: add typed execution event contract"
```

### Task 8: Bridge Legacy `schemas.py` to the New Contract Layer

**Files:**
- Modify: `miniautogen/schemas.py`
- Create: `tests/core/contracts/test_schema_bridge.py`

**Step 1: Write the failing test for backward-compatible imports**

```python
from miniautogen.schemas import Message


def test_legacy_schema_message_import_still_works():
    message = Message(sender_id="user", content="hello")
    assert message.content == "hello"
```

**Step 2: Run test to verify baseline**

Run: `PYTHONPATH=. pytest tests/core/contracts/test_schema_bridge.py -q`
Expected: PASS initially, then remain PASS after `schemas.py` changes.

**Step 3: Add bridge comments and explicit transitional exports**

```python
# Transitional bridge: keep legacy imports working while contracts move to
# miniautogen.core.contracts.
```

Keep `Message`, `AgentConfig`, and `ChatState` available from `schemas.py`. If any new imports are re-exported here, do it explicitly and minimally.

**Step 4: Run contract and legacy tests**

Run: `PYTHONPATH=. pytest tests/core/contracts tests/test_core.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add miniautogen/schemas.py tests/core/contracts/test_schema_bridge.py
git commit -m "refactor: bridge legacy schemas to new contract layer"
```

### Task 9: Add MyPy Baseline for the New Contract Layer

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add failing MyPy command to the plan**

Run: `mypy miniautogen/core/contracts`
Expected: FAIL initially because MyPy configuration is not present.

**Step 2: Add minimal MyPy configuration**

```toml
[tool.mypy]
python_version = "3.10"
warn_unused_configs = true
check_untyped_defs = true
```

**Step 3: Run MyPy against the new contract package**

Run: `mypy miniautogen/core/contracts`
Expected: PASS

**Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "build: add mypy baseline for wave 1 contracts"
```

### Task 10: Run Wave 1 Verification Sweep and Record Done State

**Files:**
- Modify: `docs/pt/target-architecture/04-roadmap-adocao.md`

**Step 1: Run the full Wave 1 verification set**

Run: `PYTHONPATH=. pytest tests/test_core.py tests/regression tests/core/contracts -q`
Expected: PASS

Run: `ruff check miniautogen tests`
Expected: PASS

Run: `mypy miniautogen/core/contracts`
Expected: PASS

**Step 2: Record that Wave 1 acceptance criteria are now concretely testable**

Add a short implementation note in `docs/pt/target-architecture/04-roadmap-adocao.md` only if the team wants execution traceability in the architecture docs. Otherwise skip this file change and keep verification in commit history.

**Step 3: Commit**

```bash
git add docs/pt/target-architecture/04-roadmap-adocao.md
git commit -m "docs: mark wave 1 verification criteria as executable"
```

## Definition of Done

Wave 1 is done when:

- regression tests protect the current async chat baseline;
- Ruff is configured and passing;
- MyPy runs on `miniautogen/core/contracts`;
- `RunContext`, `RunResult`, and `ExecutionEvent` exist with direct tests;
- `miniautogen.schemas` remains backward-compatible for the current surface;
- no public runtime behavior is broken while introducing the contract layer.
