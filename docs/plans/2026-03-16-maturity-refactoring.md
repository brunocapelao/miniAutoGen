# Maturity Refactoring: Concurrency, State Typing, Resource Management

> **For Agents:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Eliminate technical debt in fan-out exception handling, magic string status/stop-reason literals, and timeout enforcement across MiniAutoGen runtimes.

**Architecture:** Three surgical interventions: (1) Replace manual `error_holder` in `_run_fan_out` with native `ExceptionGroup` propagation, (2) Introduce `RunStatus` and `LoopStopReason` enums to replace all magic strings, (3) Add `RUN_TIMED_OUT` event emission to the agentic loop timeout path. The timeout `anyio.fail_after` wrapper already exists in the codebase -- we only add the missing event emission.

**Tech Stack:** Python 3.10+, anyio >=4.0.0, pydantic >=2.5.0, pytest >=7.4.0, pytest-asyncio >=0.23.0

**Global Prerequisites:**
- Environment: macOS, Python 3.10 or 3.11
- Tools: poetry, pytest, ruff
- Access: No external services required
- State: Branch from `main` (commit `f262cda`), clean working tree

**Verification before starting:**
```bash
cd /Users/brunocapelao/Projects/miniAutoGen
python --version        # Expected: Python 3.10.x or 3.11.x
poetry --version        # Expected: Poetry 1.x+
pytest --version        # Expected: pytest 7.x+
git status              # Expected: clean working tree on main
pytest --tb=short -q    # Expected: all tests pass
```

---

## Intervention 1: Fan-Out ExceptionGroup Propagation

### Task 1: Write failing test for multi-error fan-out

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/tests/core/runtime/test_workflow_runtime.py`

**Prerequisites:**
- All existing tests pass (`pytest --tb=short -q`)

**Step 1: Write the failing test**

Add the following test at the end of `/Users/brunocapelao/Projects/miniAutoGen/tests/core/runtime/test_workflow_runtime.py`:

```python
@pytest.mark.asyncio
async def test_fan_out_multiple_failures_returns_all_errors() -> None:
    """When multiple parallel branches fail, all errors are captured in the result."""

    class _FailAgentA:
        async def process(self, input_data: Any) -> Any:
            raise RuntimeError("branch-A exploded")

    class _FailAgentB:
        async def process(self, input_data: Any) -> Any:
            raise RuntimeError("branch-B exploded")

    registry: dict[str, Any] = {"fail_a": _FailAgentA(), "fail_b": _FailAgentB()}
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    runtime = WorkflowRuntime(runner=runner, agent_registry=registry)

    plan = WorkflowPlan(
        steps=[
            WorkflowStep(component_name="step1", agent_id="fail_a"),
            WorkflowStep(component_name="step2", agent_id="fail_b"),
        ],
        fan_out=True,
    )
    ctx = _make_context()
    result = await runtime.run(agents=[], context=ctx, plan=plan)

    assert result.status == "failed"
    assert result.error is not None
    # The error message must mention BOTH failures, not just the first one
    assert "branch-A exploded" in result.error
    assert "branch-B exploded" in result.error
```

**Step 2: Run the test to verify it fails**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/core/runtime/test_workflow_runtime.py::test_fan_out_multiple_failures_returns_all_errors -v`

**Expected output:**
```
FAILED tests/core/runtime/test_workflow_runtime.py::test_fan_out_multiple_failures_returns_all_errors
```

The test will fail because the current implementation only captures `error_holder[0]` (the first error), discarding subsequent failures. The assertion `"branch-B exploded" in result.error` (or `"branch-A exploded"`) will fail since only one error is reported.

**If you see a different error:** Ensure the test imports are correct -- the file already imports `Any`, `pytest`, `WorkflowPlan`, `WorkflowStep`, `InMemoryEventSink`, `PipelineRunner`, `WorkflowRuntime` at the top.

---

### Task 2: Remove error_holder and let ExceptionGroup propagate naturally

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/runtime/workflow_runtime.py`

**Prerequisites:**
- Task 1 test exists and fails

**Step 1: Replace the `_run_fan_out` method**

In `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/runtime/workflow_runtime.py`, find the `_run_fan_out` method (lines 136-165) and replace it entirely with:

```python
    async def _run_fan_out(
        self,
        context: RunContext,
        plan: WorkflowPlan,
    ) -> list[Any]:
        """Execute all steps in parallel, returning a list of outputs."""
        initial_input = context.input_payload
        results: list[Any] = [None] * len(plan.steps)

        async def _run_branch(index: int, step: Any) -> None:
            if step.agent_id is None:
                results[index] = initial_input
            else:
                results[index] = await self._invoke_agent(step.agent_id, initial_input)

        async with anyio.create_task_group() as tg:
            for i, step in enumerate(plan.steps):
                tg.start_soon(_run_branch, i, step)

        return results
```

Key changes:
- Removed `error_holder: list[Exception] = []`
- Removed the `try/except` inside `_run_branch` -- exceptions now propagate directly to the TaskGroup
- Removed the outer `try/except BaseException` that re-raised `error_holder[0]`
- AnyIO's TaskGroup will naturally produce an `ExceptionGroup` (or `BaseExceptionGroup` on Python 3.10 via the `exceptiongroup` backport, which is already a transitive dependency of `anyio`)

**Step 2: Update the `run` method to handle `ExceptionGroup`**

In the same file, find the `except Exception as exc:` block in the `run` method (line 90-98). Replace:

```python
        except Exception as exc:
            await self._emit(
                event_type=EventType.RUN_FAILED.value,
                run_id=run_id,
                correlation_id=correlation_id,
                payload={"error": str(exc)},
            )
            logger.error("workflow_failed", error=str(exc))
            return RunResult(run_id=run_id, status="failed", error=str(exc))
```

with:

```python
        except BaseException as exc:
            if isinstance(exc, BaseExceptionGroup):
                error_messages = [str(e) for e in exc.exceptions]
                combined_error = "; ".join(error_messages)
            else:
                combined_error = str(exc)
            await self._emit(
                event_type=EventType.RUN_FAILED.value,
                run_id=run_id,
                correlation_id=correlation_id,
                payload={"error": combined_error},
            )
            logger.error("workflow_failed", error=combined_error)
            return RunResult(run_id=run_id, status="failed", error=combined_error)
```

**Step 3: Add the compatibility import for `BaseExceptionGroup`**

At the top of `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/runtime/workflow_runtime.py`, after the existing imports (after line 11 `import anyio`), add:

```python
import sys

if sys.version_info >= (3, 11):
    pass  # BaseExceptionGroup is a builtin
else:
    from exceptiongroup import BaseExceptionGroup  # type: ignore[no-redef]
```

Note: `exceptiongroup` is already a transitive dependency of `anyio` (confirmed in `poetry.lock`), so no new library is introduced.

---

### Task 3: Verify fan-out ExceptionGroup tests pass

**Files:** None (verification only)

**Prerequisites:**
- Task 2 implementation is complete

**Step 1: Run the new test**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/core/runtime/test_workflow_runtime.py::test_fan_out_multiple_failures_returns_all_errors -v`

**Expected output:**
```
PASSED tests/core/runtime/test_workflow_runtime.py::test_fan_out_multiple_failures_returns_all_errors
```

**Step 2: Run ALL workflow runtime tests to ensure no regressions**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/core/runtime/test_workflow_runtime.py -v`

**Expected output:**
```
All tests PASSED (10 passed)
```

Key tests to confirm still pass:
- `test_fan_out_one_branch_fails` -- single failure still works
- `test_fan_out_parallel_execution` -- happy path still works
- `test_step_failure_returns_error_result` -- sequential failure unaffected

**If `test_fan_out_one_branch_fails` fails:** The existing test checks `"step exploded" in result.error`. With the new `ExceptionGroup` handling, a single error inside a group will still be captured. If anyio wraps a single exception in a group, the "; ".join will produce just `"step exploded"` which should still match. If it does not match, verify that `BaseExceptionGroup` with a single exception still lists that exception in `.exceptions`.

**Step 3: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add tests/core/runtime/test_workflow_runtime.py miniautogen/core/runtime/workflow_runtime.py
git commit -m "refactor: replace error_holder with native ExceptionGroup in fan-out

Remove manual error_holder list from _run_fan_out. Let exceptions
propagate naturally to anyio TaskGroup, which produces ExceptionGroup
on multiple failures. The run() method now catches BaseExceptionGroup
and reports all error messages joined by semicolons."
```

**If Task Fails:**

1. **Import error for `BaseExceptionGroup`:**
   - Check: `python -c "from exceptiongroup import BaseExceptionGroup"` -- should succeed since anyio depends on it
   - If fails: run `poetry install` to ensure dependencies are up to date
   - Rollback: `git checkout -- miniautogen/core/runtime/workflow_runtime.py`

2. **Single-failure test breaks:**
   - The `BaseExceptionGroup` check handles both single and multiple exceptions
   - Debug: Add `print(repr(exc))` before the isinstance check to see the actual exception type
   - If anyio does NOT wrap a single exception in ExceptionGroup (it re-raises the single exception directly), the `else` branch handles it

3. **Can't recover:**
   - Rollback: `git checkout -- .`
   - Document what failed and return to human partner

---

## Intervention 2: Eradicate Primitive Obsession (Magic Strings)

### Task 4: Write failing test for RunStatus enum

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/core/contracts/test_enums.py`

**Prerequisites:**
- Task 3 complete (or independent -- this task can be done in parallel with Intervention 1)

**Step 1: Write the test**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/core/contracts/test_enums.py`:

```python
"""Tests for RunStatus and LoopStopReason enums."""

from miniautogen.core.contracts.enums import LoopStopReason, RunStatus


def test_run_status_values() -> None:
    """RunStatus enum has the expected string values."""
    assert RunStatus.FINISHED == "finished"
    assert RunStatus.FAILED == "failed"
    assert RunStatus.CANCELLED == "cancelled"
    assert RunStatus.TIMED_OUT == "timed_out"


def test_loop_stop_reason_values() -> None:
    """LoopStopReason enum has the expected string values."""
    assert LoopStopReason.MAX_TURNS == "max_turns"
    assert LoopStopReason.ROUTER_TERMINATED == "router_terminated"
    assert LoopStopReason.STAGNATION == "stagnation"
    assert LoopStopReason.TIMEOUT == "timeout"


def test_run_status_is_str_enum() -> None:
    """RunStatus values are usable as plain strings (str Enum)."""
    status: str = RunStatus.FINISHED
    assert status == "finished"
    assert isinstance(status, str)


def test_loop_stop_reason_is_str_enum() -> None:
    """LoopStopReason values are usable as plain strings (str Enum)."""
    reason: str = LoopStopReason.MAX_TURNS
    assert reason == "max_turns"
    assert isinstance(reason, str)
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/core/contracts/test_enums.py -v`

**Expected output:**
```
ERROR - ModuleNotFoundError: No module named 'miniautogen.core.contracts.enums'
```

---

### Task 5: Create the enums module

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/contracts/enums.py`

**Prerequisites:**
- Task 4 test exists

**Step 1: Create the enums module**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/contracts/enums.py`:

```python
"""Typed enums replacing magic strings in runtime coordination."""

from enum import Enum


class RunStatus(str, Enum):
    """Terminal status of a coordination run."""

    FINISHED = "finished"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class LoopStopReason(str, Enum):
    """Reason why an agentic loop stopped iterating."""

    MAX_TURNS = "max_turns"
    ROUTER_TERMINATED = "router_terminated"
    STAGNATION = "stagnation"
    TIMEOUT = "timeout"
```

**Step 2: Run the enums test**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/core/contracts/test_enums.py -v`

**Expected output:**
```
PASSED tests/core/contracts/test_enums.py::test_run_status_values
PASSED tests/core/contracts/test_enums.py::test_loop_stop_reason_values
PASSED tests/core/contracts/test_enums.py::test_run_status_is_str_enum
PASSED tests/core/contracts/test_enums.py::test_loop_stop_reason_is_str_enum
```

**Step 3: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/core/contracts/enums.py tests/core/contracts/test_enums.py
git commit -m "feat: add RunStatus and LoopStopReason enums

Introduce str-based enums to replace magic string literals for run
status and loop stop reasons. Being str enums, they are backward
compatible with existing string comparisons."
```

---

### Task 6: Export enums from contracts package

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/contracts/__init__.py`

**Prerequisites:**
- Task 5 complete

**Step 1: Add enum imports to contracts `__init__.py`**

In `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/contracts/__init__.py`, add the import line. Find:

```python
from .events import ExecutionEvent
```

and add BEFORE it:

```python
from .enums import LoopStopReason, RunStatus
```

Then add `"LoopStopReason"` and `"RunStatus"` to the `__all__` list, maintaining alphabetical order. Find:

```python
    "Message",
```

and add BEFORE it:

```python
    "LoopStopReason",
```

Find:

```python
    "RunContext",
```

and add BEFORE it:

```python
    "RunStatus",
```

**Step 2: Add exports to public API**

In `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/api.py`, find:

```python
from miniautogen.core.contracts import (
    ExecutionEvent,
    Message,
    RunContext,
    RunResult,
)
```

and replace with:

```python
from miniautogen.core.contracts import (
    ExecutionEvent,
    LoopStopReason,
    Message,
    RunContext,
    RunResult,
    RunStatus,
)
```

Then add `"LoopStopReason"` and `"RunStatus"` to the `__all__` list in `api.py`. Find:

```python
    # Core contracts
    "Message",
```

and replace with:

```python
    # Core contracts
    "LoopStopReason",
    "Message",
```

Find:

```python
    "RunContext",
```

and add BEFORE it:

```python
    "RunStatus",
```

**Step 3: Verify imports work**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -c "from miniautogen.api import RunStatus, LoopStopReason; print(RunStatus.FINISHED, LoopStopReason.MAX_TURNS)"`

**Expected output:**
```
finished max_turns
```

**Step 4: Run full test suite to verify no regressions**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/core/contracts/ -v --tb=short`

**Expected output:** All tests pass.

**Step 5: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/core/contracts/__init__.py miniautogen/api.py
git commit -m "feat: export RunStatus and LoopStopReason from contracts and public API"
```

---

### Task 7: Replace magic strings in WorkflowRuntime with RunStatus

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/runtime/workflow_runtime.py`

**Prerequisites:**
- Task 6 complete

**Step 1: Add the import**

In `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/runtime/workflow_runtime.py`, find:

```python
from miniautogen.core.contracts.coordination import (
    CoordinationKind,
    WorkflowPlan,
)
```

and add after it:

```python
from miniautogen.core.contracts.enums import RunStatus
```

**Step 2: Replace all `status="failed"` and `status="finished"` literals**

There are exactly 3 occurrences in this file:

1. Line 68 -- validation error return:
   Replace `status="failed"` with `status=RunStatus.FAILED`

2. Inside the `except BaseException as exc:` block (from Task 2):
   Replace `status="failed"` with `status=RunStatus.FAILED`

3. Line 104 -- success return:
   Replace `status="finished"` with `status=RunStatus.FINISHED`

**Step 3: Run workflow runtime tests**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/core/runtime/test_workflow_runtime.py -v`

**Expected output:** All tests pass. Because `RunStatus` is a `str` enum, `RunStatus.FAILED == "failed"` is `True`, so existing test assertions like `assert result.status == "failed"` still pass.

**Step 4: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/core/runtime/workflow_runtime.py
git commit -m "refactor: replace magic status strings with RunStatus enum in WorkflowRuntime"
```

---

### Task 8: Replace magic strings in AgenticLoopRuntime with RunStatus and LoopStopReason

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/runtime/agentic_loop_runtime.py`

**Prerequisites:**
- Task 6 complete

**Step 1: Add the imports**

In `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/runtime/agentic_loop_runtime.py`, find:

```python
from miniautogen.core.contracts.coordination import (
    AgenticLoopPlan,
    CoordinationKind,
)
```

and add after it:

```python
from miniautogen.core.contracts.enums import LoopStopReason, RunStatus
```

**Step 2: Replace all magic strings**

Replace all occurrences in the file:

| Line | Old | New |
|------|-----|-----|
| 77 | `status="failed"` | `status=RunStatus.FAILED` |
| 101 | `stop_reason = "max_turns"` | `stop_reason = LoopStopReason.MAX_TURNS` |
| 110 | `stop_reason = reason or "max_turns"` | `stop_reason = reason or LoopStopReason.MAX_TURNS` |
| 136 | `stop_reason = "router_terminated"` | `stop_reason = LoopStopReason.ROUTER_TERMINATED` |
| 148 | `stop_reason = "stagnation"` | `stop_reason = LoopStopReason.STAGNATION` |
| 161 | `status="failed"` | `status=RunStatus.FAILED` |
| 199 | `stop_reason = "timeout"` | `stop_reason = LoopStopReason.TIMEOUT` |
| 202 | `status="failed"` | `status=RunStatus.FAILED` |
| 222 | `status="finished"` | `status=RunStatus.FINISHED` |

**Step 3: Update the `stop_reason` variable type annotation**

Line 101: Change from:

```python
        stop_reason = "max_turns"
```

to:

```python
        stop_reason: str = LoopStopReason.MAX_TURNS
```

The type annotation `str` is kept for compatibility since `LoopStopReason` is a `str` enum.

**Step 4: Run agentic loop runtime tests**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/core/runtime/test_agentic_loop_runtime.py -v`

**Expected output:** All tests pass. String comparisons like `result.metadata["stop_reason"] == "router_terminated"` still work because `LoopStopReason.ROUTER_TERMINATED == "router_terminated"` is `True`.

**Step 5: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/core/runtime/agentic_loop_runtime.py
git commit -m "refactor: replace magic strings with RunStatus/LoopStopReason enums in AgenticLoopRuntime"
```

---

### Task 9: Replace magic strings in should_stop_loop helper

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/runtime/agentic_loop.py`

**Prerequisites:**
- Task 6 complete

**Step 1: Add the import**

In `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/runtime/agentic_loop.py`, find:

```python
from miniautogen.core.contracts.agentic_loop import (
    AgenticLoopState,
    ConversationPolicy,
    RouterDecision,
)
```

and add after it:

```python
from miniautogen.core.contracts.enums import LoopStopReason
```

**Step 2: Replace the magic string**

Find:

```python
        return True, "max_turns"
```

Replace with:

```python
        return True, LoopStopReason.MAX_TURNS
```

**Step 3: Run the helper tests**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/core/runtime/test_agentic_loop_runtime.py::test_should_stop_loop_when_max_turns_is_reached -v`

**Expected output:**
```
PASSED tests/core/runtime/test_agentic_loop_runtime.py::test_should_stop_loop_when_max_turns_is_reached
```

The test asserts `reason == "max_turns"` which still passes since `LoopStopReason.MAX_TURNS == "max_turns"`.

**Step 4: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/core/runtime/agentic_loop.py
git commit -m "refactor: use LoopStopReason enum in should_stop_loop helper"
```

---

### Task 10: Replace magic strings in DeliberationRuntime and CompositeRuntime

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/runtime/deliberation_runtime.py`
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/runtime/composite_runtime.py`

**Prerequisites:**
- Task 6 complete

**Step 1: Update DeliberationRuntime**

In `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/runtime/deliberation_runtime.py`, add the import after existing coordination imports:

```python
from miniautogen.core.contracts.enums import RunStatus
```

Then replace all `status="failed"` with `status=RunStatus.FAILED` (9 occurrences at lines 88, 98, 108, 162, 203, 241, 281) and `status="finished"` with `status=RunStatus.FINISHED` (1 occurrence at line 300).

**Step 2: Update CompositeRuntime**

In `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/runtime/composite_runtime.py`, add the import:

```python
from miniautogen.core.contracts.enums import RunStatus
```

Then replace:
- Line 80: `status="finished"` with `status=RunStatus.FINISHED`
- Line 116: `result.status == "failed"` with `result.status == RunStatus.FAILED`

**Step 3: Run tests for both runtimes**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/core/runtime/test_deliberation_runtime.py tests/core/runtime/test_composite_runtime.py -v`

**Expected output:** All tests pass.

**Step 4: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/core/runtime/deliberation_runtime.py miniautogen/core/runtime/composite_runtime.py
git commit -m "refactor: replace magic status strings with RunStatus enum in Deliberation and CompositeRuntime"
```

---

### Task 11: Run Code Review

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
- Format: `FIXME(nitpick): [Issue description] (reported by [reviewer] on [date], severity: Cosmetic)`

3. **Proceed only when:**
   - Zero Critical/High/Medium issues remain
   - All Low issues have TODO(review): comments added
   - All Cosmetic issues have FIXME(nitpick): comments added

---

## Intervention 3: Structured Time-Boxing Event Emission

### Task 12: Write failing test for RUN_TIMED_OUT event emission

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/tests/core/runtime/test_agentic_loop_runtime.py`

**Prerequisites:**
- Task 8 complete (enum replacements in AgenticLoopRuntime)

**Step 1: Write the failing test**

Add the following test at the end of `/Users/brunocapelao/Projects/miniAutoGen/tests/core/runtime/test_agentic_loop_runtime.py`:

```python
@pytest.mark.asyncio
async def test_timeout_emits_run_timed_out_event() -> None:
    """When the loop times out, a RUN_TIMED_OUT event must be emitted."""
    import asyncio

    class _SlowAgent:
        async def reply(self, last_message: str, context: dict[str, Any]) -> str:
            await asyncio.sleep(5.0)
            return "slow-reply"

    router = _FakeRouter([
        RouterDecision(
            current_state_summary="start",
            missing_information="need a",
            next_agent="slow_agent",
        )
        for _ in range(10)
    ])
    slow_agent = _SlowAgent()

    registry: dict[str, Any] = {"router": router, "slow_agent": slow_agent}
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)
    runtime = AgenticLoopRuntime(runner=runner, agent_registry=registry)

    plan = AgenticLoopPlan(
        router_agent="router",
        participants=["slow_agent"],
        policy=ConversationPolicy(max_turns=10, timeout_seconds=0.1),
    )
    result = await runtime.run(agents=[], context=_make_context(), plan=plan)

    assert result.status == "finished"
    assert result.metadata["stop_reason"] == "timeout"

    event_types = [e.type for e in event_sink.events]
    assert "run_timed_out" in event_types

    # Verify the RUN_TIMED_OUT event has correct payload
    timed_out_events = [e for e in event_sink.events if e.type == "run_timed_out"]
    assert len(timed_out_events) == 1
    assert timed_out_events[0].payload["timeout_seconds"] == 0.1
```

**Step 2: Run the test to verify it fails**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/core/runtime/test_agentic_loop_runtime.py::test_timeout_emits_run_timed_out_event -v`

**Expected output:**
```
FAILED - AssertionError: assert 'run_timed_out' in [...]
```

The test fails because the current timeout handler at line 197-199 only sets `stop_reason = "timeout"` but does not emit a `RUN_TIMED_OUT` event.

---

### Task 13: Emit RUN_TIMED_OUT event on timeout

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/runtime/agentic_loop_runtime.py`

**Prerequisites:**
- Task 12 test exists and fails
- Task 8 complete (enum imports already added)

**Step 1: Add event emission in the timeout handler**

In `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/runtime/agentic_loop_runtime.py`, find the `except TimeoutError:` block. It currently reads:

```python
        except TimeoutError:
            logger.warning("agentic_loop_timed_out", timeout=plan.policy.timeout_seconds)
            stop_reason = "timeout"
```

(After Task 8, `"timeout"` will be `LoopStopReason.TIMEOUT`.)

Replace with:

```python
        except TimeoutError:
            logger.warning("agentic_loop_timed_out", timeout=plan.policy.timeout_seconds)
            stop_reason = LoopStopReason.TIMEOUT
            await self._emit(
                event_type=EventType.RUN_TIMED_OUT.value,
                run_id=run_id,
                correlation_id=correlation_id,
                payload={"timeout_seconds": plan.policy.timeout_seconds},
            )
```

**Step 2: Run the timeout event test**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/core/runtime/test_agentic_loop_runtime.py::test_timeout_emits_run_timed_out_event -v`

**Expected output:**
```
PASSED tests/core/runtime/test_agentic_loop_runtime.py::test_timeout_emits_run_timed_out_event
```

**Step 3: Run all agentic loop tests to verify no regressions**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/core/runtime/test_agentic_loop_runtime.py -v`

**Expected output:** All tests pass, including the existing `test_timeout_enforcement`.

**Step 4: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/core/runtime/agentic_loop_runtime.py tests/core/runtime/test_agentic_loop_runtime.py
git commit -m "feat: emit RUN_TIMED_OUT event when agentic loop exceeds timeout

The timeout handler now emits an EventType.RUN_TIMED_OUT event with
the timeout_seconds in the payload, improving observability for
resource containment violations."
```

**If Task Fails:**

1. **Event emission raises inside except block:**
   - The `_emit` method is `async`, so it can be awaited inside the `except` block
   - Check: Ensure `await` is used before `self._emit`
   - Rollback: `git checkout -- miniautogen/core/runtime/agentic_loop_runtime.py`

2. **Tests fail with unexpected event count:**
   - Check: `print([e.type for e in event_sink.events])` to see what events were emitted
   - Ensure `RUN_TIMED_OUT` appears exactly once

3. **Can't recover:**
   - Rollback: `git checkout -- .`
   - Document what failed and return to human partner

---

## Final Verification

### Task 14: Run full test suite

**Files:** None (verification only)

**Prerequisites:**
- All previous tasks complete

**Step 1: Run the complete test suite**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest --tb=short -q`

**Expected output:** All tests pass, zero failures.

**Step 2: Run ruff linter**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && ruff check miniautogen/core/contracts/enums.py miniautogen/core/runtime/workflow_runtime.py miniautogen/core/runtime/agentic_loop_runtime.py miniautogen/core/runtime/agentic_loop.py miniautogen/core/runtime/deliberation_runtime.py miniautogen/core/runtime/composite_runtime.py miniautogen/core/contracts/__init__.py miniautogen/api.py`

**Expected output:** No linting errors (or only pre-existing ones).

**Step 3: Run mypy type check on changed files**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && mypy miniautogen/core/contracts/enums.py miniautogen/core/runtime/workflow_runtime.py miniautogen/core/runtime/agentic_loop_runtime.py miniautogen/core/runtime/agentic_loop.py`

**Expected output:** No errors (or only pre-existing ones).

---

### Task 15: Run Code Review (Final)

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
- Format: `FIXME(nitpick): [Issue description] (reported by [reviewer] on [date], severity: Cosmetic)`

3. **Proceed only when:**
   - Zero Critical/High/Medium issues remain
   - All Low issues have TODO(review): comments added
   - All Cosmetic issues have FIXME(nitpick): comments added

---

## Summary of All Files Changed

| File | Action | Intervention |
|------|--------|-------------|
| `miniautogen/core/contracts/enums.py` | Create | 2 |
| `miniautogen/core/contracts/__init__.py` | Modify | 2 |
| `miniautogen/api.py` | Modify | 2 |
| `miniautogen/core/runtime/workflow_runtime.py` | Modify | 1, 2 |
| `miniautogen/core/runtime/agentic_loop_runtime.py` | Modify | 2, 3 |
| `miniautogen/core/runtime/agentic_loop.py` | Modify | 2 |
| `miniautogen/core/runtime/deliberation_runtime.py` | Modify | 2 |
| `miniautogen/core/runtime/composite_runtime.py` | Modify | 2 |
| `tests/core/contracts/test_enums.py` | Create | 2 |
| `tests/core/runtime/test_workflow_runtime.py` | Modify | 1 |
| `tests/core/runtime/test_agentic_loop_runtime.py` | Modify | 3 |
