# Milestone 1 — Chunk 1: Core Contracts & Microkernel Stabilization

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan.

**Goal:** Finalize all protocol contracts and prepare PipelineRunner cutover

**Architecture:** Protocol-first design — all SDK concepts defined as @runtime_checkable Protocols before implementation. Every new contract follows the same pattern as the existing `WorkflowAgent`, `DeliberationAgent`, `ConversationalAgent` protocols in `miniautogen/core/contracts/agent.py`. Tests follow the pattern in `tests/core/contracts/test_agent_protocols.py` — fake implementations, broken implementations, isinstance checks.

**Tech Stack:** Python 3.10+, AnyIO 4+, Pydantic v2, pytest-asyncio 0.23+, ruff (line-length=100)

**Global Prerequisites:**
- Environment: macOS, Python 3.10 or 3.11
- Tools: `python --version`, `pytest --version`, `ruff --version`
- State: Work from `main` branch, clean working tree

**Verification before starting:**
```bash
cd /Users/brunocapelao/Projects/miniAutoGen
python --version        # Expected: Python 3.10.x or 3.11.x
pytest --version        # Expected: pytest 7.x
ruff --version          # Expected: ruff 0.15+
git status              # Expected: clean working tree (untracked docs ok)
pytest --co -q 2>&1 | tail -1  # Expected: "NNN tests collected"
```

---

## Task 1: Define ToolProtocol and ToolResult

**Files:**
- Create: `miniautogen/core/contracts/tool.py`
- Test: `tests/core/contracts/test_tool_protocol.py`
- Modify: `miniautogen/core/contracts/__init__.py`

**Prerequisites:**
- File must exist: `miniautogen/core/contracts/__init__.py`

**Step 1: Write the failing test**

Create `tests/core/contracts/test_tool_protocol.py`:

```python
"""Tests for ToolProtocol and ToolResult contracts."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from miniautogen.core.contracts.tool import ToolProtocol, ToolResult


# --- ToolResult model ---


def test_tool_result_success() -> None:
    result = ToolResult(success=True, output={"key": "value"})
    assert result.success is True
    assert result.output == {"key": "value"}
    assert result.error is None


def test_tool_result_failure() -> None:
    result = ToolResult(success=False, output=None, error="something broke")
    assert result.success is False
    assert result.error == "something broke"


def test_tool_result_serialization_roundtrip() -> None:
    result = ToolResult(success=True, output=[1, 2, 3])
    data = result.model_dump()
    restored = ToolResult.model_validate(data)
    assert restored == result


def test_tool_result_requires_success() -> None:
    with pytest.raises(ValidationError):
        ToolResult()  # type: ignore[call-arg]


# --- ToolProtocol structural subtyping ---


class _FakeTool:
    """Satisfies ToolProtocol structurally."""

    @property
    def name(self) -> str:
        return "search"

    @property
    def description(self) -> str:
        return "Searches the web"

    async def execute(self, input: dict[str, Any]) -> ToolResult:
        return ToolResult(success=True, output="found it")


class _BrokenTool:
    """Does NOT satisfy ToolProtocol — missing execute()."""

    @property
    def name(self) -> str:
        return "broken"

    @property
    def description(self) -> str:
        return "Broken tool"


class _MinimalTool:
    """Satisfies ToolProtocol with attributes instead of properties."""

    name: str = "minimal"
    description: str = "A minimal tool"

    def __init__(self) -> None:
        self.name = "minimal"
        self.description = "A minimal tool"

    async def execute(self, input: dict[str, Any]) -> ToolResult:
        return ToolResult(success=True, output=None)


def test_fake_tool_satisfies_protocol() -> None:
    tool = _FakeTool()
    assert isinstance(tool, ToolProtocol)


def test_broken_tool_does_not_satisfy_protocol() -> None:
    tool = _BrokenTool()
    assert not isinstance(tool, ToolProtocol)


def test_minimal_tool_satisfies_protocol() -> None:
    tool = _MinimalTool()
    assert isinstance(tool, ToolProtocol)


# --- Cross-check: import from contracts __init__ ---


def test_tool_protocol_exported_from_contracts() -> None:
    from miniautogen.core.contracts import ToolProtocol, ToolResult

    assert ToolProtocol is not None
    assert ToolResult is not None
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/core/contracts/test_tool_protocol.py -v 2>&1 | head -20`

**Expected output:**
```
ERROR tests/core/contracts/test_tool_protocol.py
ModuleNotFoundError: No module named 'miniautogen.core.contracts.tool'
```

**If you see different error:** Check that `tests/core/contracts/` directory exists.

**Step 3: Create the ToolProtocol and ToolResult**

Create `miniautogen/core/contracts/tool.py`:

```python
"""Tool capability protocol for the MiniAutoGen SDK.

Defines the structural contract that tools must satisfy to be invoked
by agents or runtimes within the coordination framework.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel


class ToolResult(BaseModel):
    """Result of a tool execution."""

    success: bool
    output: Any = None
    error: str | None = None


@runtime_checkable
class ToolProtocol(Protocol):
    """Interface that every tool must implement.

    Tools are invoked by agents during agentic loop coordination
    or by runtimes that support tool-use patterns.
    """

    @property
    def name(self) -> str: ...

    @property
    def description(self) -> str: ...

    async def execute(self, input: dict[str, Any]) -> ToolResult: ...
```

**Step 4: Export from contracts __init__**

In `miniautogen/core/contracts/__init__.py`, add the import and update `__all__`:

Add after the existing `from .tool import ...` line (after line 18, before the `__all__` list):

```python
from .tool import ToolProtocol, ToolResult
```

Add to `__all__` (alphabetical order — insert after `"SubrunRequest",`):

```python
    "ToolProtocol",
    "ToolResult",
```

The updated `__init__.py` should have these new lines:
- Import: `from .tool import ToolProtocol, ToolResult` (add after line 20, before `__all__`)
- `__all__` entries: `"ToolProtocol",` and `"ToolResult",` (add after `"SubrunRequest",`)

**Step 5: Run test to verify it passes**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/core/contracts/test_tool_protocol.py -v`

**Expected output:**
```
tests/core/contracts/test_tool_protocol.py::test_tool_result_success PASSED
tests/core/contracts/test_tool_protocol.py::test_tool_result_failure PASSED
tests/core/contracts/test_tool_protocol.py::test_tool_result_serialization_roundtrip PASSED
tests/core/contracts/test_tool_protocol.py::test_tool_result_requires_success PASSED
tests/core/contracts/test_tool_protocol.py::test_fake_tool_satisfies_protocol PASSED
tests/core/contracts/test_tool_protocol.py::test_broken_tool_does_not_satisfy_protocol PASSED
tests/core/contracts/test_tool_protocol.py::test_minimal_tool_satisfies_protocol PASSED
tests/core/contracts/test_tool_protocol.py::test_tool_protocol_exported_from_contracts PASSED
```

**Step 6: Run ruff to verify formatting**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && ruff check miniautogen/core/contracts/tool.py tests/core/contracts/test_tool_protocol.py`

**Expected output:** No errors (empty output or `All checks passed!`)

**Step 7: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/core/contracts/tool.py tests/core/contracts/test_tool_protocol.py miniautogen/core/contracts/__init__.py
git commit -m "feat: add ToolProtocol and ToolResult contracts"
```

**If Task Fails:**

1. **Import error on ToolResult:** Ensure `from pydantic import BaseModel` is at the top of `tool.py`.
2. **Protocol isinstance check fails:** Ensure `@runtime_checkable` decorator is present. Note: `runtime_checkable` only checks method existence, not properties. If property checks fail, the `_MinimalTool` test may need adjusting — use instance attributes instead.
3. **Ruff error:** Fix any import ordering issues (`ruff check --fix`).
4. **Rollback:** `git checkout -- .`

---

## Task 2: Define StoreProtocol (Unifying Protocol)

**Files:**
- Create: `miniautogen/core/contracts/store.py`
- Test: `tests/core/contracts/test_store_protocol.py`
- Modify: `miniautogen/core/contracts/__init__.py`

**Prerequisites:**
- Task 1 completed (contracts __init__ already modified)
- Files must exist: `miniautogen/stores/run_store.py`, `miniautogen/stores/checkpoint_store.py`

**Context for executor:** The existing `RunStore` (in `miniautogen/stores/run_store.py`) has methods `save_run(run_id, payload)` and `get_run(run_id)`. The existing `CheckpointStore` (in `miniautogen/stores/checkpoint_store.py`) has `save_checkpoint(run_id, payload)` and `get_checkpoint(run_id)`. The new `StoreProtocol` is a **unifying** protocol with generic `save/get/exists` methods. Existing stores do NOT need to change — the protocol is for NEW store implementations. The test verifies the protocol shape is correct and that new implementations can satisfy it.

**Step 1: Write the failing test**

Create `tests/core/contracts/test_store_protocol.py`:

```python
"""Tests for StoreProtocol — unifying store contract."""

from __future__ import annotations

from miniautogen.core.contracts.store import StoreProtocol


# --- Fake implementations ---


class _FakeStore:
    """Satisfies StoreProtocol structurally."""

    def __init__(self) -> None:
        self._data: dict[str, dict] = {}

    async def save(self, key: str, payload: dict) -> None:
        self._data[key] = payload

    async def get(self, key: str) -> dict | None:
        return self._data.get(key)

    async def exists(self, key: str) -> bool:
        return key in self._data


class _BrokenStore:
    """Does NOT satisfy StoreProtocol — missing exists()."""

    async def save(self, key: str, payload: dict) -> None:
        pass

    async def get(self, key: str) -> dict | None:
        return None


# --- Protocol checks ---


def test_fake_store_satisfies_protocol() -> None:
    store = _FakeStore()
    assert isinstance(store, StoreProtocol)


def test_broken_store_does_not_satisfy_protocol() -> None:
    store = _BrokenStore()
    assert not isinstance(store, StoreProtocol)


def test_store_protocol_exported_from_contracts() -> None:
    from miniautogen.core.contracts import StoreProtocol as SP

    assert SP is not None
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/core/contracts/test_store_protocol.py -v 2>&1 | head -10`

**Expected output:**
```
ERROR tests/core/contracts/test_store_protocol.py
ModuleNotFoundError: No module named 'miniautogen.core.contracts.store'
```

**Step 3: Create StoreProtocol**

Create `miniautogen/core/contracts/store.py`:

```python
"""Unifying store protocol for the MiniAutoGen SDK.

Defines a generic key-value store contract that new store implementations
should satisfy. Existing stores (RunStore, CheckpointStore, MessageStore)
predate this protocol and have specialized method signatures.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class StoreProtocol(Protocol):
    """Generic async key-value store interface.

    New store implementations should satisfy this protocol.
    Existing stores (RunStore, CheckpointStore) use specialized
    method names and are not required to implement this interface.
    """

    async def save(self, key: str, payload: dict) -> None: ...

    async def get(self, key: str) -> dict | None: ...

    async def exists(self, key: str) -> bool: ...
```

**Step 4: Export from contracts __init__**

In `miniautogen/core/contracts/__init__.py`, add:

Import (add after the `from .tool import ...` line):
```python
from .store import StoreProtocol
```

Add to `__all__` (after `"RunStatus",`):
```python
    "StoreProtocol",
```

**Step 5: Run test to verify it passes**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/core/contracts/test_store_protocol.py -v`

**Expected output:**
```
tests/core/contracts/test_store_protocol.py::test_fake_store_satisfies_protocol PASSED
tests/core/contracts/test_store_protocol.py::test_broken_store_does_not_satisfy_protocol PASSED
tests/core/contracts/test_store_protocol.py::test_store_protocol_exported_from_contracts PASSED
```

**Step 6: Run ruff**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && ruff check miniautogen/core/contracts/store.py tests/core/contracts/test_store_protocol.py`

**Expected output:** No errors.

**Step 7: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/core/contracts/store.py tests/core/contracts/test_store_protocol.py miniautogen/core/contracts/__init__.py
git commit -m "feat: add StoreProtocol unifying store contract"
```

**If Task Fails:**

1. **isinstance check fails for _FakeStore:** `runtime_checkable` only checks method names. Ensure all three methods (`save`, `get`, `exists`) have matching signatures.
2. **Rollback:** `git checkout -- .`

---

## Task 3: Contract Test Suite for CoordinationMode

**Files:**
- Create: `tests/core/runtime/test_coordination_contract.py`

**Prerequisites:**
- Tasks 1-2 completed
- Files must exist: `miniautogen/core/contracts/coordination.py`, `miniautogen/core/contracts/run_result.py`, `miniautogen/core/contracts/run_context.py`

**Context for executor:** There are 4 runtimes that implement `CoordinationMode`: `WorkflowRuntime`, `DeliberationRuntime`, `AgenticLoopRuntime`, `CompositeRuntime`. Each has a `kind` attribute and an `async def run(agents, context, plan) -> RunResult` method. This test creates a parametrized contract suite that validates the protocol invariants ALL coordination modes must satisfy.

**Step 1: Write the contract test suite**

Create `tests/core/runtime/test_coordination_contract.py`:

```python
"""Contract tests for CoordinationMode — parametrized across all 4 runtimes.

These tests verify the invariants that ALL coordination modes must satisfy:
1. Satisfies CoordinationMode protocol (isinstance check)
2. Returns RunResult with a valid status
3. Publishes RUN_STARTED and RUN_FINISHED/RUN_FAILED events
4. Respects timeout (anyio.fail_after)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import anyio
import pytest

from miniautogen.core.contracts.agentic_loop import ConversationPolicy, RouterDecision
from miniautogen.core.contracts.coordination import (
    AgenticLoopPlan,
    CoordinationMode,
    DeliberationPlan,
    WorkflowPlan,
    WorkflowStep,
)
from miniautogen.core.contracts.deliberation import Contribution, Review
from miniautogen.core.contracts.enums import RunStatus
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.run_result import RunResult
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.runtime.agentic_loop_runtime import AgenticLoopRuntime
from miniautogen.core.runtime.deliberation_runtime import DeliberationRuntime
from miniautogen.core.runtime.pipeline_runner import PipelineRunner
from miniautogen.core.runtime.workflow_runtime import WorkflowRuntime


# ---------------------------------------------------------------------------
# Fake agents for each coordination mode
# ---------------------------------------------------------------------------


class _FakeWorkflowAgent:
    async def process(self, input_data: Any) -> Any:
        return f"{input_data}-processed"


class _FakeDeliberationAgent:
    """Satisfies DeliberationAgent for testing."""

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id

    async def contribute(self, topic: str) -> Contribution:
        return Contribution(
            participant_id=self.agent_id,
            title=topic,
            content={"body": f"analysis by {self.agent_id}"},
        )

    async def review(self, target_id: str, contribution: Contribution) -> Review:
        return Review(
            reviewer_id=self.agent_id,
            target_id=target_id,
            target_title=contribution.title,
            strengths=["good"],
            concerns=[],
            questions=[],
        )


class _FakeConversationalAgent:
    """Satisfies ConversationalAgent for agentic loop testing."""

    def __init__(self, agent_id: str, terminate_after: int = 1) -> None:
        self.agent_id = agent_id
        self._call_count = 0
        self._terminate_after = terminate_after

    async def reply(self, message: str, context: dict[str, Any]) -> str:
        self._call_count += 1
        return f"reply from {self.agent_id}"

    async def route(self, conversation_history: list[Any]) -> RouterDecision:
        self._call_count += 1
        return RouterDecision(
            current_state_summary="summary",
            missing_information="none",
            next_agent="participant-1",
            terminate=self._call_count >= self._terminate_after,
        )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_context(run_id: str = "contract-run-1") -> RunContext:
    return RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id="contract-corr-1",
        input_payload="initial-input",
    )


def _build_workflow_runtime(
    event_sink: InMemoryEventSink,
) -> tuple[WorkflowRuntime, WorkflowPlan]:
    agent = _FakeWorkflowAgent()
    registry = {"agent-1": agent}
    runner = PipelineRunner(event_sink=event_sink)
    runtime = WorkflowRuntime(runner=runner, agent_registry=registry)
    plan = WorkflowPlan(
        steps=[WorkflowStep(component_name="step1", agent_id="agent-1")],
    )
    return runtime, plan


def _build_deliberation_runtime(
    event_sink: InMemoryEventSink,
) -> tuple[DeliberationRuntime, DeliberationPlan]:
    agents = {
        "leader": _FakeDeliberationAgent("leader"),
        "participant-1": _FakeDeliberationAgent("participant-1"),
    }
    runner = PipelineRunner(event_sink=event_sink)
    runtime = DeliberationRuntime(runner=runner, agent_registry=agents)
    plan = DeliberationPlan(
        topic="test topic",
        participants=["leader", "participant-1"],
        max_rounds=1,
        leader_agent="leader",
    )
    return runtime, plan


def _build_agentic_loop_runtime(
    event_sink: InMemoryEventSink,
) -> tuple[AgenticLoopRuntime, AgenticLoopPlan]:
    agents = {
        "router": _FakeConversationalAgent("router", terminate_after=1),
        "participant-1": _FakeConversationalAgent("participant-1"),
    }
    runner = PipelineRunner(event_sink=event_sink)
    runtime = AgenticLoopRuntime(runner=runner, agent_registry=agents)
    plan = AgenticLoopPlan(
        router_agent="router",
        participants=["participant-1"],
        policy=ConversationPolicy(max_turns=3, timeout_seconds=10.0),
    )
    return runtime, plan


# ---------------------------------------------------------------------------
# Contract 1: All runtimes satisfy CoordinationMode protocol
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "builder",
    [
        _build_workflow_runtime,
        _build_deliberation_runtime,
        _build_agentic_loop_runtime,
    ],
    ids=["workflow", "deliberation", "agentic_loop"],
)
def test_runtime_satisfies_coordination_mode_protocol(builder) -> None:
    event_sink = InMemoryEventSink()
    runtime, _plan = builder(event_sink)
    assert isinstance(runtime, CoordinationMode)


# ---------------------------------------------------------------------------
# Contract 2: Returns RunResult with valid status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "builder",
    [
        _build_workflow_runtime,
        _build_deliberation_runtime,
        _build_agentic_loop_runtime,
    ],
    ids=["workflow", "deliberation", "agentic_loop"],
)
async def test_runtime_returns_run_result_with_valid_status(builder) -> None:
    event_sink = InMemoryEventSink()
    runtime, plan = builder(event_sink)
    ctx = _make_context()
    result = await runtime.run(agents=[], context=ctx, plan=plan)

    assert isinstance(result, RunResult)
    assert result.status in {
        RunStatus.FINISHED,
        RunStatus.FAILED,
        RunStatus.CANCELLED,
        RunStatus.TIMED_OUT,
    }


# ---------------------------------------------------------------------------
# Contract 3: Publishes RUN_STARTED and RUN_FINISHED/RUN_FAILED events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "builder",
    [
        _build_workflow_runtime,
        _build_deliberation_runtime,
        _build_agentic_loop_runtime,
    ],
    ids=["workflow", "deliberation", "agentic_loop"],
)
async def test_runtime_emits_run_started_and_terminal_event(builder) -> None:
    event_sink = InMemoryEventSink()
    runtime, plan = builder(event_sink)
    ctx = _make_context()
    await runtime.run(agents=[], context=ctx, plan=plan)

    event_types = [e.type for e in event_sink.events]
    assert "run_started" in event_types, (
        f"Expected 'run_started' in events, got: {event_types}"
    )
    terminal_events = {"run_finished", "run_failed"}
    assert terminal_events & set(event_types), (
        f"Expected at least one of {terminal_events} in events, got: {event_types}"
    )
```

**Step 2: Run test to verify it passes**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/core/runtime/test_coordination_contract.py -v`

**Expected output:**
```
tests/core/runtime/test_coordination_contract.py::test_runtime_satisfies_coordination_mode_protocol[workflow] PASSED
tests/core/runtime/test_coordination_contract.py::test_runtime_satisfies_coordination_mode_protocol[deliberation] PASSED
tests/core/runtime/test_coordination_contract.py::test_runtime_satisfies_coordination_mode_protocol[agentic_loop] PASSED
tests/core/runtime/test_coordination_contract.py::test_runtime_returns_run_result_with_valid_status[workflow] PASSED
tests/core/runtime/test_coordination_contract.py::test_runtime_returns_run_result_with_valid_status[deliberation] PASSED
tests/core/runtime/test_coordination_contract.py::test_runtime_returns_run_result_with_valid_status[agentic_loop] PASSED
tests/core/runtime/test_coordination_contract.py::test_runtime_emits_run_started_and_terminal_event[workflow] PASSED
tests/core/runtime/test_coordination_contract.py::test_runtime_emits_run_started_and_terminal_event[deliberation] PASSED
tests/core/runtime/test_coordination_contract.py::test_runtime_emits_run_started_and_terminal_event[agentic_loop] PASSED
```

**If deliberation or agentic_loop tests fail:** These runtimes have more complex setup requirements. Check if `DeliberationRuntime.__init__` or `AgenticLoopRuntime.__init__` expect different constructor arguments by reading the runtime files. Adjust the builder functions accordingly.

**Step 3: Run ruff**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && ruff check tests/core/runtime/test_coordination_contract.py`

**Expected output:** No errors.

**Step 4: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add tests/core/runtime/test_coordination_contract.py
git commit -m "test: add parametrized contract test suite for CoordinationMode"
```

**If Task Fails:**

1. **DeliberationRuntime constructor differs:** Read `miniautogen/core/runtime/deliberation_runtime.py` fully to check constructor signature. It may need `agent_registry` with specific agent ID matching the plan's `participants` and `leader_agent`.
2. **AgenticLoopRuntime constructor differs:** Read `miniautogen/core/runtime/agentic_loop_runtime.py` fully. It may need `agent_registry` with specific agent IDs matching the plan's `router_agent` and `participants`.
3. **Events not matching:** Some runtimes may emit `deliberation_started` instead of `run_started`. If so, adjust the assertions for that specific runtime to check its native event types.
4. **Rollback:** `git checkout -- tests/core/runtime/test_coordination_contract.py`

---

## Task 4: Mark SubrunRequest as Experimental

**Files:**
- Modify: `miniautogen/core/contracts/coordination.py` (lines 109-125)
- Create: `tests/core/contracts/test_subrun_experimental.py`

**Prerequisites:**
- File exists: `miniautogen/core/contracts/coordination.py`
- Existing tests pass: `tests/core/contracts/test_subrun_request.py`

**Context for executor:** `SubrunRequest` at line 112-125 of `miniautogen/core/contracts/coordination.py` is defined but unused in any runtime. The plan is to add a docstring stability marker and a module-level constant, NOT to remove it.

**Step 1: Write the test**

Create `tests/core/contracts/test_subrun_experimental.py`:

```python
"""Tests for SubrunRequest experimental stability marker."""

from miniautogen.core.contracts.coordination import SubrunRequest, STABILITY_EXPERIMENTAL


def test_subrun_request_has_experimental_marker_in_docstring() -> None:
    assert "STABILITY: EXPERIMENTAL" in (SubrunRequest.__doc__ or "")


def test_stability_experimental_constant_is_true() -> None:
    assert STABILITY_EXPERIMENTAL is True


def test_subrun_request_import_works() -> None:
    """SubrunRequest must remain importable from the public contracts."""
    from miniautogen.core.contracts import SubrunRequest as SR

    assert SR is not None
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/core/contracts/test_subrun_experimental.py -v 2>&1 | head -15`

**Expected output:**
```
FAILED tests/core/contracts/test_subrun_experimental.py::test_subrun_request_has_experimental_marker_in_docstring
FAILED tests/core/contracts/test_subrun_experimental.py::test_stability_experimental_constant_is_true
```

**Step 3: Modify SubrunRequest**

In `miniautogen/core/contracts/coordination.py`, make these changes:

1. Add constant before the `SubrunRequest` class (after line 108, before `# --- Subrun contracts ---`):

Replace the section starting at line 109:

```python
# --- Subrun contracts ---

STABILITY_EXPERIMENTAL = True
"""Marker indicating that SubrunRequest is not yet used by any runtime."""


class SubrunRequest(BaseModel):
    """Request to execute a nested coordination run.

    STABILITY: EXPERIMENTAL — This contract is defined for future use by
    CompositeRuntime sub-execution. It is not consumed by any runtime today.
    Do not depend on its shape remaining stable.

    Enables nested execution: e.g., a workflow step that triggers
    a sub-deliberation, or a deliberation round that spawns a sub-workflow.
    """

    mode: CoordinationKind
    plan: CoordinationPlan
    label: str = ""
    input_key: str | None = None
    output_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/core/contracts/test_subrun_experimental.py tests/core/contracts/test_subrun_request.py -v`

**Expected output:**
```
tests/core/contracts/test_subrun_experimental.py::test_subrun_request_has_experimental_marker_in_docstring PASSED
tests/core/contracts/test_subrun_experimental.py::test_stability_experimental_constant_is_true PASSED
tests/core/contracts/test_subrun_experimental.py::test_subrun_request_import_works PASSED
tests/core/contracts/test_subrun_request.py::test_subrun_request_has_required_fields PASSED
tests/core/contracts/test_subrun_request.py::test_subrun_request_defaults PASSED
tests/core/contracts/test_subrun_request.py::test_subrun_request_with_io_keys PASSED
tests/core/contracts/test_subrun_request.py::test_subrun_request_serialization_roundtrip PASSED
```

**Step 5: Run ruff**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && ruff check miniautogen/core/contracts/coordination.py tests/core/contracts/test_subrun_experimental.py`

**Expected output:** No errors.

**Step 6: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/core/contracts/coordination.py tests/core/contracts/test_subrun_experimental.py
git commit -m "docs: mark SubrunRequest as STABILITY_EXPERIMENTAL"
```

**If Task Fails:**

1. **Existing subrun tests break:** The docstring change should not affect behavior. If tests break, check that the class body was not accidentally modified.
2. **Import error on STABILITY_EXPERIMENTAL:** Make sure the constant is at module level, not inside the class.
3. **Rollback:** `git checkout -- miniautogen/core/contracts/coordination.py`

---

## Task 5: Legacy Pipeline Cutover Preparation

**Files:**
- Modify: `miniautogen/compat/state_bridge.py` (line 8)
- Modify: `miniautogen/pipeline/pipeline.py` (line 35, the `run` method)
- Create: `tests/compat/test_pipeline_cutover.py`

**Prerequisites:**
- Tasks 1-4 completed
- All existing tests pass: `python -m pytest --tb=short -q`

**Context for executor:** `miniautogen/compat/state_bridge.py` has `RUNTIME_RUNNER_CUTOVER_READY = False` at line 8. The `Pipeline` class in `miniautogen/pipeline/pipeline.py` is the legacy executor — `PipelineRunner` in `miniautogen/core/runtime/pipeline_runner.py` is the canonical replacement. Flipping the flag and adding a deprecation warning signals consumers to migrate.

**Step 1: Write the failing test**

Create `tests/compat/test_pipeline_cutover.py`:

```python
"""Tests for legacy Pipeline cutover readiness."""

from __future__ import annotations

import warnings


def test_runtime_runner_cutover_ready_is_true() -> None:
    from miniautogen.compat.state_bridge import RUNTIME_RUNNER_CUTOVER_READY

    assert RUNTIME_RUNNER_CUTOVER_READY is True


def test_pipeline_run_emits_deprecation_warning() -> None:
    """Pipeline.run() must emit a DeprecationWarning."""
    import asyncio
    from miniautogen.pipeline.pipeline import Pipeline

    pipeline = Pipeline(components=[])

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        asyncio.get_event_loop().run_until_complete(pipeline.run({}))

    deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
    assert len(deprecation_warnings) >= 1, (
        f"Expected DeprecationWarning, got: {[x.category.__name__ for x in w]}"
    )
    assert "PipelineRunner" in str(deprecation_warnings[0].message)
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/compat/test_pipeline_cutover.py -v 2>&1 | head -20`

**Expected output:**
```
FAILED tests/compat/test_pipeline_cutover.py::test_runtime_runner_cutover_ready_is_true - AssertionError
FAILED tests/compat/test_pipeline_cutover.py::test_pipeline_run_emits_deprecation_warning
```

**If directory doesn't exist:** Create `tests/compat/` first with `mkdir -p tests/compat`.

**Step 3: Flip the cutover flag**

In `miniautogen/compat/state_bridge.py`, change line 8:

```python
RUNTIME_RUNNER_CUTOVER_READY = True
```

**Step 4: Add deprecation warning to Pipeline.run()**

In `miniautogen/pipeline/pipeline.py`, modify the `run` method (starting at line 35). Add a `warnings` import at the top and a `warnings.warn` call at the beginning of `run`:

Add at the top of the file (after existing imports, around line 3):
```python
import warnings
```

Replace the `run` method body (lines 35-48) with:

```python
    async def run(self, state: Any) -> Any:
        """
        Executes the pipeline on the provided state asynchronously,
        passing the state from each component to the next.

        .. deprecated::
            Use ``PipelineRunner.run_pipeline()`` instead. The Pipeline class
            will be removed in a future release.

        Args:
            state (ChatPipelineState): State of the chat to be processed.

        Returns:
            ChatPipelineState: State of the chat after processing all components.
        """
        warnings.warn(
            "Pipeline.run() is deprecated. Use PipelineRunner.run_pipeline() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        for component in self.components:
            state = await component.process(state)
        return state
```

**Step 5: Run test to verify it passes**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/compat/test_pipeline_cutover.py -v`

**Expected output:**
```
tests/compat/test_pipeline_cutover.py::test_runtime_runner_cutover_ready_is_true PASSED
tests/compat/test_pipeline_cutover.py::test_pipeline_run_emits_deprecation_warning PASSED
```

**Step 6: Run ALL existing tests to check for regressions**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest --tb=short -q 2>&1 | tail -5`

**Expected output:** All tests pass. Some tests may now emit `DeprecationWarning` — that is expected behavior.

**IMPORTANT:** If any existing tests FAIL because they call `Pipeline.run()` with `warnings.filterwarnings("error")`, those tests need `@pytest.mark.filterwarnings("ignore::DeprecationWarning")` added. Check the output carefully.

**Step 7: Run ruff**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && ruff check miniautogen/compat/state_bridge.py miniautogen/pipeline/pipeline.py tests/compat/test_pipeline_cutover.py`

**Expected output:** No errors.

**Step 8: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/compat/state_bridge.py miniautogen/pipeline/pipeline.py tests/compat/test_pipeline_cutover.py
git commit -m "feat: flip RUNTIME_RUNNER_CUTOVER_READY and deprecate Pipeline.run()"
```

**If Task Fails:**

1. **Existing pipeline tests break:** Some tests may use `Pipeline.run()` and fail if they treat warnings as errors. Fix by adding `@pytest.mark.filterwarnings("ignore::DeprecationWarning")` to those tests, or by filtering in the test's conftest.
2. **asyncio.get_event_loop() deprecation:** If on Python 3.10+, you may see a deprecation for `get_event_loop()`. Rewrite the test to use `anyio.run()` or `pytest.mark.asyncio` instead:
   ```python
   @pytest.mark.asyncio
   async def test_pipeline_run_emits_deprecation_warning() -> None:
       from miniautogen.pipeline.pipeline import Pipeline
       pipeline = Pipeline(components=[])
       with warnings.catch_warnings(record=True) as w:
           warnings.simplefilter("always")
           await pipeline.run({})
       deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
       assert len(deprecation_warnings) >= 1
       assert "PipelineRunner" in str(deprecation_warnings[0].message)
   ```
3. **Rollback:** `git checkout -- miniautogen/compat/state_bridge.py miniautogen/pipeline/pipeline.py`

---

## Task 6: Stabilize api.py Exports

**Files:**
- Modify: `miniautogen/api.py`
- Modify: `tests/test_api_exports.py`

**Prerequisites:**
- Tasks 1-5 completed (ToolProtocol, ToolResult, StoreProtocol exist in contracts)
- All tests pass

**Context for executor:** `miniautogen/api.py` is the public surface of the SDK. It currently exports 30+ symbols. We need to add `ToolProtocol`, `ToolResult`, and `StoreProtocol`, then add a comprehensive `__all__` verification test.

**Step 1: Write the failing test**

Add the following tests to `tests/test_api_exports.py` (append at end of file):

```python
def test_api_exports_tool_contracts() -> None:
    from miniautogen.api import ToolProtocol, ToolResult

    assert ToolProtocol is not None
    assert ToolResult is not None


def test_api_exports_store_protocol() -> None:
    from miniautogen.api import StoreProtocol

    assert StoreProtocol is not None


def test_api_all_matches_actual_exports() -> None:
    """Verify __all__ contains exactly the symbols that are importable."""
    import miniautogen.api as api

    declared = set(api.__all__)
    # Every name in __all__ must be an actual attribute
    for name in declared:
        assert hasattr(api, name), f"__all__ declares '{name}' but it is not importable"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/test_api_exports.py -v 2>&1 | tail -20`

**Expected output:**
```
FAILED tests/test_api_exports.py::test_api_exports_tool_contracts - ImportError
FAILED tests/test_api_exports.py::test_api_exports_store_protocol - ImportError
```

**Step 3: Add new exports to api.py**

In `miniautogen/api.py`, make these changes:

1. Add import for tool contracts (after the agent protocol imports, around line 23):

```python
from miniautogen.core.contracts.tool import ToolProtocol, ToolResult
```

2. Add import for store protocol (after the tool import):

```python
from miniautogen.core.contracts.store import StoreProtocol
```

3. Add to `__all__` list. Insert in the appropriate sections:

After `"WorkflowAgent",` in the `# Agent protocols` section:
```python
    # Tool contracts
    "ToolProtocol",
    "ToolResult",
    # Store protocol
    "StoreProtocol",
```

The complete updated `__all__` should be:

```python
__all__ = [
    # Core contracts
    "ExecutionEvent",
    "LoopStopReason",
    "Message",
    "RunContext",
    "RunResult",
    "RunStatus",
    "Conversation",
    # Agent protocols
    "WorkflowAgent",
    "DeliberationAgent",
    "ConversationalAgent",
    # Tool contracts
    "ToolProtocol",
    "ToolResult",
    # Store protocol
    "StoreProtocol",
    # Agentic loop
    "RouterDecision",
    "ConversationPolicy",
    "AgenticLoopState",
    "AgenticLoopPlan",
    # Deliberation (general + specialized)
    "Contribution",
    "Review",
    # Coordination
    "CoordinationKind",
    "CoordinationPlan",
    "DeliberationPlan",
    "WorkflowPlan",
    "WorkflowStep",
    "CompositionStep",
    "SubrunRequest",
    # Runtimes (Coordination Modes)
    "AgenticLoopRuntime",
    "CompositeRuntime",
    "DeliberationRuntime",
    "PipelineRunner",
    "WorkflowRuntime",
    # Pipeline
    "Pipeline",
    "PipelineComponent",
    # Policy enforcement
    "BudgetTracker",
    "BudgetExceededError",
    # Backend driver abstraction
    "AgentDriver",
    "BackendCapabilities",
    "BackendResolver",
]
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/test_api_exports.py -v`

**Expected output:**
```
tests/test_api_exports.py::test_api_exports_all_core_contracts PASSED
tests/test_api_exports.py::test_api_exports_agent_protocols PASSED
tests/test_api_exports.py::test_api_exports_coordination PASSED
tests/test_api_exports.py::test_api_exports_runtimes PASSED
tests/test_api_exports.py::test_api_exports_deliberation_generals PASSED
tests/test_api_exports.py::test_api_exports_policy_enforcement PASSED
tests/test_api_exports.py::test_api_exports_agentic_loop_contracts PASSED
tests/test_api_exports.py::test_api_exports_tool_contracts PASSED
tests/test_api_exports.py::test_api_exports_store_protocol PASSED
tests/test_api_exports.py::test_api_all_matches_actual_exports PASSED
```

**Step 5: Run ALL tests**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest --tb=short -q 2>&1 | tail -5`

**Expected output:** All tests pass including the new ones.

**Step 6: Run ruff**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && ruff check miniautogen/api.py tests/test_api_exports.py`

**Expected output:** No errors.

**Step 7: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/api.py tests/test_api_exports.py
git commit -m "feat: add ToolProtocol, ToolResult, StoreProtocol to public API"
```

**If Task Fails:**

1. **Import error for backends:** If `miniautogen.backends` module fails to import (e.g., missing dependency), that is a pre-existing issue. The `test_api_all_matches_actual_exports` test will catch this. Fix by ensuring the backends module is importable.
2. **__all__ mismatch:** If the test finds a symbol in `__all__` that is not importable, remove it from `__all__`.
3. **Rollback:** `git checkout -- miniautogen/api.py tests/test_api_exports.py`

---

## Task 7: Full Regression Check

**Files:** None (verification only)

**Prerequisites:** Tasks 1-6 completed

**Step 1: Run the complete test suite**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest --tb=short -q`

**Expected output:** All tests pass (400+ existing + ~20 new tests).

```
NNN passed in X.XXs
```

**Step 2: Run ruff on all changed files**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && ruff check miniautogen/core/contracts/tool.py miniautogen/core/contracts/store.py miniautogen/core/contracts/__init__.py miniautogen/core/contracts/coordination.py miniautogen/compat/state_bridge.py miniautogen/pipeline/pipeline.py miniautogen/api.py`

**Expected output:** No errors.

**Step 3: Verify git log shows 6 clean commits**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && git log --oneline -6`

**Expected output:**
```
<hash> feat: add ToolProtocol, ToolResult, StoreProtocol to public API
<hash> feat: flip RUNTIME_RUNNER_CUTOVER_READY and deprecate Pipeline.run()
<hash> docs: mark SubrunRequest as STABILITY_EXPERIMENTAL
<hash> test: add parametrized contract test suite for CoordinationMode
<hash> feat: add StoreProtocol unifying store contract
<hash> feat: add ToolProtocol and ToolResult contracts
```

**If Task Fails:**

1. **Test failures:** Read the failure output carefully. Most likely cause is import issues from the new modules. Ensure all `__init__.py` files are updated.
2. **Ruff failures:** Run `ruff check --fix` on the offending files.
3. **Do NOT proceed to code review if tests fail.**

---

## Code Review Checkpoint

After completing all tasks, run parallel code review with:

### Task 8: Run Code Review

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
- This tracks tech debt for future resolution

**Cosmetic/Nitpick Issues:**
- Add `FIXME(nitpick):` comments in code at the relevant location
- Format: `FIXME(nitpick): [Issue description] (reported by [reviewer] on [date], severity: Cosmetic)`
- Low-priority improvements tracked inline

3. **Proceed only when:**
   - Zero Critical/High/Medium issues remain
   - All Low issues have TODO(review): comments added
   - All Cosmetic issues have FIXME(nitpick): comments added
