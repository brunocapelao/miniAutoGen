# Milestone 1 — Chunk 3: Resilience & Policies

> **For Agents:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Complete policy framework with ApprovalPolicy as crown jewel for future Terminal Harness

**Architecture:** Policies operate laterally — core emits events, policies observe and react. ApprovalGate is a Protocol (not ABC) so the Terminal Harness can provide its own implementation without inheriting from SDK classes. PolicyChain composes multiple policies into ordered evaluation. TimeoutScope provides structured nested cancel scopes via AnyIO.

**Tech Stack:** Python 3.10+, AnyIO 4+, Pydantic v2, tenacity, pytest-asyncio, ruff (line-length=100)

**Global Prerequisites:**
- Environment: macOS, Python 3.10+
- Tools: `python --version`, `poetry --version`, `ruff --version`
- State: Branch from `main`, clean working tree

**Verification before starting:**
```bash
cd /Users/brunocapelao/Projects/miniAutoGen
python --version        # Expected: Python 3.10.x or 3.11.x
poetry --version        # Expected: Poetry 1.x+
ruff --version          # Expected: ruff 0.15+
git status              # Expected: clean working tree on main (or feature branch)
poetry run pytest tests/policies/ -v  # Expected: all existing tests pass
```

---

## Task 1: Implement ApprovalPolicy Module

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/policies/approval.py`
- Test: `/Users/brunocapelao/Projects/miniAutoGen/tests/policies/test_approval.py`

**Prerequisites:**
- Existing file must exist: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/policies/__init__.py`

**Step 1: Write the failing test**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/policies/test_approval.py`:

```python
from __future__ import annotations

import pytest

from miniautogen.policies.approval import (
    ApprovalGate,
    ApprovalPolicy,
    ApprovalRequest,
    ApprovalResponse,
    AutoApproveGate,
)


class TestApprovalRequestCreation:
    def test_creates_with_required_fields(self):
        req = ApprovalRequest(
            request_id="req-1",
            action="execute_pipeline",
            description="Run data pipeline",
            context={"pipeline": "etl"},
        )
        assert req.request_id == "req-1"
        assert req.action == "execute_pipeline"
        assert req.description == "Run data pipeline"
        assert req.context == {"pipeline": "etl"}
        assert req.timeout_seconds is None

    def test_creates_with_timeout(self):
        req = ApprovalRequest(
            request_id="req-2",
            action="deploy",
            description="Deploy to prod",
            context={},
            timeout_seconds=30.0,
        )
        assert req.timeout_seconds == 30.0

    def test_is_frozen(self):
        req = ApprovalRequest(
            request_id="req-1",
            action="run",
            description="test",
            context={},
        )
        with pytest.raises(AttributeError):
            req.action = "changed"


class TestApprovalResponseCreation:
    def test_approved_response(self):
        resp = ApprovalResponse(
            request_id="req-1",
            decision="approved",
        )
        assert resp.request_id == "req-1"
        assert resp.decision == "approved"
        assert resp.reason is None
        assert resp.modifications is None

    def test_denied_response_with_reason(self):
        resp = ApprovalResponse(
            request_id="req-1",
            decision="denied",
            reason="Not authorized",
        )
        assert resp.decision == "denied"
        assert resp.reason == "Not authorized"

    def test_modified_response_with_modifications(self):
        resp = ApprovalResponse(
            request_id="req-1",
            decision="modified",
            modifications={"timeout": 60},
        )
        assert resp.decision == "modified"
        assert resp.modifications == {"timeout": 60}

    def test_is_frozen(self):
        resp = ApprovalResponse(
            request_id="req-1",
            decision="approved",
        )
        with pytest.raises(AttributeError):
            resp.decision = "denied"


class TestApprovalPolicy:
    def test_default_is_empty_set(self):
        policy = ApprovalPolicy()
        assert policy.require_approval_for == frozenset()

    def test_configured_with_actions(self):
        policy = ApprovalPolicy(
            require_approval_for=frozenset({"execute_pipeline", "deploy"}),
        )
        assert "execute_pipeline" in policy.require_approval_for
        assert "deploy" in policy.require_approval_for

    def test_is_frozen(self):
        policy = ApprovalPolicy()
        with pytest.raises(AttributeError):
            policy.require_approval_for = frozenset({"x"})


class TestAutoApproveGate:
    @pytest.mark.asyncio
    async def test_approves_any_request(self):
        gate = AutoApproveGate()
        req = ApprovalRequest(
            request_id="req-1",
            action="anything",
            description="test",
            context={},
        )
        resp = await gate.request_approval(req)
        assert resp.request_id == "req-1"
        assert resp.decision == "approved"
        assert resp.reason == "auto-approved"

    @pytest.mark.asyncio
    async def test_satisfies_approval_gate_protocol(self):
        gate = AutoApproveGate()
        assert isinstance(gate, ApprovalGate)
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen && poetry run pytest tests/policies/test_approval.py -v
```

**Expected output:**
```
ModuleNotFoundError: No module named 'miniautogen.policies.approval'
```

**Step 3: Write the implementation**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/policies/approval.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol, runtime_checkable


@dataclass(frozen=True)
class ApprovalRequest:
    """Describes an action awaiting external approval."""

    request_id: str
    action: str
    description: str
    context: dict[str, Any]
    timeout_seconds: float | None = None


@dataclass(frozen=True)
class ApprovalResponse:
    """Result of an approval decision."""

    request_id: str
    decision: Literal["approved", "denied", "modified"]
    reason: str | None = None
    modifications: dict[str, Any] | None = None


@dataclass(frozen=True)
class ApprovalPolicy:
    """Policy declaring which actions require external approval."""

    require_approval_for: frozenset[str] = frozenset()


@runtime_checkable
class ApprovalGate(Protocol):
    """Protocol for external approval providers.

    Implementations pause execution and await an external decision.
    The Terminal Harness (Milestone 3) will implement this to prompt
    the human operator.
    """

    async def request_approval(self, request: ApprovalRequest) -> ApprovalResponse: ...


class AutoApproveGate:
    """Default gate that approves everything (headless mode)."""

    async def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:
        return ApprovalResponse(
            request_id=request.request_id,
            decision="approved",
            reason="auto-approved",
        )
```

**Step 4: Run test to verify it passes**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen && poetry run pytest tests/policies/test_approval.py -v
```

**Expected output:**
```
tests/policies/test_approval.py::TestApprovalRequestCreation::test_creates_with_required_fields PASSED
tests/policies/test_approval.py::TestApprovalRequestCreation::test_creates_with_timeout PASSED
tests/policies/test_approval.py::TestApprovalRequestCreation::test_is_frozen PASSED
tests/policies/test_approval.py::TestApprovalResponseCreation::test_approved_response PASSED
tests/policies/test_approval.py::TestApprovalResponseCreation::test_denied_response_with_reason PASSED
tests/policies/test_approval.py::TestApprovalResponseCreation::test_modified_response_with_modifications PASSED
tests/policies/test_approval.py::TestApprovalResponseCreation::test_is_frozen PASSED
tests/policies/test_approval.py::TestApprovalPolicy::test_default_is_empty_set PASSED
tests/policies/test_approval.py::TestApprovalPolicy::test_configured_with_actions PASSED
tests/policies/test_approval.py::TestApprovalPolicy::test_is_frozen PASSED
tests/policies/test_approval.py::TestAutoApproveGate::test_approves_any_request PASSED
tests/policies/test_approval.py::TestAutoApproveGate::test_satisfies_approval_gate_protocol PASSED
```

**Step 5: Lint**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen && poetry run ruff check miniautogen/policies/approval.py tests/policies/test_approval.py
```

**Expected output:** No errors (exit code 0).

**Step 6: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/policies/approval.py tests/policies/test_approval.py
git commit -m "feat: add ApprovalPolicy, ApprovalGate protocol, and AutoApproveGate"
```

**If Task Fails:**

1. **Test won't run:** Check `ls tests/policies/` — ensure `__init__.py` is not required (pytest discovers without it in this project).
2. **Frozen dataclass error:** Verify `@dataclass(frozen=True)` is on all three dataclasses. Frozen dataclasses raise `FrozenInstanceError` (subclass of `AttributeError`).
3. **Protocol isinstance check fails:** Ensure `@runtime_checkable` decorator is on `ApprovalGate`.
4. **Rollback:** `git checkout -- miniautogen/policies/approval.py tests/policies/test_approval.py`

---

## Task 2: Add Approval Event Types

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/events/types.py` (lines 22-23, after `BUDGET_EXCEEDED`)
- Test: `/Users/brunocapelao/Projects/miniAutoGen/tests/policies/test_approval_events.py`

**Prerequisites:**
- Task 1 completed
- Existing file: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/events/types.py`

**Step 1: Write the failing test**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/policies/test_approval_events.py`:

```python
from miniautogen.core.events.types import (
    APPROVAL_EVENT_TYPES,
    EventType,
)


class TestApprovalEventTypes:
    def test_approval_requested_exists(self):
        assert EventType.APPROVAL_REQUESTED.value == "approval_requested"

    def test_approval_granted_exists(self):
        assert EventType.APPROVAL_GRANTED.value == "approval_granted"

    def test_approval_denied_exists(self):
        assert EventType.APPROVAL_DENIED.value == "approval_denied"

    def test_approval_timeout_exists(self):
        assert EventType.APPROVAL_TIMEOUT.value == "approval_timeout"

    def test_approval_event_types_set_contains_all(self):
        expected = {
            "approval_requested",
            "approval_granted",
            "approval_denied",
            "approval_timeout",
        }
        assert APPROVAL_EVENT_TYPES == expected

    def test_approval_event_types_set_has_four_members(self):
        assert len(APPROVAL_EVENT_TYPES) == 4
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen && poetry run pytest tests/policies/test_approval_events.py -v
```

**Expected output:**
```
ImportError: cannot import name 'APPROVAL_EVENT_TYPES' from 'miniautogen.core.events.types'
```

**Step 3: Modify the EventType enum and add the set**

In `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/events/types.py`, add four new members after `BUDGET_EXCEEDED` (line 22) and add the `APPROVAL_EVENT_TYPES` set at the end of the file.

Add these enum members after `BUDGET_EXCEEDED = "budget_exceeded"` (line 22):

```python
    # Approval events
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    APPROVAL_TIMEOUT = "approval_timeout"
```

Add this set at the bottom of the file (after `BACKEND_EVENT_TYPES`):

```python
APPROVAL_EVENT_TYPES = {
    EventType.APPROVAL_REQUESTED.value,
    EventType.APPROVAL_GRANTED.value,
    EventType.APPROVAL_DENIED.value,
    EventType.APPROVAL_TIMEOUT.value,
}
```

The complete file after editing should have:
- Lines 22: `BUDGET_EXCEEDED = "budget_exceeded"`
- Lines 23-27: The four new approval enum members
- Lines at end: The `APPROVAL_EVENT_TYPES` set

**Step 4: Run test to verify it passes**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen && poetry run pytest tests/policies/test_approval_events.py -v
```

**Expected output:**
```
tests/policies/test_approval_events.py::TestApprovalEventTypes::test_approval_requested_exists PASSED
tests/policies/test_approval_events.py::TestApprovalEventTypes::test_approval_granted_exists PASSED
tests/policies/test_approval_events.py::TestApprovalEventTypes::test_approval_denied_exists PASSED
tests/policies/test_approval_events.py::TestApprovalEventTypes::test_approval_timeout_exists PASSED
tests/policies/test_approval_events.py::TestApprovalEventTypes::test_approval_event_types_set_contains_all PASSED
tests/policies/test_approval_events.py::TestApprovalEventTypes::test_approval_event_types_set_has_four_members PASSED
```

**Step 5: Verify no regressions**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen && poetry run pytest tests/ -v --timeout=30
```

**Expected output:** All tests pass (existing + new).

**Step 6: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/core/events/types.py tests/policies/test_approval_events.py
git commit -m "feat: add APPROVAL_REQUESTED/GRANTED/DENIED/TIMEOUT event types"
```

**If Task Fails:**

1. **Import error persists after edit:** Verify the enum members are indented correctly (4 spaces) inside the `EventType` class body.
2. **Existing tests break:** The enum is append-only; adding members should not break existing tests. If `test_policy_categories.py` fails, check if it asserts an exact enum count.
3. **Rollback:** `git checkout -- miniautogen/core/events/types.py`

---

## Task 3: Integrate ApprovalGate with PipelineRunner

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/runtime/pipeline_runner.py` (lines 20-31, 60-98)
- Test: `/Users/brunocapelao/Projects/miniAutoGen/tests/core/runtime/test_pipeline_runner_approval.py`

**Prerequisites:**
- Task 1 completed (ApprovalGate, ApprovalRequest, ApprovalResponse exist)
- Task 2 completed (APPROVAL_REQUESTED, APPROVAL_GRANTED, APPROVAL_DENIED event types exist)
- Existing files:
  - `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/runtime/pipeline_runner.py`
  - `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/pipeline/pipeline.py`
  - `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/pipeline/components/pipelinecomponent.py`

**Step 1: Write the failing test**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/core/runtime/test_pipeline_runner_approval.py`:

```python
from __future__ import annotations

import pytest

from miniautogen.core.events import InMemoryEventSink
from miniautogen.core.events.types import EventType
from miniautogen.core.runtime.pipeline_runner import PipelineRunner
from miniautogen.pipeline.components.pipelinecomponent import PipelineComponent
from miniautogen.pipeline.pipeline import Pipeline
from miniautogen.policies.approval import (
    ApprovalGate,
    ApprovalPolicy,
    ApprovalRequest,
    ApprovalResponse,
    AutoApproveGate,
)


class PassthroughComponent(PipelineComponent):
    async def process(self, state):
        state["executed"] = True
        return state


class DenyGate:
    """Gate that always denies."""

    async def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:
        return ApprovalResponse(
            request_id=request.request_id,
            decision="denied",
            reason="test denial",
        )


class TestPipelineRunnerApprovalGateApproved:
    @pytest.mark.asyncio
    async def test_approved_gate_allows_pipeline_execution(self):
        sink = InMemoryEventSink()
        runner = PipelineRunner(
            event_sink=sink,
            approval_gate=AutoApproveGate(),
            approval_policy=ApprovalPolicy(
                require_approval_for=frozenset({"run_pipeline"}),
            ),
        )
        pipeline = Pipeline([PassthroughComponent()])

        result = await runner.run_pipeline(pipeline, {"executed": False})

        assert result["executed"] is True

    @pytest.mark.asyncio
    async def test_approved_gate_emits_requested_then_granted_events(self):
        sink = InMemoryEventSink()
        runner = PipelineRunner(
            event_sink=sink,
            approval_gate=AutoApproveGate(),
            approval_policy=ApprovalPolicy(
                require_approval_for=frozenset({"run_pipeline"}),
            ),
        )
        pipeline = Pipeline([PassthroughComponent()])

        await runner.run_pipeline(pipeline, {"executed": False})

        event_types = [e.type for e in sink.events]
        assert EventType.APPROVAL_REQUESTED.value in event_types
        assert EventType.APPROVAL_GRANTED.value in event_types
        # APPROVAL_REQUESTED must come before APPROVAL_GRANTED
        req_idx = event_types.index(EventType.APPROVAL_REQUESTED.value)
        grant_idx = event_types.index(EventType.APPROVAL_GRANTED.value)
        assert req_idx < grant_idx


class TestPipelineRunnerApprovalGateDenied:
    @pytest.mark.asyncio
    async def test_denied_gate_prevents_pipeline_execution(self):
        sink = InMemoryEventSink()
        runner = PipelineRunner(
            event_sink=sink,
            approval_gate=DenyGate(),
            approval_policy=ApprovalPolicy(
                require_approval_for=frozenset({"run_pipeline"}),
            ),
        )
        pipeline = Pipeline([PassthroughComponent()])

        result = await runner.run_pipeline(pipeline, {"executed": False})

        # Pipeline did NOT run — result is None when denied
        assert result is None

    @pytest.mark.asyncio
    async def test_denied_gate_emits_denied_and_cancelled_events(self):
        sink = InMemoryEventSink()
        runner = PipelineRunner(
            event_sink=sink,
            approval_gate=DenyGate(),
            approval_policy=ApprovalPolicy(
                require_approval_for=frozenset({"run_pipeline"}),
            ),
        )
        pipeline = Pipeline([PassthroughComponent()])

        await runner.run_pipeline(pipeline, {"executed": False})

        event_types = [e.type for e in sink.events]
        assert EventType.APPROVAL_DENIED.value in event_types
        assert EventType.RUN_CANCELLED.value in event_types


class TestPipelineRunnerNoApprovalGate:
    @pytest.mark.asyncio
    async def test_no_gate_runs_pipeline_normally(self):
        """When no approval_gate is set, pipeline runs without approval."""
        sink = InMemoryEventSink()
        runner = PipelineRunner(event_sink=sink)
        pipeline = Pipeline([PassthroughComponent()])

        result = await runner.run_pipeline(pipeline, {"executed": False})

        assert result["executed"] is True
        event_types = [e.type for e in sink.events]
        assert EventType.APPROVAL_REQUESTED.value not in event_types

    @pytest.mark.asyncio
    async def test_gate_without_policy_skips_approval(self):
        """If gate is set but no policy, skip approval (nothing requires it)."""
        sink = InMemoryEventSink()
        runner = PipelineRunner(
            event_sink=sink,
            approval_gate=AutoApproveGate(),
        )
        pipeline = Pipeline([PassthroughComponent()])

        result = await runner.run_pipeline(pipeline, {"executed": False})

        assert result["executed"] is True
        event_types = [e.type for e in sink.events]
        assert EventType.APPROVAL_REQUESTED.value not in event_types

    @pytest.mark.asyncio
    async def test_action_not_in_policy_skips_approval(self):
        """If run_pipeline is not in require_approval_for, skip approval."""
        sink = InMemoryEventSink()
        runner = PipelineRunner(
            event_sink=sink,
            approval_gate=AutoApproveGate(),
            approval_policy=ApprovalPolicy(
                require_approval_for=frozenset({"deploy"}),
            ),
        )
        pipeline = Pipeline([PassthroughComponent()])

        result = await runner.run_pipeline(pipeline, {"executed": False})

        assert result["executed"] is True
        event_types = [e.type for e in sink.events]
        assert EventType.APPROVAL_REQUESTED.value not in event_types
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen && poetry run pytest tests/core/runtime/test_pipeline_runner_approval.py -v
```

**Expected output:**
```
TypeError: PipelineRunner.__init__() got an unexpected keyword argument 'approval_gate'
```

**Step 3: Modify PipelineRunner to support approval gate**

In `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/runtime/pipeline_runner.py`:

1. Add imports at the top (after existing imports, around line 13):

```python
from miniautogen.policies.approval import (
    ApprovalGate,
    ApprovalPolicy,
    ApprovalRequest,
    ApprovalResponse,
)
```

2. Modify `__init__` to accept `approval_gate` and `approval_policy` parameters. Replace the existing `__init__` (lines 20-32) with:

```python
    def __init__(
        self,
        event_sink: EventSink | None = None,
        run_store: RunStore | None = None,
        checkpoint_store: CheckpointStore | None = None,
        execution_policy: ExecutionPolicy | None = None,
        approval_gate: ApprovalGate | None = None,
        approval_policy: ApprovalPolicy | None = None,
    ):
        self.event_sink = event_sink or NullEventSink()
        self.run_store = run_store
        self.checkpoint_store = checkpoint_store
        self.execution_policy = execution_policy
        self.approval_gate = approval_gate
        self.approval_policy = approval_policy
        self.last_run_id: str | None = None
        self.logger = get_logger(__name__)
```

3. Add a private method `_request_approval` after `_persist_failed_run` (around line 58):

```python
    async def _request_approval(
        self,
        run_id: str,
        correlation_id: str,
        action: str,
    ) -> ApprovalResponse | None:
        """Request approval if gate and policy are configured.

        Returns None if approval is not required (no gate, no policy,
        or action not in require_approval_for). Returns the
        ApprovalResponse otherwise.
        """
        if self.approval_gate is None or self.approval_policy is None:
            return None
        if action not in self.approval_policy.require_approval_for:
            return None

        request = ApprovalRequest(
            request_id=f"{run_id}:{action}",
            action=action,
            description=f"Approval required for '{action}'",
            context={"run_id": run_id, "correlation_id": correlation_id},
        )
        await self.event_sink.publish(
            ExecutionEvent(
                type=EventType.APPROVAL_REQUESTED.value,
                timestamp=datetime.now(timezone.utc),
                run_id=run_id,
                correlation_id=correlation_id,
                scope="pipeline_runner",
                payload={"request_id": request.request_id, "action": action},
            )
        )
        response = await self.approval_gate.request_approval(request)
        if response.decision == "approved":
            await self.event_sink.publish(
                ExecutionEvent(
                    type=EventType.APPROVAL_GRANTED.value,
                    timestamp=datetime.now(timezone.utc),
                    run_id=run_id,
                    correlation_id=correlation_id,
                    scope="pipeline_runner",
                    payload={
                        "request_id": request.request_id,
                        "reason": response.reason,
                    },
                )
            )
        else:
            await self.event_sink.publish(
                ExecutionEvent(
                    type=EventType.APPROVAL_DENIED.value,
                    timestamp=datetime.now(timezone.utc),
                    run_id=run_id,
                    correlation_id=correlation_id,
                    scope="pipeline_runner",
                    payload={
                        "request_id": request.request_id,
                        "decision": response.decision,
                        "reason": response.reason,
                    },
                )
            )
        return response
```

4. In `run_pipeline`, add the approval check after the `RUN_STARTED` event emission (after line 98 `logger.info("run_started")`). Insert before the `try:` block at line 100:

```python
        # --- Approval gate ---
        approval_response = await self._request_approval(
            current_run_id, correlation_id, "run_pipeline"
        )
        if approval_response is not None and approval_response.decision != "approved":
            await self.event_sink.publish(
                ExecutionEvent(
                    type=EventType.RUN_CANCELLED.value,
                    timestamp=datetime.now(timezone.utc),
                    run_id=current_run_id,
                    correlation_id=correlation_id,
                    scope="pipeline_runner",
                    payload={"reason": approval_response.reason},
                )
            )
            logger.info("run_cancelled", reason=approval_response.reason)
            return None
```

**Step 4: Run test to verify it passes**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen && poetry run pytest tests/core/runtime/test_pipeline_runner_approval.py -v
```

**Expected output:**
```
tests/core/runtime/test_pipeline_runner_approval.py::TestPipelineRunnerApprovalGateApproved::test_approved_gate_allows_pipeline_execution PASSED
tests/core/runtime/test_pipeline_runner_approval.py::TestPipelineRunnerApprovalGateApproved::test_approved_gate_emits_requested_then_granted_events PASSED
tests/core/runtime/test_pipeline_runner_approval.py::TestPipelineRunnerApprovalGateDenied::test_denied_gate_prevents_pipeline_execution PASSED
tests/core/runtime/test_pipeline_runner_approval.py::TestPipelineRunnerApprovalGateDenied::test_denied_gate_emits_denied_and_cancelled_events PASSED
tests/core/runtime/test_pipeline_runner_approval.py::TestPipelineRunnerNoApprovalGate::test_no_gate_runs_pipeline_normally PASSED
tests/core/runtime/test_pipeline_runner_approval.py::TestPipelineRunnerNoApprovalGate::test_gate_without_policy_skips_approval PASSED
tests/core/runtime/test_pipeline_runner_approval.py::TestPipelineRunnerNoApprovalGate::test_action_not_in_policy_skips_approval PASSED
```

**Step 5: Verify no regressions**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen && poetry run pytest tests/core/runtime/ -v
```

**Expected output:** All pipeline runner tests pass (existing + new).

**Step 6: Lint**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen && poetry run ruff check miniautogen/core/runtime/pipeline_runner.py tests/core/runtime/test_pipeline_runner_approval.py
```

**Step 7: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/core/runtime/pipeline_runner.py tests/core/runtime/test_pipeline_runner_approval.py
git commit -m "feat: integrate ApprovalGate with PipelineRunner"
```

**If Task Fails:**

1. **Import cycle:** If importing from `miniautogen.policies.approval` in `pipeline_runner.py` causes a circular import, use a `TYPE_CHECKING` guard:
   ```python
   from __future__ import annotations
   from typing import TYPE_CHECKING
   if TYPE_CHECKING:
       from miniautogen.policies.approval import ApprovalGate, ApprovalPolicy
   ```
   And move the runtime imports into `_request_approval`.
2. **Existing tests break on new __init__ params:** All new params default to `None`, so existing callers are unaffected. If any test uses positional args, check the call site.
3. **Rollback:** `git checkout -- miniautogen/core/runtime/pipeline_runner.py`

---

## Task 4: Integrate RetryPolicy with PipelineRunner

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/runtime/pipeline_runner.py`
- Test: `/Users/brunocapelao/Projects/miniAutoGen/tests/core/runtime/test_pipeline_runner_retry.py`

**Prerequisites:**
- Task 3 completed
- Existing files:
  - `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/policies/retry.py`

**Step 1: Write the failing test**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/core/runtime/test_pipeline_runner_retry.py`:

```python
from __future__ import annotations

import pytest

from miniautogen.core.events import InMemoryEventSink
from miniautogen.core.events.types import EventType
from miniautogen.core.runtime.pipeline_runner import PipelineRunner
from miniautogen.pipeline.components.pipelinecomponent import PipelineComponent
from miniautogen.pipeline.pipeline import Pipeline
from miniautogen.policies.retry import RetryPolicy


class TransientFailComponent(PipelineComponent):
    """Fails with RuntimeError the first N times, then succeeds."""

    def __init__(self, fail_count: int = 1):
        self._fail_count = fail_count
        self._calls = 0

    async def process(self, state):
        self._calls += 1
        if self._calls <= self._fail_count:
            raise RuntimeError(f"Transient failure #{self._calls}")
        state["attempts"] = self._calls
        return state

    @property
    def calls(self) -> int:
        return self._calls


class PermanentFailComponent(PipelineComponent):
    """Always raises ValueError (non-retryable by default)."""

    async def process(self, state):
        raise ValueError("Permanent failure")


class TestPipelineRunnerRetryOnTransientError:
    @pytest.mark.asyncio
    async def test_retries_and_succeeds(self):
        component = TransientFailComponent(fail_count=2)
        pipeline = Pipeline([component])
        sink = InMemoryEventSink()
        runner = PipelineRunner(
            event_sink=sink,
            retry_policy=RetryPolicy(
                max_attempts=3,
                retry_exceptions=(RuntimeError,),
            ),
        )

        result = await runner.run_pipeline(pipeline, {"attempts": 0})

        assert result["attempts"] == 3
        assert component.calls == 3

    @pytest.mark.asyncio
    async def test_emits_component_retried_event(self):
        component = TransientFailComponent(fail_count=1)
        pipeline = Pipeline([component])
        sink = InMemoryEventSink()
        runner = PipelineRunner(
            event_sink=sink,
            retry_policy=RetryPolicy(
                max_attempts=2,
                retry_exceptions=(RuntimeError,),
            ),
        )

        await runner.run_pipeline(pipeline, {"attempts": 0})

        event_types = [e.type for e in sink.events]
        assert EventType.COMPONENT_RETRIED.value in event_types


class TestPipelineRunnerNoRetryOnPermanentError:
    @pytest.mark.asyncio
    async def test_permanent_error_not_retried(self):
        pipeline = Pipeline([PermanentFailComponent()])
        sink = InMemoryEventSink()
        runner = PipelineRunner(
            event_sink=sink,
            retry_policy=RetryPolicy(
                max_attempts=3,
                retry_exceptions=(RuntimeError,),
            ),
        )

        with pytest.raises(ValueError, match="Permanent failure"):
            await runner.run_pipeline(pipeline, {})


class TestPipelineRunnerRetryExhausted:
    @pytest.mark.asyncio
    async def test_raises_after_exhausting_retries(self):
        component = TransientFailComponent(fail_count=5)
        pipeline = Pipeline([component])
        sink = InMemoryEventSink()
        runner = PipelineRunner(
            event_sink=sink,
            retry_policy=RetryPolicy(
                max_attempts=3,
                retry_exceptions=(RuntimeError,),
            ),
        )

        with pytest.raises(RuntimeError, match="Transient failure"):
            await runner.run_pipeline(pipeline, {"attempts": 0})

        assert component.calls == 3


class TestPipelineRunnerNoRetryPolicy:
    @pytest.mark.asyncio
    async def test_no_retry_policy_runs_once(self):
        component = TransientFailComponent(fail_count=1)
        pipeline = Pipeline([component])
        runner = PipelineRunner()

        with pytest.raises(RuntimeError, match="Transient failure"):
            await runner.run_pipeline(pipeline, {"attempts": 0})

        assert component.calls == 1
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen && poetry run pytest tests/core/runtime/test_pipeline_runner_retry.py -v
```

**Expected output:**
```
TypeError: PipelineRunner.__init__() got an unexpected keyword argument 'retry_policy'
```

**Step 3: Modify PipelineRunner to support retry policy**

In `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/runtime/pipeline_runner.py`:

1. Add import at the top (after existing imports):

```python
from miniautogen.policies.retry import RetryPolicy, build_retrying_call
```

2. Add `retry_policy` parameter to `__init__`. In the `__init__` signature, add after `approval_policy`:

```python
        retry_policy: RetryPolicy | None = None,
```

And in the body add:

```python
        self.retry_policy = retry_policy
```

3. Modify the `run_pipeline` method. Replace the `try` block that runs the pipeline (the block starting with `try:` that contains `pipeline.run(state)`) with a version that wraps with retry. Replace the block from `try:` through `raise` (after `logger.error`) with:

```python
        try:
            if self.retry_policy is not None:
                retry_runner = build_retrying_call(self.retry_policy)
                attempt_count = 0

                async def _run_with_retry_tracking() -> Any:
                    nonlocal attempt_count
                    attempt_count += 1
                    if attempt_count > 1:
                        await self.event_sink.publish(
                            ExecutionEvent(
                                type=EventType.COMPONENT_RETRIED.value,
                                timestamp=datetime.now(timezone.utc),
                                run_id=current_run_id,
                                correlation_id=correlation_id,
                                scope="pipeline_runner",
                                payload={"attempt": attempt_count},
                            )
                        )
                        logger.info(
                            "component_retried", attempt=attempt_count
                        )
                    if effective_timeout is None:
                        return await pipeline.run(state)
                    else:
                        with anyio.fail_after(effective_timeout):
                            return await pipeline.run(state)

                result = await retry_runner(_run_with_retry_tracking)
            else:
                if effective_timeout is None:
                    result = await pipeline.run(state)
                else:
                    with anyio.fail_after(effective_timeout):
                        result = await pipeline.run(state)
        except TimeoutError:
            if self.run_store is not None:
                await self.run_store.save_run(
                    current_run_id,
                    {
                        "status": "timed_out",
                        "correlation_id": correlation_id,
                    },
                )
            await self.event_sink.publish(
                ExecutionEvent(
                    type=EventType.RUN_TIMED_OUT.value,
                    timestamp=datetime.now(timezone.utc),
                    run_id=current_run_id,
                    correlation_id=correlation_id,
                    scope="pipeline_runner",
                )
            )
            logger.warning("run_timed_out")
            raise
        except Exception as exc:
            await self._persist_failed_run(
                current_run_id, correlation_id, type(exc).__name__
            )
            logger.error("run_failed", error_type=type(exc).__name__)
            raise
```

**Step 4: Run test to verify it passes**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen && poetry run pytest tests/core/runtime/test_pipeline_runner_retry.py -v
```

**Expected output:**
```
tests/core/runtime/test_pipeline_runner_retry.py::TestPipelineRunnerRetryOnTransientError::test_retries_and_succeeds PASSED
tests/core/runtime/test_pipeline_runner_retry.py::TestPipelineRunnerRetryOnTransientError::test_emits_component_retried_event PASSED
tests/core/runtime/test_pipeline_runner_retry.py::TestPipelineRunnerNoRetryOnPermanentError::test_permanent_error_not_retried PASSED
tests/core/runtime/test_pipeline_runner_retry.py::TestPipelineRunnerRetryExhausted::test_raises_after_exhausting_retries PASSED
tests/core/runtime/test_pipeline_runner_retry.py::TestPipelineRunnerNoRetryPolicy::test_no_retry_policy_runs_once PASSED
```

**Step 5: Verify no regressions**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen && poetry run pytest tests/core/runtime/ -v
```

**Step 6: Lint**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen && poetry run ruff check miniautogen/core/runtime/pipeline_runner.py tests/core/runtime/test_pipeline_runner_retry.py
```

**Step 7: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/core/runtime/pipeline_runner.py tests/core/runtime/test_pipeline_runner_retry.py
git commit -m "feat: integrate RetryPolicy with PipelineRunner"
```

**If Task Fails:**

1. **Tenacity raises `RetryError` instead of the original exception:** The `RetryPolicy` uses `reraise=True`, so the original exception should propagate. If not, check that `build_retrying_call` has `reraise=True`.
2. **Event emission inside retry closure causes issues:** The `event_sink.publish` is `async` and safe to call from within the retry loop because tenacity's `AsyncRetrying` properly awaits.
3. **Rollback:** `git checkout -- miniautogen/core/runtime/pipeline_runner.py`

---

## Task 5: Implement PolicyChain

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/policies/chain.py`
- Test: `/Users/brunocapelao/Projects/miniAutoGen/tests/policies/test_chain.py`

**Prerequisites:**
- Task 1 completed (ApprovalPolicy exists for use as example)
- Existing file: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/contracts/run_context.py`

**Step 1: Write the failing test**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/policies/test_chain.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

import pytest

from miniautogen.core.contracts.run_context import RunContext
from miniautogen.policies.chain import Policy, PolicyChain, PolicyDecision


class AlwaysProceedPolicy:
    async def apply(self, context: RunContext) -> PolicyDecision:
        return "proceed"


class AlwaysDenyPolicy:
    async def apply(self, context: RunContext) -> PolicyDecision:
        return "deny"


class AlwaysRetryPolicy:
    async def apply(self, context: RunContext) -> PolicyDecision:
        return "retry"


class TrackingPolicy:
    """Records the order it was called."""

    def __init__(self, name: str, decision: PolicyDecision = "proceed"):
        self.name = name
        self.decision = decision
        self.called = False
        self.call_order: int | None = None

    async def apply(self, context: RunContext) -> PolicyDecision:
        self.called = True
        return self.decision


def _make_context() -> RunContext:
    return RunContext(
        run_id="test-run",
        started_at=datetime.now(timezone.utc),
        correlation_id="test-corr",
    )


class TestPolicyProtocol:
    def test_always_proceed_satisfies_protocol(self):
        assert isinstance(AlwaysProceedPolicy(), Policy)

    def test_always_deny_satisfies_protocol(self):
        assert isinstance(AlwaysDenyPolicy(), Policy)


class TestPolicyChainAllProceed:
    @pytest.mark.asyncio
    async def test_returns_proceed_when_all_proceed(self):
        chain = PolicyChain(policies=[AlwaysProceedPolicy(), AlwaysProceedPolicy()])
        result = await chain.evaluate(_make_context())
        assert result == "proceed"

    @pytest.mark.asyncio
    async def test_empty_chain_returns_proceed(self):
        chain = PolicyChain(policies=[])
        result = await chain.evaluate(_make_context())
        assert result == "proceed"


class TestPolicyChainDenyShortCircuits:
    @pytest.mark.asyncio
    async def test_deny_stops_evaluation(self):
        p1 = TrackingPolicy("first", decision="proceed")
        p2 = AlwaysDenyPolicy()
        p3 = TrackingPolicy("third", decision="proceed")
        chain = PolicyChain(policies=[p1, p2, p3])

        result = await chain.evaluate(_make_context())

        assert result == "deny"
        assert p1.called is True
        assert p3.called is False  # Short-circuited

    @pytest.mark.asyncio
    async def test_first_deny_wins(self):
        chain = PolicyChain(
            policies=[AlwaysDenyPolicy(), AlwaysRetryPolicy()]
        )
        result = await chain.evaluate(_make_context())
        assert result == "deny"


class TestPolicyChainRetryShortCircuits:
    @pytest.mark.asyncio
    async def test_retry_stops_evaluation(self):
        p1 = TrackingPolicy("first", decision="proceed")
        p2 = AlwaysRetryPolicy()
        p3 = TrackingPolicy("third", decision="proceed")
        chain = PolicyChain(policies=[p1, p2, p3])

        result = await chain.evaluate(_make_context())

        assert result == "retry"
        assert p1.called is True
        assert p3.called is False

    @pytest.mark.asyncio
    async def test_deny_takes_precedence_over_retry_in_order(self):
        chain = PolicyChain(
            policies=[AlwaysRetryPolicy(), AlwaysDenyPolicy()]
        )
        result = await chain.evaluate(_make_context())
        # First non-proceed wins — retry comes first
        assert result == "retry"


class TestPolicyChainOrdering:
    @pytest.mark.asyncio
    async def test_evaluates_in_order(self):
        p1 = TrackingPolicy("first")
        p2 = TrackingPolicy("second")
        p3 = TrackingPolicy("third")
        chain = PolicyChain(policies=[p1, p2, p3])

        await chain.evaluate(_make_context())

        assert p1.called is True
        assert p2.called is True
        assert p3.called is True
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen && poetry run pytest tests/policies/test_chain.py -v
```

**Expected output:**
```
ModuleNotFoundError: No module named 'miniautogen.policies.chain'
```

**Step 3: Write the implementation**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/policies/chain.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from miniautogen.core.contracts.run_context import RunContext

PolicyDecision = Literal["proceed", "deny", "retry"]


@runtime_checkable
class Policy(Protocol):
    """Protocol for composable policies.

    Each policy evaluates a RunContext and returns a decision.
    """

    async def apply(self, context: RunContext) -> PolicyDecision: ...


@dataclass(frozen=True)
class PolicyChain:
    """Ordered chain of policies evaluated sequentially.

    Evaluation short-circuits on the first non-"proceed" decision.
    An empty chain returns "proceed".
    """

    policies: tuple[Policy, ...] = ()

    def __init__(self, policies: list[Policy] | tuple[Policy, ...] = ()) -> None:
        object.__setattr__(self, "policies", tuple(policies))

    async def evaluate(self, context: RunContext) -> PolicyDecision:
        """Evaluate all policies in order. Short-circuit on deny/retry."""
        for policy in self.policies:
            decision = await policy.apply(context)
            if decision != "proceed":
                return decision
        return "proceed"
```

**Step 4: Run test to verify it passes**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen && poetry run pytest tests/policies/test_chain.py -v
```

**Expected output:**
```
tests/policies/test_chain.py::TestPolicyProtocol::test_always_proceed_satisfies_protocol PASSED
tests/policies/test_chain.py::TestPolicyProtocol::test_always_deny_satisfies_protocol PASSED
tests/policies/test_chain.py::TestPolicyChainAllProceed::test_returns_proceed_when_all_proceed PASSED
tests/policies/test_chain.py::TestPolicyChainAllProceed::test_empty_chain_returns_proceed PASSED
tests/policies/test_chain.py::TestPolicyChainDenyShortCircuits::test_deny_stops_evaluation PASSED
tests/policies/test_chain.py::TestPolicyChainDenyShortCircuits::test_first_deny_wins PASSED
tests/policies/test_chain.py::TestPolicyChainRetryShortCircuits::test_retry_stops_evaluation PASSED
tests/policies/test_chain.py::TestPolicyChainRetryShortCircuits::test_deny_takes_precedence_over_retry_in_order PASSED
tests/policies/test_chain.py::TestPolicyChainOrdering::test_evaluates_in_order PASSED
```

**Step 5: Lint**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen && poetry run ruff check miniautogen/policies/chain.py tests/policies/test_chain.py
```

**Step 6: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/policies/chain.py tests/policies/test_chain.py
git commit -m "feat: add PolicyChain for composable policy evaluation"
```

**If Task Fails:**

1. **Frozen dataclass with mutable default:** The `__init__` override using `object.__setattr__` is the standard pattern for frozen dataclasses that accept lists. If this fails, verify the `__init__` override is defined correctly.
2. **Protocol isinstance check fails:** Ensure `@runtime_checkable` is on the `Policy` protocol.
3. **RunContext import error:** Verify `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/contracts/run_context.py` exists (confirmed in prerequisites).
4. **Rollback:** `git checkout -- miniautogen/policies/chain.py tests/policies/test_chain.py`

---

## Task 6: Implement TimeoutScope for Structured Timeout Composition

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/policies/timeout.py`
- Test: `/Users/brunocapelao/Projects/miniAutoGen/tests/policies/test_timeout.py`

**Prerequisites:**
- AnyIO 4+ installed (confirmed in `pyproject.toml`)

**Step 1: Write the failing test**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/policies/test_timeout.py`:

```python
from __future__ import annotations

import pytest

import anyio

from miniautogen.policies.timeout import TimeoutScope


class TestTimeoutScopeCreation:
    def test_creates_with_defaults(self):
        scope = TimeoutScope()
        assert scope.pipeline_timeout is None
        assert scope.turn_timeout is None
        assert scope.tool_timeout is None

    def test_creates_with_all_timeouts(self):
        scope = TimeoutScope(
            pipeline_timeout=60.0,
            turn_timeout=30.0,
            tool_timeout=5.0,
        )
        assert scope.pipeline_timeout == 60.0
        assert scope.turn_timeout == 30.0
        assert scope.tool_timeout == 5.0

    def test_is_frozen(self):
        scope = TimeoutScope()
        with pytest.raises(AttributeError):
            scope.pipeline_timeout = 10.0


class TestTimeoutScopePipelineContext:
    @pytest.mark.asyncio
    async def test_pipeline_scope_completes_within_timeout(self):
        scope = TimeoutScope(pipeline_timeout=5.0)
        async with scope.pipeline_scope():
            await anyio.sleep(0.01)
        # No exception = success

    @pytest.mark.asyncio
    async def test_pipeline_scope_raises_on_timeout(self):
        scope = TimeoutScope(pipeline_timeout=0.01)
        with pytest.raises(TimeoutError):
            async with scope.pipeline_scope():
                await anyio.sleep(5.0)

    @pytest.mark.asyncio
    async def test_pipeline_scope_no_timeout_is_noop(self):
        scope = TimeoutScope(pipeline_timeout=None)
        async with scope.pipeline_scope():
            await anyio.sleep(0.01)
        # No exception = success


class TestTimeoutScopeTurnContext:
    @pytest.mark.asyncio
    async def test_turn_scope_completes_within_timeout(self):
        scope = TimeoutScope(turn_timeout=5.0)
        async with scope.turn_scope():
            await anyio.sleep(0.01)

    @pytest.mark.asyncio
    async def test_turn_scope_raises_on_timeout(self):
        scope = TimeoutScope(turn_timeout=0.01)
        with pytest.raises(TimeoutError):
            async with scope.turn_scope():
                await anyio.sleep(5.0)


class TestTimeoutScopeToolContext:
    @pytest.mark.asyncio
    async def test_tool_scope_completes_within_timeout(self):
        scope = TimeoutScope(tool_timeout=5.0)
        async with scope.tool_scope():
            await anyio.sleep(0.01)

    @pytest.mark.asyncio
    async def test_tool_scope_raises_on_timeout(self):
        scope = TimeoutScope(tool_timeout=0.01)
        with pytest.raises(TimeoutError):
            async with scope.tool_scope():
                await anyio.sleep(5.0)


class TestTimeoutScopeNesting:
    @pytest.mark.asyncio
    async def test_inner_turn_timeout_fires_before_outer_pipeline(self):
        """Turn timeout (0.01s) fires before pipeline timeout (10s)."""
        scope = TimeoutScope(pipeline_timeout=10.0, turn_timeout=0.01)
        with pytest.raises(TimeoutError):
            async with scope.pipeline_scope():
                async with scope.turn_scope():
                    await anyio.sleep(5.0)

    @pytest.mark.asyncio
    async def test_inner_tool_timeout_fires_before_outer_turn(self):
        """Tool timeout (0.01s) fires before turn timeout (10s)."""
        scope = TimeoutScope(turn_timeout=10.0, tool_timeout=0.01)
        with pytest.raises(TimeoutError):
            async with scope.turn_scope():
                async with scope.tool_scope():
                    await anyio.sleep(5.0)

    @pytest.mark.asyncio
    async def test_full_nesting_inner_fires_first(self):
        """Tool (0.01s) < Turn (10s) < Pipeline (60s)."""
        scope = TimeoutScope(
            pipeline_timeout=60.0,
            turn_timeout=10.0,
            tool_timeout=0.01,
        )
        with pytest.raises(TimeoutError):
            async with scope.pipeline_scope():
                async with scope.turn_scope():
                    async with scope.tool_scope():
                        await anyio.sleep(5.0)
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen && poetry run pytest tests/policies/test_timeout.py -v
```

**Expected output:**
```
ModuleNotFoundError: No module named 'miniautogen.policies.timeout'
```

**Step 3: Write the implementation**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/policies/timeout.py`:

```python
from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator

import anyio


@dataclass(frozen=True)
class TimeoutScope:
    """Structured timeout composition for nested cancel scopes.

    Provides three levels of timeout nesting:
    - ``pipeline_timeout``: outermost, bounds the entire pipeline run
    - ``turn_timeout``: per-agent turn within the pipeline
    - ``tool_timeout``: per-tool execution within a turn

    Each scope uses ``anyio.fail_after`` for proper structured concurrency.
    When a timeout is ``None``, the scope is a no-op passthrough.
    """

    pipeline_timeout: float | None = None
    turn_timeout: float | None = None
    tool_timeout: float | None = None

    @asynccontextmanager
    async def pipeline_scope(self) -> AsyncIterator[None]:
        """Context manager for pipeline-level timeout."""
        if self.pipeline_timeout is not None:
            with anyio.fail_after(self.pipeline_timeout):
                yield
        else:
            yield

    @asynccontextmanager
    async def turn_scope(self) -> AsyncIterator[None]:
        """Context manager for per-turn timeout."""
        if self.turn_timeout is not None:
            with anyio.fail_after(self.turn_timeout):
                yield
        else:
            yield

    @asynccontextmanager
    async def tool_scope(self) -> AsyncIterator[None]:
        """Context manager for per-tool timeout."""
        if self.tool_timeout is not None:
            with anyio.fail_after(self.tool_timeout):
                yield
        else:
            yield
```

**Step 4: Run test to verify it passes**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen && poetry run pytest tests/policies/test_timeout.py -v
```

**Expected output:**
```
tests/policies/test_timeout.py::TestTimeoutScopeCreation::test_creates_with_defaults PASSED
tests/policies/test_timeout.py::TestTimeoutScopeCreation::test_creates_with_all_timeouts PASSED
tests/policies/test_timeout.py::TestTimeoutScopeCreation::test_is_frozen PASSED
tests/policies/test_timeout.py::TestTimeoutScopePipelineContext::test_pipeline_scope_completes_within_timeout PASSED
tests/policies/test_timeout.py::TestTimeoutScopePipelineContext::test_pipeline_scope_raises_on_timeout PASSED
tests/policies/test_timeout.py::TestTimeoutScopePipelineContext::test_pipeline_scope_no_timeout_is_noop PASSED
tests/policies/test_timeout.py::TestTimeoutScopeTurnContext::test_turn_scope_completes_within_timeout PASSED
tests/policies/test_timeout.py::TestTimeoutScopeTurnContext::test_turn_scope_raises_on_timeout PASSED
tests/policies/test_timeout.py::TestTimeoutScopeToolContext::test_tool_scope_completes_within_timeout PASSED
tests/policies/test_timeout.py::TestTimeoutScopeToolContext::test_tool_scope_raises_on_timeout PASSED
tests/policies/test_timeout.py::TestTimeoutScopeNesting::test_inner_turn_timeout_fires_before_outer_pipeline PASSED
tests/policies/test_timeout.py::TestTimeoutScopeNesting::test_inner_tool_timeout_fires_before_outer_turn PASSED
tests/policies/test_timeout.py::TestTimeoutScopeNesting::test_full_nesting_inner_fires_first PASSED
```

**Step 5: Lint**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen && poetry run ruff check miniautogen/policies/timeout.py tests/policies/test_timeout.py
```

**Step 6: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/policies/timeout.py tests/policies/test_timeout.py
git commit -m "feat: add TimeoutScope for structured nested cancel scopes"
```

**If Task Fails:**

1. **`anyio.fail_after` not raising `TimeoutError`:** AnyIO 4+ raises `TimeoutError` (not `TimeoutCancelledError`). If using AnyIO 3, upgrade.
2. **Nested timeout does not fire:** Ensure the inner `anyio.fail_after` scope is created inside the outer one. AnyIO cancel scopes are properly nested.
3. **Rollback:** `git checkout -- miniautogen/policies/timeout.py tests/policies/test_timeout.py`

---

## Task 7: Export New Types and Update api.py

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/policies/__init__.py`
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/api.py`
- Test: `/Users/brunocapelao/Projects/miniAutoGen/tests/policies/test_policy_exports.py`

**Prerequisites:**
- Tasks 1, 5, 6 completed (approval.py, chain.py, timeout.py exist)

**Step 1: Write the failing test**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/policies/test_policy_exports.py`:

```python
from __future__ import annotations


class TestPoliciesPackageExports:
    def test_approval_types_exported(self):
        from miniautogen.policies import (
            ApprovalGate,
            ApprovalPolicy,
            ApprovalRequest,
            ApprovalResponse,
            AutoApproveGate,
        )

        assert ApprovalPolicy is not None
        assert ApprovalGate is not None
        assert ApprovalRequest is not None
        assert ApprovalResponse is not None
        assert AutoApproveGate is not None

    def test_chain_types_exported(self):
        from miniautogen.policies import Policy, PolicyChain, PolicyDecision

        assert Policy is not None
        assert PolicyChain is not None
        assert PolicyDecision is not None

    def test_timeout_types_exported(self):
        from miniautogen.policies import TimeoutScope

        assert TimeoutScope is not None


class TestApiModuleExports:
    def test_approval_types_in_api(self):
        from miniautogen.api import (
            ApprovalGate,
            ApprovalPolicy,
            ApprovalRequest,
            ApprovalResponse,
            AutoApproveGate,
        )

        assert ApprovalPolicy is not None
        assert ApprovalGate is not None
        assert ApprovalRequest is not None
        assert ApprovalResponse is not None
        assert AutoApproveGate is not None

    def test_chain_types_in_api(self):
        from miniautogen.api import PolicyChain

        assert PolicyChain is not None

    def test_timeout_scope_in_api(self):
        from miniautogen.api import TimeoutScope

        assert TimeoutScope is not None
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen && poetry run pytest tests/policies/test_policy_exports.py -v
```

**Expected output:**
```
ImportError: cannot import name 'ApprovalGate' from 'miniautogen.policies'
```

**Step 3a: Update policies/__init__.py**

Replace the entire contents of `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/policies/__init__.py` with:

```python
from miniautogen.policies.approval import (
    ApprovalGate,
    ApprovalPolicy,
    ApprovalRequest,
    ApprovalResponse,
    AutoApproveGate,
)
from miniautogen.policies.budget import BudgetExceededError, BudgetPolicy, BudgetTracker
from miniautogen.policies.chain import Policy, PolicyChain, PolicyDecision
from miniautogen.policies.execution import ExecutionPolicy
from miniautogen.policies.permission import (
    PermissionDeniedError,
    PermissionPolicy,
    check_permission,
)
from miniautogen.policies.retry import RetryPolicy, build_retrying_call
from miniautogen.policies.timeout import TimeoutScope
from miniautogen.policies.validation import (
    ValidationError,
    ValidationPolicy,
    Validator,
    validate_with_policy,
)

__all__ = [
    "ApprovalGate",
    "ApprovalPolicy",
    "ApprovalRequest",
    "ApprovalResponse",
    "AutoApproveGate",
    "BudgetExceededError",
    "BudgetPolicy",
    "BudgetTracker",
    "ExecutionPolicy",
    "PermissionDeniedError",
    "PermissionPolicy",
    "Policy",
    "PolicyChain",
    "PolicyDecision",
    "RetryPolicy",
    "TimeoutScope",
    "ValidationError",
    "ValidationPolicy",
    "Validator",
    "build_retrying_call",
    "check_permission",
    "validate_with_policy",
]
```

**Step 3b: Update api.py**

In `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/api.py`, add the new imports. After the existing line:

```python
from miniautogen.policies.budget import BudgetExceededError, BudgetTracker
```

Add:

```python
from miniautogen.policies.approval import (
    ApprovalGate,
    ApprovalPolicy,
    ApprovalRequest,
    ApprovalResponse,
    AutoApproveGate,
)
from miniautogen.policies.chain import PolicyChain
from miniautogen.policies.timeout import TimeoutScope
```

In the `__all__` list, after the existing `"BudgetExceededError"` entry in the `# Policy enforcement` section, add the new names. Replace the `# Policy enforcement` section with:

```python
    # Policy enforcement
    "BudgetTracker",
    "BudgetExceededError",
    "ApprovalGate",
    "ApprovalPolicy",
    "ApprovalRequest",
    "ApprovalResponse",
    "AutoApproveGate",
    "PolicyChain",
    "TimeoutScope",
```

**Step 4: Run test to verify it passes**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen && poetry run pytest tests/policies/test_policy_exports.py -v
```

**Expected output:**
```
tests/policies/test_policy_exports.py::TestPoliciesPackageExports::test_approval_types_exported PASSED
tests/policies/test_policy_exports.py::TestPoliciesPackageExports::test_chain_types_exported PASSED
tests/policies/test_policy_exports.py::TestPoliciesPackageExports::test_timeout_types_exported PASSED
tests/policies/test_policy_exports.py::TestApiModuleExports::test_approval_types_in_api PASSED
tests/policies/test_policy_exports.py::TestApiModuleExports::test_chain_types_in_api PASSED
tests/policies/test_policy_exports.py::TestApiModuleExports::test_timeout_scope_in_api PASSED
```

**Step 5: Full test suite regression check**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen && poetry run pytest tests/ -v --timeout=60
```

**Expected output:** All tests pass.

**Step 6: Lint**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen && poetry run ruff check miniautogen/policies/__init__.py miniautogen/api.py tests/policies/test_policy_exports.py
```

**Step 7: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/policies/__init__.py miniautogen/api.py tests/policies/test_policy_exports.py
git commit -m "feat: export ApprovalPolicy, PolicyChain, TimeoutScope from policies and api"
```

**If Task Fails:**

1. **Circular import:** If `policies/__init__.py` importing from `chain.py` causes a cycle (chain imports `RunContext` from core), verify there is no reverse import from core into policies.
2. **`PolicyDecision` is a `Literal` type alias, not a class:** It can still be imported and used for type annotations. The test just checks it is not `None`.
3. **Rollback:** `git checkout -- miniautogen/policies/__init__.py miniautogen/api.py`

---

## Task 8: Code Review Checkpoint

### Run Code Review

1. **Dispatch all 3 reviewers in parallel:**
   - REQUIRED SUB-SKILL: Use requesting-code-review
   - All reviewers run simultaneously (code-reviewer, business-logic-reviewer, security-reviewer)
   - Wait for all to complete

   **Scope for review:**
   - New files: `miniautogen/policies/approval.py`, `miniautogen/policies/chain.py`, `miniautogen/policies/timeout.py`
   - Modified files: `miniautogen/core/events/types.py`, `miniautogen/core/runtime/pipeline_runner.py`, `miniautogen/policies/__init__.py`, `miniautogen/api.py`
   - Test files: All `test_*.py` files created in Tasks 1-7

2. **Handle findings by severity (MANDATORY):**

   **Critical/High/Medium Issues:**
   - Fix immediately (do NOT add TODO comments for these severities)
   - Re-run all 3 reviewers in parallel after fixes
   - Repeat until zero Critical/High/Medium issues remain

   **Low Issues:**
   - Add `TODO(review):` comments in code at the relevant location
   - Format: `TODO(review): [Issue description] (reported by [reviewer] on 2026-03-16, severity: Low)`

   **Cosmetic/Nitpick Issues:**
   - Add `FIXME(nitpick):` comments in code at the relevant location
   - Format: `FIXME(nitpick): [Issue description] (reported by [reviewer] on 2026-03-16, severity: Cosmetic)`

3. **Proceed only when:**
   - Zero Critical/High/Medium issues remain
   - All Low issues have `TODO(review):` comments added
   - All Cosmetic issues have `FIXME(nitpick):` comments added

**Key review focus areas:**
- ApprovalGate is a Protocol (not ABC) -- verify
- All dataclasses are frozen -- verify
- No blocking code in async paths -- verify
- PipelineRunner changes are backward-compatible (all new params default to None) -- verify
- Event types follow existing naming convention (snake_case) -- verify
- No imports leak adapter/provider details into core -- verify

**After review, commit any fixes:**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add -A
git commit -m "fix: address code review findings for Chunk 3 policies"
```

---

## Summary of Deliverables

| Task | File Created/Modified | Purpose |
|------|-----------------------|---------|
| 1 | `policies/approval.py`, `tests/policies/test_approval.py` | ApprovalPolicy, ApprovalGate Protocol, AutoApproveGate |
| 2 | `core/events/types.py`, `tests/policies/test_approval_events.py` | APPROVAL_REQUESTED/GRANTED/DENIED/TIMEOUT events |
| 3 | `core/runtime/pipeline_runner.py`, `tests/core/runtime/test_pipeline_runner_approval.py` | Approval gate integration in PipelineRunner |
| 4 | `core/runtime/pipeline_runner.py`, `tests/core/runtime/test_pipeline_runner_retry.py` | Retry policy integration in PipelineRunner |
| 5 | `policies/chain.py`, `tests/policies/test_chain.py` | PolicyChain for composable policy evaluation |
| 6 | `policies/timeout.py`, `tests/policies/test_timeout.py` | TimeoutScope for structured nested cancel scopes |
| 7 | `policies/__init__.py`, `api.py`, `tests/policies/test_policy_exports.py` | Export all new types |
| 8 | Code review checkpoint | 3-reviewer parallel review |
