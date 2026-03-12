# MiniAutoGen Wave 2 Runtime And Compatibility Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Introduce the new runtime backbone for MiniAutoGen by adding `PipelineRunner`, controlled AnyIO adoption, state bridges, `ChatAdmin` delegation, and explicit compatibility boundaries without breaking the current public behavior.

**Architecture:** This wave keeps the current pipeline composition intact while moving execution mechanics into a dedicated runner and compatibility layer. AnyIO enters only as an internal runtime capability, with `ChatAdmin` preserved as the public facade during transition and legacy state bridged explicitly instead of merged informally.

**Tech Stack:** Python 3.10+, AnyIO, pytest, pytest-asyncio, Pydantic v2, Ruff

---

## Wave Scope

This wave covers only:

- `PipelineRunner`
- controlled AnyIO entry in runtime internals
- bridge between legacy `ChatPipelineState` and new execution context
- `ChatAdmin` refactor into facade over the runner
- explicit compatibility helpers and cut criteria

This wave does not cover:

- new store implementations
- vendor adapters
- full observability exporters
- optional capabilities like MCP or structured outputs

## Execution Rules

- Preserve current `ChatAdmin.run()` public behavior until the final compatibility-cut task.
- Do not expose AnyIO types in the public API.
- Use bridges and facades instead of in-place mutation of old abstractions.
- Keep the current `Pipeline` class as the composition primitive.
- Every runtime change must be covered by regression tests and direct runner tests.

### Task 1: Freeze Runtime Behavior Before Internal Refactor

**Files:**
- Create: `tests/runtime/test_chatadmin_runtime_regression.py`
- Create: `tests/runtime/test_pipeline_state_regression.py`
- Modify: `tests/test_core.py`

**Step 1: Write failing regression tests for current runtime behavior**

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
async def test_chatadmin_increments_round_count_for_each_executed_round():
    chat = Chat(repository=InMemoryChatRepository())
    chat.add_agent(Agent("user", "User", "human"))
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
    assert admin.running is False
```

**Step 2: Run tests to verify baseline**

Run: `PYTHONPATH=. pytest tests/runtime/test_chatadmin_runtime_regression.py -q`
Expected: FAIL initially because the new test file does not exist yet.

**Step 3: Add the regression tests without changing production code**

```python
@pytest.mark.asyncio
async def test_chatadmin_stops_when_max_rounds_is_reached():
    chat = Chat(repository=InMemoryChatRepository())
    chat.add_agent(Agent("user", "User", "human"))
    await chat.add_message("user", "hello")

    admin = ChatAdmin("admin", "Admin", "role", Pipeline([]), chat, "goal", 0)
    await admin.run()
    assert admin.running is False
```

**Step 4: Run runtime regression and core tests**

Run: `PYTHONPATH=. pytest tests/test_core.py tests/runtime -q`
Expected: PASS with current runtime behavior captured.

**Step 5: Commit**

```bash
git add tests/test_core.py tests/runtime
git commit -m "test: freeze runtime behavior before wave 2 refactor"
```

### Task 2: Introduce Runtime Package And Minimal PipelineRunner

**Files:**
- Create: `miniautogen/core/runtime/__init__.py`
- Create: `miniautogen/core/runtime/pipeline_runner.py`
- Create: `tests/core/runtime/test_pipeline_runner.py`

**Step 1: Write failing tests for `PipelineRunner`**

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
async def test_pipeline_runner_executes_existing_pipeline_components_in_order():
    runner = PipelineRunner()
    pipeline = Pipeline([MarkerComponent()])

    result = await runner.run_pipeline(pipeline, {"visited": False})
    assert result["visited"] is True
```

**Step 2: Run the runner test**

Run: `PYTHONPATH=. pytest tests/core/runtime/test_pipeline_runner.py -q`
Expected: FAIL because `PipelineRunner` does not exist yet.

**Step 3: Implement the minimal runner**

```python
class PipelineRunner:
    async def run_pipeline(self, pipeline, state):
        current = state
        for component in pipeline.components:
            current = await component.process(current)
        return current
```

**Step 4: Re-export runner from runtime package**

```python
from .pipeline_runner import PipelineRunner
```

**Step 5: Run runtime tests**

Run: `PYTHONPATH=. pytest tests/core/runtime/test_pipeline_runner.py -q`
Expected: PASS

**Step 6: Commit**

```bash
git add miniautogen/core/runtime tests/core/runtime
git commit -m "feat: add minimal pipeline runner for wave 2"
```

### Task 3: Add Explicit Legacy-State Bridge

**Files:**
- Create: `miniautogen/compat/__init__.py`
- Create: `miniautogen/compat/state_bridge.py`
- Create: `tests/compat/test_state_bridge.py`

**Step 1: Write failing tests for the legacy-state bridge**

```python
from miniautogen.compat.state_bridge import bridge_chat_pipeline_state
from miniautogen.pipeline.pipeline import ChatPipelineState


def test_bridge_chat_pipeline_state_returns_mutable_runtime_mapping():
    state = ChatPipelineState(group_chat="chat", chat_admin="admin")
    result = bridge_chat_pipeline_state(state)

    assert result["group_chat"] == "chat"
    assert result["chat_admin"] == "admin"
```

**Step 2: Run bridge tests**

Run: `PYTHONPATH=. pytest tests/compat/test_state_bridge.py -q`
Expected: FAIL because `state_bridge.py` does not exist yet.

**Step 3: Implement the compatibility bridge**

```python
def bridge_chat_pipeline_state(state):
    if hasattr(state, "get_state"):
        return dict(state.get_state())
    return dict(state)
```

**Step 4: Add module exports**

```python
from .state_bridge import bridge_chat_pipeline_state
```

**Step 5: Run compatibility tests**

Run: `PYTHONPATH=. pytest tests/compat/test_state_bridge.py -q`
Expected: PASS

**Step 6: Commit**

```bash
git add miniautogen/compat tests/compat
git commit -m "feat: add explicit bridge for legacy pipeline state"
```

### Task 4: Introduce Controlled AnyIO Entry Point

**Files:**
- Modify: `miniautogen/core/runtime/pipeline_runner.py`
- Create: `tests/core/runtime/test_pipeline_runner_anyio.py`

**Step 1: Write failing tests for internal AnyIO usage**

```python
import pytest

from miniautogen.core.runtime.pipeline_runner import PipelineRunner


@pytest.mark.asyncio
async def test_pipeline_runner_accepts_timeout_parameter_without_public_anyio_leak():
    runner = PipelineRunner()
    assert hasattr(runner, "run_pipeline")
    assert "anyio" not in str(runner.run_pipeline)
```

**Step 2: Run AnyIO runner tests**

Run: `PYTHONPATH=. pytest tests/core/runtime/test_pipeline_runner_anyio.py -q`
Expected: FAIL until the test file and controlled timeout path exist.

**Step 3: Add internal AnyIO-based execution helper**

```python
import anyio


class PipelineRunner:
    async def run_pipeline(self, pipeline, state, *, timeout_seconds=None):
        if timeout_seconds is None:
            return await self._run_components(pipeline, state)
        with anyio.fail_after(timeout_seconds):
            return await self._run_components(pipeline, state)

    async def _run_components(self, pipeline, state):
        current = state
        for component in pipeline.components:
            current = await component.process(current)
        return current
```

**Step 4: Run runner tests**

Run: `PYTHONPATH=. pytest tests/core/runtime -q`
Expected: PASS

**Step 5: Commit**

```bash
git add miniautogen/core/runtime/pipeline_runner.py tests/core/runtime
git commit -m "feat: add controlled anyio timeout support to pipeline runner"
```

### Task 5: Delegate `ChatAdmin` To `PipelineRunner`

**Files:**
- Modify: `miniautogen/chat/chatadmin.py`
- Create: `tests/runtime/test_chatadmin_runner_delegation.py`

**Step 1: Write failing tests for `ChatAdmin` delegation**

```python
import pytest

from miniautogen.chat.chatadmin import ChatAdmin
from miniautogen.pipeline.pipeline import Pipeline
from miniautogen.storage.in_memory_repository import InMemoryChatRepository
from miniautogen.chat.chat import Chat


@pytest.mark.asyncio
async def test_chatadmin_initializes_runner_and_executes_rounds_through_it():
    chat = Chat(repository=InMemoryChatRepository())
    admin = ChatAdmin("admin", "Admin", "role", Pipeline([]), chat, "goal", 1)

    assert getattr(admin, "_runner", None) is not None
```

**Step 2: Run delegation tests**

Run: `PYTHONPATH=. pytest tests/runtime/test_chatadmin_runner_delegation.py -q`
Expected: FAIL because `ChatAdmin` does not initialize the runner yet.

**Step 3: Initialize and use the runner inside `ChatAdmin`**

```python
from miniautogen.core.runtime import PipelineRunner


class ChatAdmin(Agent):
    def __init__(...):
        ...
        self._runner = PipelineRunner()

    async def execute_round(self, state):
        await self._runner.run_pipeline(self.pipeline, state)
        self.round += 1
```

**Step 4: Keep the public API stable**

Do not change:

- constructor signature;
- `run()` method name;
- `start()` / `stop()` behavior;
- `from_json()` inputs.

**Step 5: Run runtime and regression tests**

Run: `PYTHONPATH=. pytest tests/runtime tests/regression tests/test_core.py -q`
Expected: PASS

**Step 6: Commit**

```bash
git add miniautogen/chat/chatadmin.py tests/runtime tests/regression tests/test_core.py
git commit -m "feat: delegate chat admin execution to pipeline runner"
```

### Task 6: Add Runtime Context Bridge For New Contracts

**Files:**
- Modify: `miniautogen/compat/state_bridge.py`
- Modify: `miniautogen/core/runtime/pipeline_runner.py`
- Create: `tests/compat/test_run_context_bridge.py`

**Step 1: Write failing tests for `RunContext` bridging**

```python
from datetime import datetime

from miniautogen.compat.state_bridge import build_runtime_context
from miniautogen.core.contracts.run_context import RunContext


def test_build_runtime_context_preserves_run_identity_and_payload():
    ctx = build_runtime_context(
        run_id="run-1",
        started_at=datetime.utcnow(),
        correlation_id="corr-1",
        input_payload={"message": "hello"},
    )

    assert isinstance(ctx, RunContext)
    assert ctx.run_id == "run-1"
```

**Step 2: Run tests**

Run: `PYTHONPATH=. pytest tests/compat/test_run_context_bridge.py -q`
Expected: FAIL because the bridge function does not exist yet.

**Step 3: Implement the `RunContext` builder without replacing callers yet**

```python
from miniautogen.core.contracts.run_context import RunContext


def build_runtime_context(**kwargs):
    return RunContext(**kwargs)
```

**Step 4: Use the bridge internally in the runner where appropriate**

Only adapt internal entry points. Do not require all callers to supply `RunContext` yet.

**Step 5: Run compatibility and runner tests**

Run: `PYTHONPATH=. pytest tests/compat tests/core/runtime -q`
Expected: PASS

**Step 6: Commit**

```bash
git add miniautogen/compat/state_bridge.py miniautogen/core/runtime/pipeline_runner.py tests/compat
git commit -m "feat: add run context bridge for runtime transition"
```

### Task 7: Formalize Compatibility Cut Criteria In Code And Docs

**Files:**
- Create: `miniautogen/compat/cutover.py`
- Create: `tests/compat/test_cutover_flags.py`
- Modify: `docs/pt/target-architecture/07-plano-de-migracao.md`

**Step 1: Write failing tests for cutover markers**

```python
from miniautogen.compat.cutover import RUNTIME_CUTOVER_PENDING


def test_runtime_cutover_marker_defaults_to_pending():
    assert RUNTIME_CUTOVER_PENDING is True
```

**Step 2: Run tests**

Run: `PYTHONPATH=. pytest tests/compat/test_cutover_flags.py -q`
Expected: FAIL because the cutover marker does not exist.

**Step 3: Implement explicit compatibility markers**

```python
RUNTIME_CUTOVER_PENDING = True
LEGACY_CHATADMIN_FACADE_ACTIVE = True
LEGACY_CHATPIPELINESTATE_BRIDGE_ACTIVE = True
```

Use these markers only as code-level compatibility metadata for this wave.

**Step 4: Update migration doc with Wave 2 cut criteria**

Add a short section documenting that runtime cutover can only happen when:

- `PipelineRunner` covers the current pipeline path;
- runner delegation is regression-tested;
- `ChatAdmin` remains facade-compatible;
- state bridge usage is explicit and measurable.

**Step 5: Run compatibility tests**

Run: `PYTHONPATH=. pytest tests/compat -q`
Expected: PASS

**Step 6: Commit**

```bash
git add miniautogen/compat/cutover.py tests/compat docs/pt/target-architecture/07-plano-de-migracao.md
git commit -m "docs: formalize runtime compatibility cutover markers"
```

### Task 8: Add Wave 2 Definition Of Done Backlog File

**Files:**
- Create: `docs/plans/backlog/wave-2-runtime-compat.md`

**Step 1: Create the Wave 2 backlog summary**

```md
# Wave 2 Runtime Compatibility

- Packages:
  - `miniautogen/core/runtime`
  - `miniautogen/compat`
  - `miniautogen/chat`
- Done when:
  - `PipelineRunner` executes the current pipeline shape
  - AnyIO stays internal to runtime
  - `ChatAdmin` delegates without breaking public behavior
  - explicit bridges exist for legacy state
  - cutover flags are documented
```

**Step 2: Verify backlog file format**

Run: `rg -n "Done when|Packages:" docs/plans/backlog/wave-2-runtime-compat.md`
Expected: PASS

**Step 3: Commit**

```bash
git add docs/plans/backlog/wave-2-runtime-compat.md
git commit -m "docs: add wave 2 runtime compatibility backlog file"
```

## Wave 2 Acceptance Criteria

Wave 2 is complete only when all of the following are true:

- `PipelineRunner` exists and is covered by direct tests;
- AnyIO is used only in runtime internals;
- `ChatAdmin` delegates execution through the runner while preserving public behavior;
- explicit compatibility bridges exist for legacy pipeline state and `RunContext`;
- runtime regression tests remain green;
- cutover criteria are documented and code-visible.

## Verification Sweep

Run:

```bash
PYTHONPATH=. pytest tests/runtime tests/core/runtime tests/compat tests/test_core.py -q
PYTHONPATH=. pytest tests/regression -q
```

Expected:

- runtime internals are covered;
- compatibility remains intact;
- no public behavior regression is introduced in this wave.
