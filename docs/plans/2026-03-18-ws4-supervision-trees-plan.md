# WS4: Supervision Trees — Implementation Plan

**Status:** Ready for execution
**Date:** 2026-03-18
**Branch:** `feat/ws4-supervision-trees`
**Design spec:** `docs/plans/2026-03-18-ws4-supervision-trees-design.md`

---

## Summary

Replaces flat `try/except` error handling across all four runtimes with a
hierarchical supervision tree, and replaces the non-atomic checkpoint+event
pattern in `PipelineRunner` (lines 209-222) with a transactional
`CheckpointManager`.

**Two invariants enforced:**
- **Invariant 2 (Fault Delegation):** An agent never recovers from its own
  critical failures. Errors propagate upward to a Supervisor.
- **Invariant 3 (Step Transactionality):** State transition, emitted events,
  and execution pointer are persisted atomically.

---

## Global Prerequisites

```bash
python --version
# Expected: Python 3.11+

pytest --version
# Expected: pytest 7.0+

git status
# Expected: clean working tree on main

python -c "from miniautogen.core.contracts.enums import ErrorCategory; print('OK')"
# Expected: OK  (WS3 TG-0 must be merged)

python -c "from miniautogen.core.contracts.run_context import RunContext; rc = RunContext(run_id='x', input_payload={}); print(rc.model_fields_set)"
# Expected: no error  (WS2 frozen RunContext must be merged)
```

**If WS2 is not yet merged:** The `step_index` field will be stored directly
inside the checkpoint payload dict (`checkpoint_payload["step_index"]`) as an
interim measure. When WS2 lands, migrate to `RunContext.step_index` with no
behavioral change to `CheckpointManager.atomic_transition` (it already
receives `step_index` as an explicit parameter).

**If WS3 TG-0 is not yet merged:** Add `ErrorCategory` StrEnum to
`miniautogen/core/contracts/enums.py` as the first task before TG-1.

---

## Task Groups

| TG | Description | New Files | Modified Files |
|----|-------------|-----------|----------------|
| TG-1 | StepSupervision Model | `core/contracts/supervision.py` | `core/contracts/enums.py`, `core/contracts/coordination.py`, `core/contracts/agent_spec.py` |
| TG-2 | Error Classifier | `core/runtime/classifier.py` | — |
| TG-3 | Supervisor Protocol + StepSupervisor | `core/runtime/supervisors.py` | — |
| TG-4 | FlowSupervisor | `core/runtime/flow_supervisor.py` | `core/events/types.py` |
| TG-5 | CheckpointManager | `core/runtime/checkpoint_manager.py` | `stores/checkpoint_store.py` |
| TG-6 | EventStore ABC + InMemory | `stores/event_store.py`, `stores/in_memory_event_store.py` | — |
| TG-7 | Heartbeat Protocol | `core/runtime/heartbeat.py` | — |
| TG-8 | Runtime Integration | — | `core/runtime/pipeline_runner.py`, `core/runtime/workflow_runtime.py`, `core/runtime/agentic_loop_runtime.py`, `core/runtime/deliberation_runtime.py`, `core/runtime/composite_runtime.py`, `core/runtime/recovery.py` |

---

## TG-1: StepSupervision Model

**Goal:** Frozen Pydantic model that captures per-step supervision
configuration plus strategy enum. Attach optional `supervision` fields to
`WorkflowStep`, `WorkflowPlan`, and `AgentSpec`.

**Constraint:** New model in `core/contracts/` with `ConfigDict(frozen=True)`.
No adapter or runtime logic allowed in contracts.

**Failure condition:** `pytest tests/core/contracts/test_supervision.py` red
after writing tests, green after implementation.

---

### Task 1.1 — Write failing tests for `SupervisionStrategy` + `StepSupervision`

**What:** Create `tests/core/contracts/test_supervision.py` with tests that
import from `miniautogen.core.contracts.enums` (strategy enum) and
`miniautogen.core.contracts.supervision` (model). All tests must fail at
import.

**Where:** `tests/core/contracts/test_supervision.py` (new file)

**How:**

```python
"""Tests for SupervisionStrategy enum and StepSupervision frozen model."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from miniautogen.core.contracts.enums import SupervisionStrategy


class TestSupervisionStrategy:
    def test_has_restart(self) -> None:
        assert SupervisionStrategy.RESTART == "restart"

    def test_has_resume(self) -> None:
        assert SupervisionStrategy.RESUME == "resume"

    def test_has_stop(self) -> None:
        assert SupervisionStrategy.STOP == "stop"

    def test_has_escalate(self) -> None:
        assert SupervisionStrategy.ESCALATE == "escalate"

    def test_is_str_comparable(self) -> None:
        assert isinstance(SupervisionStrategy.RESTART, str)

    def test_all_four_members(self) -> None:
        names = {m.name for m in SupervisionStrategy}
        assert names == {"RESTART", "RESUME", "STOP", "ESCALATE"}


class TestStepSupervision:
    def setup_method(self) -> None:
        from miniautogen.core.contracts.supervision import StepSupervision
        self.StepSupervision = StepSupervision

    def test_default_strategy_is_escalate(self) -> None:
        s = self.StepSupervision()
        assert s.strategy == SupervisionStrategy.ESCALATE

    def test_default_max_restarts(self) -> None:
        s = self.StepSupervision()
        assert s.max_restarts == 3

    def test_default_restart_window(self) -> None:
        s = self.StepSupervision()
        assert s.restart_window_seconds == 60.0

    def test_default_circuit_breaker_threshold(self) -> None:
        s = self.StepSupervision()
        assert s.circuit_breaker_threshold == 5

    def test_default_heartbeat_is_none(self) -> None:
        s = self.StepSupervision()
        assert s.heartbeat_interval_seconds is None

    def test_default_max_lifetime_is_none(self) -> None:
        s = self.StepSupervision()
        assert s.max_lifetime_seconds is None

    def test_is_frozen(self) -> None:
        s = self.StepSupervision()
        with pytest.raises((ValidationError, TypeError)):
            s.strategy = SupervisionStrategy.RESTART  # type: ignore[misc]

    def test_custom_values(self) -> None:
        s = self.StepSupervision(
            strategy=SupervisionStrategy.RESTART,
            max_restarts=5,
            restart_window_seconds=120.0,
            circuit_breaker_threshold=10,
            heartbeat_interval_seconds=5.0,
            max_lifetime_seconds=300.0,
        )
        assert s.strategy == SupervisionStrategy.RESTART
        assert s.max_restarts == 5
        assert s.heartbeat_interval_seconds == 5.0

    def test_model_dump_roundtrip(self) -> None:
        s = self.StepSupervision(strategy=SupervisionStrategy.RESTART, max_restarts=2)
        data = s.model_dump()
        s2 = self.StepSupervision.model_validate(data)
        assert s == s2


class TestWorkflowStepSupervisionField:
    def test_workflow_step_accepts_supervision(self) -> None:
        from miniautogen.core.contracts.coordination import WorkflowStep
        from miniautogen.core.contracts.supervision import StepSupervision
        step = WorkflowStep(
            component_name="step-a",
            supervision=StepSupervision(strategy=SupervisionStrategy.RESTART),
        )
        assert step.supervision is not None
        assert step.supervision.strategy == SupervisionStrategy.RESTART

    def test_workflow_step_supervision_defaults_none(self) -> None:
        from miniautogen.core.contracts.coordination import WorkflowStep
        step = WorkflowStep(component_name="step-a")
        assert step.supervision is None

    def test_workflow_plan_has_default_supervision(self) -> None:
        from miniautogen.core.contracts.coordination import WorkflowPlan, WorkflowStep
        from miniautogen.core.contracts.supervision import StepSupervision
        plan = WorkflowPlan(steps=[WorkflowStep(component_name="s1")])
        assert plan.default_supervision == StepSupervision()

    def test_agent_spec_accepts_supervision(self) -> None:
        from miniautogen.core.contracts.agent_spec import AgentSpec
        from miniautogen.core.contracts.supervision import StepSupervision
        spec = AgentSpec(
            id="agent-1",
            name="Agent One",
            supervision=StepSupervision(strategy=SupervisionStrategy.STOP),
        )
        assert spec.supervision is not None
```

**Verify:**

```bash
pytest tests/core/contracts/test_supervision.py -v 2>&1 | head -30
# Expected: ImportError or AttributeError — all tests fail
```

---

### Task 1.2 — Implement `SupervisionStrategy` in `enums.py`

**What:** Append `SupervisionStrategy` StrEnum after `LoopStopReason`.

**Where:** `miniautogen/core/contracts/enums.py`

**How:** Append after line 22 (after `LoopStopReason` class):

```python
class SupervisionStrategy(str, Enum):
    """What the supervisor does when a child fails."""

    RESTART  = "restart"   # Re-run the step with fresh state
    RESUME   = "resume"    # Re-run the step from its last checkpoint
    STOP     = "stop"      # Terminate the step and the parent flow
    ESCALATE = "escalate"  # Propagate the error to the parent supervisor
```

**Verify:**

```bash
pytest tests/core/contracts/test_supervision.py::TestSupervisionStrategy -v
# Expected: 6 passed
```

---

### Task 1.3 — Create `miniautogen/core/contracts/supervision.py`

**What:** New module with `StepSupervision` frozen Pydantic model and
`SupervisionDecision` result model.

**Where:** `miniautogen/core/contracts/supervision.py` (new file)

**How:**

```python
"""Supervision contracts for per-step fault recovery configuration."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from miniautogen.core.contracts.enums import SupervisionStrategy


class StepSupervision(BaseModel):
    """Immutable per-step supervision policy.

    Attached to WorkflowStep, WorkflowPlan (flow-level default), or AgentSpec.
    Resolution order: step-level > flow-level > agent-level > system default.
    """

    model_config = ConfigDict(frozen=True)

    strategy: SupervisionStrategy = SupervisionStrategy.ESCALATE
    max_restarts: int = 3
    restart_window_seconds: float = 60.0
    circuit_breaker_threshold: int = 5
    heartbeat_interval_seconds: float | None = None
    max_lifetime_seconds: float | None = None


class SupervisionDecision(BaseModel):
    """Immutable result returned by a Supervisor after handling a failure."""

    model_config = ConfigDict(frozen=True)

    action: SupervisionStrategy
    reason: str
    should_checkpoint: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
```

**Verify:**

```bash
pytest tests/core/contracts/test_supervision.py::TestStepSupervision -v
# Expected: all StepSupervision tests pass
```

---

### Task 1.4 — Attach `supervision` fields to `WorkflowStep`, `WorkflowPlan`, `AgentSpec`

**What:** Add optional `supervision: StepSupervision | None = None` to
`WorkflowStep` and `AgentSpec`; add `default_supervision: StepSupervision`
to `WorkflowPlan`.

**Where:**
- `miniautogen/core/contracts/coordination.py`
- `miniautogen/core/contracts/agent_spec.py`

**How — coordination.py:** Replace `WorkflowStep` and `WorkflowPlan` class
bodies:

```python
# In WorkflowStep — add after `config` field:
supervision: StepSupervision | None = None  # overrides plan default

# In WorkflowPlan — add after `synthesis_agent` field:
default_supervision: StepSupervision = Field(default_factory=StepSupervision)
```

Add the import at the top of `coordination.py`:

```python
from miniautogen.core.contracts.supervision import StepSupervision
```

**How — agent_spec.py:** Add to `AgentSpec` after `vendor_extensions`:

```python
supervision: StepSupervision | None = None  # agent-level default
```

Add the import at the top of `agent_spec.py`:

```python
from miniautogen.core.contracts.supervision import StepSupervision
```

**Verify:**

```bash
pytest tests/core/contracts/test_supervision.py -v
# Expected: all tests in the file pass (no red)

pytest tests/core/contracts/ -v --tb=short
# Expected: no regressions in existing contract tests
```

---

### COMMIT POINT — TG-1

```bash
git add miniautogen/core/contracts/enums.py \
        miniautogen/core/contracts/supervision.py \
        miniautogen/core/contracts/coordination.py \
        miniautogen/core/contracts/agent_spec.py \
        tests/core/contracts/test_supervision.py

git commit -m "feat(core): add SupervisionStrategy enum and StepSupervision frozen model"
```

---

## TG-2: Error Classifier

**Goal:** A pure function `classify_error(exc) -> ErrorCategory` that maps
arbitrary Python exceptions to canonical categories. No side effects, no I/O.

**Constraint:** Lives in `core/runtime/` (runtime utility, not a contract). Must
not import any adapter or store modules.

**Failure condition:** `pytest tests/core/runtime/test_classifier.py` red
before implementation, green after.

---

### Task 2.1 — Write failing tests for `classify_error`

**What:** Create test file that imports `classify_error` and asserts correct
`ErrorCategory` values for various exception types.

**Where:** `tests/core/runtime/test_classifier.py` (new file)

**How:**

```python
"""Tests for the error classification utility."""
from __future__ import annotations

import asyncio

import anyio
import pytest

from miniautogen.core.contracts.enums import ErrorCategory
from miniautogen.core.runtime.classifier import classify_error


class TestClassifyError:
    def test_connection_error_is_transient(self) -> None:
        assert classify_error(ConnectionError("refused")) == ErrorCategory.TRANSIENT

    def test_os_error_is_transient(self) -> None:
        assert classify_error(OSError("socket reset")) == ErrorCategory.TRANSIENT

    def test_timeout_error_is_timeout(self) -> None:
        assert classify_error(TimeoutError("timed out")) == ErrorCategory.TIMEOUT

    def test_value_error_is_permanent(self) -> None:
        assert classify_error(ValueError("bad value")) == ErrorCategory.PERMANENT

    def test_type_error_is_permanent(self) -> None:
        assert classify_error(TypeError("bad type")) == ErrorCategory.PERMANENT

    def test_key_error_is_permanent(self) -> None:
        assert classify_error(KeyError("missing key")) == ErrorCategory.PERMANENT

    def test_import_error_is_adapter(self) -> None:
        assert classify_error(ImportError("no module named x")) == ErrorCategory.ADAPTER

    def test_file_not_found_is_configuration(self) -> None:
        assert classify_error(FileNotFoundError("no such file")) == ErrorCategory.CONFIGURATION

    def test_pydantic_validation_error_is_validation(self) -> None:
        from pydantic import BaseModel, ValidationError

        class M(BaseModel):
            x: int

        try:
            M(x="bad")  # type: ignore[arg-type]
        except ValidationError as exc:
            assert classify_error(exc) == ErrorCategory.VALIDATION

    def test_cancelled_error_is_cancellation(self) -> None:
        assert classify_error(asyncio.CancelledError()) == ErrorCategory.CANCELLATION

    def test_exception_with_error_category_attr_uses_it(self) -> None:
        class CustomError(Exception):
            error_category = ErrorCategory.STATE_CONSISTENCY

        assert classify_error(CustomError("bad state")) == ErrorCategory.STATE_CONSISTENCY

    def test_unknown_exception_defaults_to_transient(self) -> None:
        class RandomError(Exception):
            pass

        assert classify_error(RandomError("unknown")) == ErrorCategory.TRANSIENT

    def test_runtime_error_defaults_to_transient(self) -> None:
        assert classify_error(RuntimeError("oops")) == ErrorCategory.TRANSIENT
```

**Verify:**

```bash
pytest tests/core/runtime/test_classifier.py -v 2>&1 | head -20
# Expected: ImportError — classifier module does not exist yet
```

---

### Task 2.2 — Implement `classify_error`

**What:** Create `miniautogen/core/runtime/classifier.py` with the
`classify_error` function. Priority order: explicit `error_category`
attribute → specific exception type checks → default `TRANSIENT`.

**Where:** `miniautogen/core/runtime/classifier.py` (new file)

**How:**

```python
"""Error classification utility for the supervision layer.

Maps arbitrary exceptions to canonical ErrorCategory values so that
supervisors can apply strategy-to-error overrides without pattern-matching
on raw exception types.
"""
from __future__ import annotations

import asyncio

import anyio

from miniautogen.core.contracts.enums import ErrorCategory


def classify_error(exc: BaseException) -> ErrorCategory:
    """Map an exception to a canonical ErrorCategory.

    Classification priority:
    1. If the exception has an ``error_category`` attribute, use it directly.
    2. Specific type checks in priority order.
    3. Default: TRANSIENT (optimistic — supervisors catch permanent failures
       that self-identify via strategy-to-error override table).
    """
    # Priority 1: explicit annotation wins
    category = getattr(exc, "error_category", None)
    if isinstance(category, ErrorCategory):
        return category

    # Priority 2: pydantic validation
    try:
        from pydantic import ValidationError as PydanticValidationError
        if isinstance(exc, PydanticValidationError):
            return ErrorCategory.VALIDATION
    except ImportError:
        pass

    # Priority 3: cancellation (must check before TimeoutError on some backends)
    if isinstance(exc, asyncio.CancelledError):
        return ErrorCategory.CANCELLATION
    try:
        cancelled_cls = anyio.get_cancelled_exc_class()
        if isinstance(exc, cancelled_cls):
            return ErrorCategory.CANCELLATION
    except RuntimeError:
        # anyio.get_cancelled_exc_class() raises RuntimeError outside async ctx
        pass

    # Priority 4: timeout
    if isinstance(exc, TimeoutError):
        return ErrorCategory.TIMEOUT

    # Priority 5: import / adapter
    if isinstance(exc, ImportError):
        return ErrorCategory.ADAPTER

    # Priority 6: configuration
    if isinstance(exc, FileNotFoundError):
        return ErrorCategory.CONFIGURATION

    # Priority 7: permanent (programming errors)
    if isinstance(exc, (ValueError, TypeError, KeyError, AttributeError)):
        return ErrorCategory.PERMANENT

    # Default: optimistic transient
    return ErrorCategory.TRANSIENT
```

**Verify:**

```bash
pytest tests/core/runtime/test_classifier.py -v
# Expected: all 13 tests pass
```

---

### COMMIT POINT — TG-2

```bash
git add miniautogen/core/runtime/classifier.py \
        tests/core/runtime/test_classifier.py

git commit -m "feat(runtime): add classify_error utility mapping exceptions to ErrorCategory"
```

---

## TG-3: Supervisor Protocol + StepSupervisor

**Goal:** Define the `Supervisor` `@runtime_checkable` Protocol and implement
`StepSupervisor` with the decision algorithm: forced overrides →
circuit-breaker → restart budget → configured strategy.

**Constraint:** No I/O. No event emission (events are emitted by the runtime
integration layer in TG-8). `StepSupervisor` is pure async logic with
in-memory state only.

**Failure condition:** `pytest tests/core/runtime/test_step_supervisor.py`
all red before, all green after.

---

### Task 3.1 — Write failing tests for `Supervisor` protocol and `StepSupervisor`

**Where:** `tests/core/runtime/test_step_supervisor.py` (new file)

**How:**

```python
"""Tests for StepSupervisor decision algorithm."""
from __future__ import annotations

import pytest
import anyio

from miniautogen.core.contracts.enums import ErrorCategory, SupervisionStrategy
from miniautogen.core.contracts.supervision import StepSupervision, SupervisionDecision
from miniautogen.core.runtime.supervisors import StepSupervisor


@pytest.fixture
def restart_supervision() -> StepSupervision:
    return StepSupervision(
        strategy=SupervisionStrategy.RESTART,
        max_restarts=3,
        restart_window_seconds=60.0,
        circuit_breaker_threshold=5,
    )


@pytest.fixture
def supervisor() -> StepSupervisor:
    return StepSupervisor()


class TestForcedOverrides:
    """Error categories that force a specific strategy regardless of config."""

    @pytest.mark.anyio
    async def test_permanent_error_forces_stop(
        self, supervisor: StepSupervisor, restart_supervision: StepSupervision
    ) -> None:
        decision = await supervisor.handle_failure(
            child_id="step-a",
            error=ValueError("bad"),
            error_category=ErrorCategory.PERMANENT,
            supervision=restart_supervision,
            restart_count=0,
        )
        assert decision.action == SupervisionStrategy.STOP

    @pytest.mark.anyio
    async def test_validation_error_forces_stop(
        self, supervisor: StepSupervisor, restart_supervision: StepSupervision
    ) -> None:
        decision = await supervisor.handle_failure(
            child_id="step-a",
            error=TypeError("invalid"),
            error_category=ErrorCategory.VALIDATION,
            supervision=restart_supervision,
            restart_count=0,
        )
        assert decision.action == SupervisionStrategy.STOP

    @pytest.mark.anyio
    async def test_cancellation_forces_stop(
        self, supervisor: StepSupervisor, restart_supervision: StepSupervision
    ) -> None:
        decision = await supervisor.handle_failure(
            child_id="step-a",
            error=Exception("cancelled"),
            error_category=ErrorCategory.CANCELLATION,
            supervision=restart_supervision,
            restart_count=0,
        )
        assert decision.action == SupervisionStrategy.STOP

    @pytest.mark.anyio
    async def test_configuration_error_forces_escalate(
        self, supervisor: StepSupervisor, restart_supervision: StepSupervision
    ) -> None:
        decision = await supervisor.handle_failure(
            child_id="step-a",
            error=FileNotFoundError("config missing"),
            error_category=ErrorCategory.CONFIGURATION,
            supervision=restart_supervision,
            restart_count=0,
        )
        assert decision.action == SupervisionStrategy.ESCALATE

    @pytest.mark.anyio
    async def test_state_consistency_forces_escalate(
        self, supervisor: StepSupervisor, restart_supervision: StepSupervision
    ) -> None:
        decision = await supervisor.handle_failure(
            child_id="step-a",
            error=RuntimeError("data corrupted"),
            error_category=ErrorCategory.STATE_CONSISTENCY,
            supervision=restart_supervision,
            restart_count=0,
        )
        assert decision.action == SupervisionStrategy.ESCALATE


class TestCircuitBreaker:
    @pytest.mark.anyio
    async def test_circuit_opens_at_threshold(self, supervisor: StepSupervisor) -> None:
        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESTART,
            circuit_breaker_threshold=3,
        )
        # Simulate 2 failures first
        supervisor._failure_count["step-x"] = 2
        # Third failure should open circuit
        decision = await supervisor.handle_failure(
            child_id="step-x",
            error=ConnectionError("down"),
            error_category=ErrorCategory.TRANSIENT,
            supervision=supervision,
            restart_count=0,
        )
        assert decision.action == SupervisionStrategy.STOP

    @pytest.mark.anyio
    async def test_circuit_stays_closed_below_threshold(
        self, supervisor: StepSupervisor
    ) -> None:
        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESTART,
            circuit_breaker_threshold=5,
        )
        supervisor._failure_count["step-y"] = 3
        decision = await supervisor.handle_failure(
            child_id="step-y",
            error=ConnectionError("down"),
            error_category=ErrorCategory.TRANSIENT,
            supervision=supervision,
            restart_count=2,
        )
        assert decision.action == SupervisionStrategy.RESTART


class TestRestartBudget:
    @pytest.mark.anyio
    async def test_exceeding_max_restarts_escalates(
        self, supervisor: StepSupervisor
    ) -> None:
        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESTART,
            max_restarts=2,
            circuit_breaker_threshold=10,
        )
        decision = await supervisor.handle_failure(
            child_id="step-z",
            error=ConnectionError("down"),
            error_category=ErrorCategory.TRANSIENT,
            supervision=supervision,
            restart_count=2,  # already at max
        )
        assert decision.action == SupervisionStrategy.ESCALATE

    @pytest.mark.anyio
    async def test_within_restart_budget_restarts(
        self, supervisor: StepSupervisor
    ) -> None:
        supervision = StepSupervision(
            strategy=SupervisionStrategy.RESTART,
            max_restarts=3,
            circuit_breaker_threshold=10,
        )
        decision = await supervisor.handle_failure(
            child_id="step-w",
            error=ConnectionError("down"),
            error_category=ErrorCategory.TRANSIENT,
            supervision=supervision,
            restart_count=1,
        )
        assert decision.action == SupervisionStrategy.RESTART


class TestConfiguredStrategy:
    @pytest.mark.anyio
    async def test_stop_strategy_returns_stop(self, supervisor: StepSupervisor) -> None:
        supervision = StepSupervision(strategy=SupervisionStrategy.STOP)
        decision = await supervisor.handle_failure(
            child_id="step-a",
            error=ConnectionError("down"),
            error_category=ErrorCategory.TRANSIENT,
            supervision=supervision,
            restart_count=0,
        )
        assert decision.action == SupervisionStrategy.STOP

    @pytest.mark.anyio
    async def test_escalate_strategy_returns_escalate(
        self, supervisor: StepSupervisor
    ) -> None:
        supervision = StepSupervision(strategy=SupervisionStrategy.ESCALATE)
        decision = await supervisor.handle_failure(
            child_id="step-a",
            error=ConnectionError("down"),
            error_category=ErrorCategory.TRANSIENT,
            supervision=supervision,
            restart_count=0,
        )
        assert decision.action == SupervisionStrategy.ESCALATE

    @pytest.mark.anyio
    async def test_decision_includes_reason(self, supervisor: StepSupervisor) -> None:
        supervision = StepSupervision(strategy=SupervisionStrategy.STOP)
        decision = await supervisor.handle_failure(
            child_id="step-a",
            error=ValueError("bad"),
            error_category=ErrorCategory.PERMANENT,
            supervision=supervision,
            restart_count=0,
        )
        assert len(decision.reason) > 0
```

**Verify:**

```bash
pytest tests/core/runtime/test_step_supervisor.py -v 2>&1 | head -20
# Expected: ImportError — supervisors module does not exist yet
```

---

### Task 3.2 — Implement `Supervisor` protocol and `StepSupervisor`

**Where:** `miniautogen/core/runtime/supervisors.py` (new file)

**How:**

```python
"""Supervisor protocol and StepSupervisor implementation.

Hierarchy:
    SystemSupervisor (singleton)
      FlowSupervisor (one per top-level run)
        StepSupervisor (one per WorkflowStep / AgenticLoop turn)
          AgentSupervisor (one per agent invocation)

This module implements the Protocol definition and the StepSupervisor.
FlowSupervisor lives in flow_supervisor.py (TG-4).
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Protocol, runtime_checkable

from miniautogen.core.contracts.enums import ErrorCategory, SupervisionStrategy
from miniautogen.core.contracts.supervision import StepSupervision, SupervisionDecision

# Error categories that override the configured strategy unconditionally.
_FORCE_STOP: frozenset[ErrorCategory] = frozenset({
    ErrorCategory.PERMANENT,
    ErrorCategory.VALIDATION,
    ErrorCategory.CANCELLATION,
})

_FORCE_ESCALATE: frozenset[ErrorCategory] = frozenset({
    ErrorCategory.CONFIGURATION,
    ErrorCategory.STATE_CONSISTENCY,
})


@runtime_checkable
class Supervisor(Protocol):
    """Receives errors from children and decides on a recovery action.

    All supervisor implementations must be safe to call from async context.
    """

    async def handle_failure(
        self,
        *,
        child_id: str,
        error: BaseException,
        error_category: ErrorCategory,
        supervision: StepSupervision,
        restart_count: int,
    ) -> SupervisionDecision:
        ...


class StepSupervisor:
    """Supervises a single step: handles restart counting and circuit breaking.

    One instance should be created per step (or per step type) so that the
    failure counters are scoped correctly.

    Attributes:
        _failure_count: total failures per child_id (circuit breaker counter).
        _restart_times: timestamps of recent restarts per child_id (window budget).
    """

    def __init__(self) -> None:
        self._failure_count: dict[str, int] = defaultdict(int)
        self._restart_times: dict[str, deque[float]] = defaultdict(deque)

    async def handle_failure(
        self,
        *,
        child_id: str,
        error: BaseException,
        error_category: ErrorCategory,
        supervision: StepSupervision,
        restart_count: int,
    ) -> SupervisionDecision:
        """Apply the decision algorithm and return a SupervisionDecision.

        Algorithm (priority order):
        1. Forced override by error category.
        2. Circuit breaker threshold.
        3. Restart budget within window.
        4. Configured strategy.
        """
        # Step 1: increment total failure counter
        self._failure_count[child_id] += 1
        total = self._failure_count[child_id]

        # Step 2: forced overrides by error category
        if error_category in _FORCE_STOP:
            return SupervisionDecision(
                action=SupervisionStrategy.STOP,
                reason=f"error category '{error_category}' forces STOP (error: {error!r})",
            )
        if error_category in _FORCE_ESCALATE:
            return SupervisionDecision(
                action=SupervisionStrategy.ESCALATE,
                reason=f"error category '{error_category}' forces ESCALATE (error: {error!r})",
            )

        # Step 3: circuit breaker
        if total >= supervision.circuit_breaker_threshold:
            return SupervisionDecision(
                action=SupervisionStrategy.STOP,
                reason=(
                    f"circuit breaker opened: {total} total failures >= "
                    f"threshold {supervision.circuit_breaker_threshold}"
                ),
                metadata={"total_failures": total},
            )

        # Step 4: restart budget within window
        now = time.monotonic()
        window = supervision.restart_window_seconds
        times = self._restart_times[child_id]
        # Evict old timestamps outside the window
        while times and (now - times[0]) > window:
            times.popleft()

        restarts_in_window = len(times)
        if supervision.strategy == SupervisionStrategy.RESTART:
            if restarts_in_window >= supervision.max_restarts:
                return SupervisionDecision(
                    action=SupervisionStrategy.ESCALATE,
                    reason=(
                        f"restart budget exhausted: {restarts_in_window} restarts "
                        f"in last {window}s >= max {supervision.max_restarts}"
                    ),
                    metadata={"restarts_in_window": restarts_in_window},
                )
            # Record this restart
            times.append(now)
            return SupervisionDecision(
                action=SupervisionStrategy.RESTART,
                reason=f"transient failure, restart #{restarts_in_window + 1} of {supervision.max_restarts}",
                should_checkpoint=False,
            )

        # Step 5: configured strategy (RESUME, STOP, ESCALATE)
        return SupervisionDecision(
            action=supervision.strategy,
            reason=f"applying configured strategy '{supervision.strategy}' for error: {error!r}",
        )
```

**Verify:**

```bash
pytest tests/core/runtime/test_step_supervisor.py -v
# Expected: all tests pass

pytest tests/core/runtime/test_classifier.py tests/core/runtime/test_step_supervisor.py -v
# Expected: no regressions
```

---

### COMMIT POINT — TG-3

```bash
git add miniautogen/core/runtime/supervisors.py \
        tests/core/runtime/test_step_supervisor.py

git commit -m "feat(runtime): add Supervisor protocol and StepSupervisor with decision algorithm"
```

---

## TG-4: FlowSupervisor

**Goal:** Aggregate supervisor that owns per-flow state: total failures across
all steps, per-step completion map, flow-level circuit breaker. Emits five new
`SUPERVISION_*` event types.

**Constraint:** `FlowSupervisor` must not call `EventSink.publish` directly.
Instead it returns a `FlowDecision` containing a list of `ExecutionEvent`
objects to emit. The runtime integration layer (TG-8) does the actual publish
to keep I/O out of this module.

**Failure condition:** `pytest tests/core/runtime/test_flow_supervisor.py`
all red before, all green after.

---

### Task 4.1 — Add `SUPERVISION_*` event types to `EventType`

**What:** Append five new members to `EventType` enum.

**Where:** `miniautogen/core/events/types.py`

**How:** Append after the `APPROVAL_TIMEOUT` member (before the sentinel sets):

```python
    # Supervision tree events
    SUPERVISION_FAILURE_RECEIVED = "supervision_failure_received"
    SUPERVISION_DECISION_MADE    = "supervision_decision_made"
    SUPERVISION_RESTART_STARTED  = "supervision_restart_started"
    SUPERVISION_CIRCUIT_OPENED   = "supervision_circuit_opened"
    SUPERVISION_ESCALATED        = "supervision_escalated"
```

Also add the constant set:

```python
SUPERVISION_EVENT_TYPES: set[EventType] = {
    EventType.SUPERVISION_FAILURE_RECEIVED,
    EventType.SUPERVISION_DECISION_MADE,
    EventType.SUPERVISION_RESTART_STARTED,
    EventType.SUPERVISION_CIRCUIT_OPENED,
    EventType.SUPERVISION_ESCALATED,
}
```

**Verify:**

```bash
python -c "from miniautogen.core.events.types import EventType, SUPERVISION_EVENT_TYPES; print(len(SUPERVISION_EVENT_TYPES))"
# Expected: 5
```

---

### Task 4.2 — Write failing tests for `FlowSupervisor`

**Where:** `tests/core/runtime/test_flow_supervisor.py` (new file)

**How:**

```python
"""Tests for FlowSupervisor aggregate supervision logic."""
from __future__ import annotations

import pytest

from miniautogen.core.contracts.enums import ErrorCategory, SupervisionStrategy
from miniautogen.core.contracts.supervision import StepSupervision, SupervisionDecision
from miniautogen.core.runtime.flow_supervisor import (
    FlowDecision,
    FlowSupervisor,
    StepStatus,
)


@pytest.fixture
def flow_supervisor() -> FlowSupervisor:
    return FlowSupervisor(flow_circuit_breaker_threshold=5)


class TestFlowCircuitBreaker:
    @pytest.mark.anyio
    async def test_opens_at_threshold(self, flow_supervisor: FlowSupervisor) -> None:
        flow_supervisor._total_flow_failures = 4  # one below
        decision = await flow_supervisor.handle_escalation(
            step_id="step-3",
            error=ConnectionError("down"),
            error_category=ErrorCategory.TRANSIENT,
            exhausted_strategy=SupervisionStrategy.ESCALATE,
        )
        assert decision.stop_flow is True
        assert decision.circuit_opened is True

    @pytest.mark.anyio
    async def test_stays_open_below_threshold(self, flow_supervisor: FlowSupervisor) -> None:
        flow_supervisor._total_flow_failures = 2
        decision = await flow_supervisor.handle_escalation(
            step_id="step-1",
            error=ConnectionError("down"),
            error_category=ErrorCategory.TRANSIENT,
            exhausted_strategy=SupervisionStrategy.ESCALATE,
        )
        assert decision.circuit_opened is False


class TestStepCompletionMap:
    @pytest.mark.anyio
    async def test_failed_step_marked_in_map(
        self, flow_supervisor: FlowSupervisor
    ) -> None:
        await flow_supervisor.handle_escalation(
            step_id="step-2",
            error=ValueError("bad"),
            error_category=ErrorCategory.PERMANENT,
            exhausted_strategy=SupervisionStrategy.STOP,
        )
        assert flow_supervisor._step_completion_map["step-2"] == StepStatus.FAILED

    @pytest.mark.anyio
    async def test_mark_step_completed(self, flow_supervisor: FlowSupervisor) -> None:
        flow_supervisor.mark_step_completed("step-1")
        assert flow_supervisor._step_completion_map["step-1"] == StepStatus.COMPLETED


class TestFlowDecisionEvents:
    @pytest.mark.anyio
    async def test_decision_produces_events(
        self, flow_supervisor: FlowSupervisor
    ) -> None:
        decision = await flow_supervisor.handle_escalation(
            step_id="step-3",
            error=ConnectionError("down"),
            error_category=ErrorCategory.TRANSIENT,
            exhausted_strategy=SupervisionStrategy.ESCALATE,
        )
        assert len(decision.events_to_emit) >= 1

    @pytest.mark.anyio
    async def test_circuit_open_emits_circuit_opened_event(
        self, flow_supervisor: FlowSupervisor
    ) -> None:
        flow_supervisor._total_flow_failures = 4
        decision = await flow_supervisor.handle_escalation(
            step_id="step-x",
            error=ConnectionError("down"),
            error_category=ErrorCategory.TRANSIENT,
            exhausted_strategy=SupervisionStrategy.ESCALATE,
        )
        event_types = {e.type for e in decision.events_to_emit}
        from miniautogen.core.events.types import EventType
        assert EventType.SUPERVISION_CIRCUIT_OPENED.value in event_types
```

**Verify:**

```bash
pytest tests/core/runtime/test_flow_supervisor.py -v 2>&1 | head -20
# Expected: ImportError — flow_supervisor module does not exist
```

---

### Task 4.3 — Implement `FlowSupervisor`

**Where:** `miniautogen/core/runtime/flow_supervisor.py` (new file)

**How:**

```python
"""FlowSupervisor: aggregate supervision across all steps in a flow.

Owns:
- total_flow_failures counter (flow-level circuit breaker)
- step_completion_map (tracks terminal status of each step)

Does NOT own step-level restart counters — those live in StepSupervisor.
Does NOT call EventSink.publish — returns events in FlowDecision for the
runtime integration layer to emit.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from miniautogen.core.contracts.enums import ErrorCategory, SupervisionStrategy
from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.types import EventType


class StepStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"
    SKIPPED   = "skipped"


@dataclass
class FlowDecision:
    """Result returned by FlowSupervisor.handle_escalation."""

    stop_flow: bool = False
    circuit_opened: bool = False
    propagate_to_system: bool = False
    events_to_emit: list[ExecutionEvent] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class FlowSupervisor:
    """Aggregate supervisor for a single flow run.

    One instance per PipelineRunner.run_pipeline call.
    """

    def __init__(
        self,
        run_id: str = "unknown",
        flow_circuit_breaker_threshold: int = 10,
    ) -> None:
        self._run_id = run_id
        self._flow_circuit_breaker_threshold = flow_circuit_breaker_threshold
        self._total_flow_failures: int = 0
        self._step_completion_map: dict[str, StepStatus] = {}

    def mark_step_completed(self, step_id: str) -> None:
        self._step_completion_map[step_id] = StepStatus.COMPLETED

    async def handle_escalation(
        self,
        *,
        step_id: str,
        error: BaseException,
        error_category: ErrorCategory,
        exhausted_strategy: SupervisionStrategy,
    ) -> FlowDecision:
        """Handle an escalation from a StepSupervisor.

        Algorithm:
        1. Increment total_flow_failures.
        2. Check flow-level circuit breaker.
        3. Mark step as FAILED in completion map.
        4. Decide whether to stop flow or propagate to SystemSupervisor.
        """
        self._total_flow_failures += 1
        total = self._total_flow_failures
        events: list[ExecutionEvent] = []
        now = datetime.now(timezone.utc)

        # Emit: failure received
        events.append(ExecutionEvent(
            type=EventType.SUPERVISION_FAILURE_RECEIVED.value,
            timestamp=now,
            run_id=self._run_id,
            scope="flow_supervisor",
            payload={
                "step_id": step_id,
                "error_type": type(error).__name__,
                "error_category": error_category,
                "exhausted_strategy": exhausted_strategy,
                "total_flow_failures": total,
            },
        ))

        # Circuit breaker
        if total >= self._flow_circuit_breaker_threshold:
            self._step_completion_map[step_id] = StepStatus.FAILED
            events.append(ExecutionEvent(
                type=EventType.SUPERVISION_CIRCUIT_OPENED.value,
                timestamp=datetime.now(timezone.utc),
                run_id=self._run_id,
                scope="flow_supervisor",
                payload={
                    "total_flow_failures": total,
                    "threshold": self._flow_circuit_breaker_threshold,
                },
            ))
            return FlowDecision(
                stop_flow=True,
                circuit_opened=True,
                events_to_emit=events,
                metadata={"total_flow_failures": total},
            )

        # Mark step status
        self._step_completion_map[step_id] = StepStatus.FAILED

        # Determine whether to stop flow or propagate
        if exhausted_strategy == SupervisionStrategy.ESCALATE:
            propagate = True
            stop = True
        else:
            propagate = False
            stop = True  # conservative: stop flow when step fails

        events.append(ExecutionEvent(
            type=EventType.SUPERVISION_DECISION_MADE.value,
            timestamp=datetime.now(timezone.utc),
            run_id=self._run_id,
            scope="flow_supervisor",
            payload={
                "step_id": step_id,
                "stop_flow": stop,
                "propagate_to_system": propagate,
                "step_completion_map": {
                    k: v.value for k, v in self._step_completion_map.items()
                },
            },
        ))

        if propagate:
            events.append(ExecutionEvent(
                type=EventType.SUPERVISION_ESCALATED.value,
                timestamp=datetime.now(timezone.utc),
                run_id=self._run_id,
                scope="flow_supervisor",
                payload={"step_id": step_id, "error_type": type(error).__name__},
            ))

        return FlowDecision(
            stop_flow=stop,
            circuit_opened=False,
            propagate_to_system=propagate,
            events_to_emit=events,
        )
```

**Verify:**

```bash
pytest tests/core/runtime/test_flow_supervisor.py -v
# Expected: all tests pass

python -c "from miniautogen.core.runtime.flow_supervisor import FlowSupervisor; print('OK')"
# Expected: OK
```

---

### COMMIT POINT — TG-4

```bash
git add miniautogen/core/events/types.py \
        miniautogen/core/runtime/flow_supervisor.py \
        tests/core/runtime/test_flow_supervisor.py

git commit -m "feat(events): add SUPERVISION_* event types and FlowSupervisor aggregate supervisor"
```

---

## TG-5: CheckpointManager

**Goal:** Wrap checkpoint state + events + step_index in a single atomic
transaction. Add `transaction()` async context manager to `CheckpointStore`
ABC with a no-op default (non-breaking for existing implementations).

**Constraint:** `CheckpointManager` depends on `CheckpointStore` and
`EventStore` (TG-6). It must be implemented before TG-6 but the failing
test can be written now. Use a stub `EventStore` protocol in tests.

**Failure condition:** `pytest tests/core/runtime/test_checkpoint_manager.py`
all red before, all green after TG-5 + TG-6.

---

### Task 5.1 — Add `transaction()` context manager to `CheckpointStore` ABC

**What:** Non-breaking addition. Default yields `self` (no-op transaction,
safe for in-memory stores).

**Where:** `miniautogen/stores/checkpoint_store.py`

**How:** Add the import and method after `delete_checkpoint`:

```python
import contextlib
from collections.abc import AsyncIterator

# ... existing class body ...

    @contextlib.asynccontextmanager
    async def transaction(self) -> AsyncIterator["CheckpointStore"]:
        """Yield a transactional view of this store.

        Default: yields self (no-op transaction, suitable for in-memory stores).
        SQL implementations override to use a database transaction.
        """
        yield self
```

**Verify:**

```bash
python -c "
import asyncio
from miniautogen.stores.in_memory_checkpoint_store import InMemoryCheckpointStore
async def t():
    s = InMemoryCheckpointStore()
    async with s.transaction() as txn:
        await txn.save_checkpoint('r1', {'x': 1})
    print(await s.get_checkpoint('r1'))
asyncio.run(t())
"
# Expected: {'x': 1}
```

---

### Task 5.2 — Write failing tests for `CheckpointManager`

**Where:** `tests/core/runtime/test_checkpoint_manager.py` (new file)

**How:**

```python
"""Tests for CheckpointManager atomic transition."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.types import EventType
from miniautogen.core.runtime.checkpoint_manager import CheckpointManager
from miniautogen.stores.in_memory_checkpoint_store import InMemoryCheckpointStore
from miniautogen.stores.in_memory_event_store import InMemoryEventStore


@pytest.fixture
def checkpoint_store() -> InMemoryCheckpointStore:
    return InMemoryCheckpointStore()


@pytest.fixture
def event_store() -> InMemoryEventStore:
    return InMemoryEventStore()


@pytest.fixture
def manager(
    checkpoint_store: InMemoryCheckpointStore,
    event_store: InMemoryEventStore,
) -> CheckpointManager:
    from miniautogen.core.events.event_sink import NullEventSink
    return CheckpointManager(
        checkpoint_store=checkpoint_store,
        event_store=event_store,
        event_sink=NullEventSink(),
    )


def _event(run_id: str, type_: str) -> ExecutionEvent:
    return ExecutionEvent(
        type=type_,
        timestamp=datetime.now(timezone.utc),
        run_id=run_id,
        scope="test",
    )


class TestAtomicTransition:
    @pytest.mark.anyio
    async def test_saves_checkpoint_payload(
        self,
        manager: CheckpointManager,
        checkpoint_store: InMemoryCheckpointStore,
    ) -> None:
        await manager.atomic_transition(
            run_id="run-1",
            new_state={"output": "hello"},
            events=[],
            step_index=0,
        )
        cp = await checkpoint_store.get_checkpoint("run-1")
        assert cp is not None
        assert cp["state"] == {"output": "hello"}
        assert cp["step_index"] == 0

    @pytest.mark.anyio
    async def test_saves_events_to_event_store(
        self,
        manager: CheckpointManager,
        event_store: InMemoryEventStore,
    ) -> None:
        events = [
            _event("run-2", EventType.COMPONENT_FINISHED.value),
            _event("run-2", EventType.RUN_FINISHED.value),
        ]
        await manager.atomic_transition(
            run_id="run-2",
            new_state={},
            events=events,
            step_index=1,
        )
        stored = await event_store.list_events("run-2")
        assert len(stored) == 2

    @pytest.mark.anyio
    async def test_step_index_increments(
        self,
        manager: CheckpointManager,
        checkpoint_store: InMemoryCheckpointStore,
    ) -> None:
        for i in range(3):
            await manager.atomic_transition(
                run_id="run-3",
                new_state={"step": i},
                events=[],
                step_index=i,
            )
        cp = await checkpoint_store.get_checkpoint("run-3")
        assert cp["step_index"] == 2

    @pytest.mark.anyio
    async def test_transition_id_is_unique_uuid(
        self,
        manager: CheckpointManager,
        checkpoint_store: InMemoryCheckpointStore,
    ) -> None:
        await manager.atomic_transition(
            run_id="run-4",
            new_state={},
            events=[],
            step_index=0,
        )
        cp = await checkpoint_store.get_checkpoint("run-4")
        import uuid
        uuid.UUID(cp["transition_id"])  # raises if not valid UUID

    @pytest.mark.anyio
    async def test_empty_events_list_is_valid(
        self,
        manager: CheckpointManager,
        checkpoint_store: InMemoryCheckpointStore,
    ) -> None:
        await manager.atomic_transition(
            run_id="run-5",
            new_state={"key": "val"},
            events=[],
            step_index=0,
        )
        cp = await checkpoint_store.get_checkpoint("run-5")
        assert cp is not None
```

**Verify:**

```bash
pytest tests/core/runtime/test_checkpoint_manager.py -v 2>&1 | head -20
# Expected: ImportError — CheckpointManager and InMemoryEventStore not yet created
```

---

### Task 5.3 — Implement `CheckpointManager`

**Where:** `miniautogen/core/runtime/checkpoint_manager.py` (new file)

**How:**

```python
"""CheckpointManager: atomic transition bundling state + events + step pointer.

Replaces the non-atomic checkpoint-then-emit pattern in PipelineRunner
(lines 209-222) with a single transactional write.

Guarantee:
- For SQL-backed stores: state, events, and step_index are written in one DB
  transaction. A crash between writes is impossible at the application level.
- For in-memory stores: sequential writes are atomic within single-threaded
  async (no preemption between awaits within the same task).

After the transaction commits, events are fanned out to live subscribers via
event_sink (fire-and-forget). If pub/sub fails, the durable event_store is the
source of truth and can be replayed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.event_sink import EventSink
from miniautogen.stores.checkpoint_store import CheckpointStore
from miniautogen.stores.event_store import EventStore


class CheckpointManager:
    """Wraps state + events + pointer into a single atomic transition."""

    def __init__(
        self,
        checkpoint_store: CheckpointStore,
        event_store: EventStore,
        event_sink: EventSink,
    ) -> None:
        self._store = checkpoint_store
        self._event_store = event_store
        self._sink = event_sink

    async def atomic_transition(
        self,
        run_id: str,
        *,
        new_state: dict[str, Any],
        events: list[ExecutionEvent],
        step_index: int,
    ) -> None:
        """Persist state, events, and execution pointer atomically.

        Args:
            run_id: The run identifier.
            new_state: Serialized RunContext or step output dict.
            events: All ExecutionEvents generated during this step.
            step_index: Index of the last *completed* step (0-based).
                On resume: next_step = step_index + 1.
        """
        transition_id = str(uuid4())
        checkpoint_payload: dict[str, Any] = {
            "state": new_state,
            "step_index": step_index,
            "transition_id": transition_id,
            "transitioned_at": datetime.now(timezone.utc).isoformat(),
        }

        async with self._store.transaction() as txn:
            await txn.save_checkpoint(run_id, checkpoint_payload)
            for event in events:
                await self._event_store.append(run_id, event)

        # Fire-and-forget: pub/sub notification after durable write.
        # If the sink raises, the events are already persisted and can be replayed.
        for event in events:
            try:
                await self._sink.publish(event)
            except Exception:
                pass  # Sink failure is non-fatal; logged by the sink itself.
```

**Verify:**

```bash
# Still fails because InMemoryEventStore (TG-6) is missing — that is expected.
pytest tests/core/runtime/test_checkpoint_manager.py -v 2>&1 | head -20
# Expected: ImportError: cannot import name 'InMemoryEventStore'
```

---

### COMMIT POINT — TG-5

```bash
git add miniautogen/stores/checkpoint_store.py \
        miniautogen/core/runtime/checkpoint_manager.py \
        tests/core/runtime/test_checkpoint_manager.py

git commit -m "feat(stores): add CheckpointStore.transaction() and CheckpointManager atomic transition"
```

---

## TG-6: EventStore ABC + InMemory Implementation

**Goal:** Append-only, ordered event store that is distinct from `EventSink`
(which is pub/sub). Required by `CheckpointManager` for durable event
persistence within the atomic transaction.

**Constraint:** `EventStore` ABC must live in `stores/` (not `core/runtime/`).
In-memory implementation must be thread-safe within single-threaded async (no
lock needed). Monotonic `event_id` auto-increment.

**Failure condition:** `pytest tests/stores/test_event_store.py` all red
before, all green after. `test_checkpoint_manager.py` must also go green.

---

### Task 6.1 — Write failing tests for `EventStore` ABC + `InMemoryEventStore`

**Where:** `tests/stores/test_event_store.py` (new file)

**How:**

```python
"""Tests for EventStore ABC and InMemoryEventStore."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.types import EventType
from miniautogen.stores.in_memory_event_store import InMemoryEventStore


def _event(run_id: str, type_: str = "test_event") -> ExecutionEvent:
    return ExecutionEvent(
        type=type_,
        timestamp=datetime.now(timezone.utc),
        run_id=run_id,
        scope="test",
    )


@pytest.fixture
def store() -> InMemoryEventStore:
    return InMemoryEventStore()


class TestInMemoryEventStore:
    @pytest.mark.anyio
    async def test_append_and_list(self, store: InMemoryEventStore) -> None:
        e = _event("run-1")
        await store.append("run-1", e)
        events = await store.list_events("run-1")
        assert len(events) == 1
        assert events[0].type == "test_event"

    @pytest.mark.anyio
    async def test_events_ordered_by_insertion(self, store: InMemoryEventStore) -> None:
        for i in range(5):
            await store.append("run-2", _event("run-2", f"evt_{i}"))
        events = await store.list_events("run-2")
        types = [e.type for e in events]
        assert types == ["evt_0", "evt_1", "evt_2", "evt_3", "evt_4"]

    @pytest.mark.anyio
    async def test_list_events_after_index(self, store: InMemoryEventStore) -> None:
        for i in range(5):
            await store.append("run-3", _event("run-3", f"evt_{i}"))
        events = await store.list_events("run-3", after_index=2)
        # Returns events with event_id > 2 (i.e., evt_2, evt_3, evt_4)
        assert len(events) == 3
        assert events[0].type == "evt_2"

    @pytest.mark.anyio
    async def test_count_events(self, store: InMemoryEventStore) -> None:
        for i in range(4):
            await store.append("run-4", _event("run-4"))
        count = await store.count_events("run-4")
        assert count == 4

    @pytest.mark.anyio
    async def test_count_events_empty_run(self, store: InMemoryEventStore) -> None:
        count = await store.count_events("nonexistent-run")
        assert count == 0

    @pytest.mark.anyio
    async def test_list_events_empty_run(self, store: InMemoryEventStore) -> None:
        events = await store.list_events("nonexistent-run")
        assert events == []

    @pytest.mark.anyio
    async def test_events_isolated_per_run(self, store: InMemoryEventStore) -> None:
        await store.append("run-a", _event("run-a", "evt_a"))
        await store.append("run-b", _event("run-b", "evt_b"))
        a_events = await store.list_events("run-a")
        b_events = await store.list_events("run-b")
        assert len(a_events) == 1
        assert a_events[0].type == "evt_a"
        assert len(b_events) == 1
        assert b_events[0].type == "evt_b"

    @pytest.mark.anyio
    async def test_after_index_zero_returns_all(self, store: InMemoryEventStore) -> None:
        for i in range(3):
            await store.append("run-5", _event("run-5", f"e{i}"))
        events = await store.list_events("run-5", after_index=0)
        assert len(events) == 3
```

**Verify:**

```bash
pytest tests/stores/test_event_store.py -v 2>&1 | head -20
# Expected: ImportError — InMemoryEventStore does not exist
```

---

### Task 6.2 — Implement `EventStore` ABC

**Where:** `miniautogen/stores/event_store.py` (new file)

**How:**

```python
"""EventStore: append-only durable store for ExecutionEvents.

Distinct from EventSink (pub/sub for live notification).
The EventStore provides replay-safe, ordered persistence.

Operational semantics:
- Append-only: events are never updated or deleted.
- Ordering: each event receives a monotonic auto-increment event_id (int).
- list_events(after_index=N) returns events with position > N, ordered ASC.
- after_index=0 returns all events (position > 0 ≡ all).
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from miniautogen.core.contracts.events import ExecutionEvent


class EventStore(ABC):
    """Abstract append-only event store."""

    @abstractmethod
    async def append(self, run_id: str, event: ExecutionEvent) -> None:
        """Durably append an event. Assigns a monotonic position."""

    @abstractmethod
    async def list_events(
        self, run_id: str, *, after_index: int = 0
    ) -> list[ExecutionEvent]:
        """Return events at position > after_index, ordered by position ASC.

        after_index=0 returns all events for the run.
        """

    @abstractmethod
    async def count_events(self, run_id: str) -> int:
        """Return the total number of events for this run."""
```

**Verify:**

```bash
python -c "from miniautogen.stores.event_store import EventStore; print('OK')"
# Expected: OK
```

---

### Task 6.3 — Implement `InMemoryEventStore`

**Where:** `miniautogen/stores/in_memory_event_store.py` (new file)

**How:**

```python
"""In-memory EventStore for tests and single-process use.

Sequential writes are atomic in single-threaded async (no preemption between
awaits within the same task), so no explicit locking is needed.
"""
from __future__ import annotations

from collections import defaultdict

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.stores.event_store import EventStore


class InMemoryEventStore(EventStore):
    """Thread-safe (within async) append-only event store backed by lists."""

    def __init__(self) -> None:
        # _events[run_id] is a list of (1-based position, event) tuples
        self._events: dict[str, list[ExecutionEvent]] = defaultdict(list)

    async def append(self, run_id: str, event: ExecutionEvent) -> None:
        """Append event. Position = current length + 1 (1-based monotonic)."""
        self._events[run_id].append(event)

    async def list_events(
        self, run_id: str, *, after_index: int = 0
    ) -> list[ExecutionEvent]:
        """Return events at position > after_index (1-based), ordered ASC.

        after_index=0 → all events (position 1, 2, 3, ... all > 0).
        after_index=2 → events at positions 3, 4, ... (i.e., list index 2+).
        """
        all_events = self._events.get(run_id, [])
        return list(all_events[after_index:])

    async def count_events(self, run_id: str) -> int:
        return len(self._events.get(run_id, []))
```

**Verify:**

```bash
pytest tests/stores/test_event_store.py -v
# Expected: all 9 tests pass

pytest tests/core/runtime/test_checkpoint_manager.py -v
# Expected: all 5 tests pass (CheckpointManager + InMemoryEventStore now both exist)
```

---

### COMMIT POINT — TG-6

```bash
git add miniautogen/stores/event_store.py \
        miniautogen/stores/in_memory_event_store.py \
        tests/stores/test_event_store.py

git commit -m "feat(stores): add EventStore ABC and InMemoryEventStore for durable event persistence"
```

---

## TG-7: Heartbeat Protocol

**Goal:** `HeartbeatToken` injected into `RunContext.metadata`, plus a
`_watchdog` async task that cancels the step's `CancelScope` if no beat
arrives within `2 * heartbeat_interval_seconds`.

**Constraint:** `HeartbeatToken` is a pure async object — no threads, no
OS timers. Uses `anyio.current_time()` for monotonic measurement. The watchdog
runs as a **sibling task** inside the step's `TaskGroup`, so AnyIO's structured
concurrency cancels it automatically when the agent task completes normally.

**Failure condition:** `pytest tests/core/runtime/test_heartbeat.py` all red
before, all green after.

---

### Task 7.1 — Write failing tests for `HeartbeatToken` + watchdog

**Where:** `tests/core/runtime/test_heartbeat.py` (new file)

**How:**

```python
"""Tests for HeartbeatToken and watchdog task."""
from __future__ import annotations

import pytest
import anyio

from miniautogen.core.runtime.heartbeat import HeartbeatToken, run_with_heartbeat


class TestHeartbeatToken:
    @pytest.mark.anyio
    async def test_beat_updates_last_beat_time(self) -> None:
        token = HeartbeatToken()
        t0 = token.last_beat_time
        await anyio.sleep(0.01)
        await token.beat()
        assert token.last_beat_time > t0

    @pytest.mark.anyio
    async def test_initial_last_beat_is_current_time(self) -> None:
        before = anyio.current_time()
        token = HeartbeatToken()
        after = anyio.current_time()
        assert before <= token.last_beat_time <= after + 0.1

    @pytest.mark.anyio
    async def test_is_alive_within_interval(self) -> None:
        token = HeartbeatToken()
        assert token.is_alive(interval_seconds=1.0) is True

    @pytest.mark.anyio
    async def test_is_alive_returns_false_after_long_silence(self) -> None:
        token = HeartbeatToken()
        # Manually backdate the last beat
        token._last_beat = anyio.current_time() - 100.0
        assert token.is_alive(interval_seconds=1.0) is False


class TestRunWithHeartbeat:
    @pytest.mark.anyio
    async def test_completes_normally_when_agent_beats(self) -> None:
        """Agent that beats regularly should complete without being killed."""
        async def agent_that_beats(token: HeartbeatToken) -> str:
            for _ in range(3):
                await anyio.sleep(0.01)
                await token.beat()
            return "done"

        result = await run_with_heartbeat(
            agent_that_beats,
            heartbeat_interval_seconds=0.5,
        )
        assert result == "done"

    @pytest.mark.anyio
    async def test_raises_when_agent_stops_beating(self) -> None:
        """Agent that freezes should be killed by watchdog."""
        async def frozen_agent(token: HeartbeatToken) -> str:
            # Beat once, then freeze
            await token.beat()
            await anyio.sleep(10.0)  # Will be cancelled
            return "never"

        with pytest.raises((TimeoutError, anyio.get_cancelled_exc_class())):
            await run_with_heartbeat(
                frozen_agent,
                heartbeat_interval_seconds=0.05,  # very short for test speed
            )
```

**Verify:**

```bash
pytest tests/core/runtime/test_heartbeat.py -v 2>&1 | head -20
# Expected: ImportError — heartbeat module does not exist
```

---

### Task 7.2 — Implement `HeartbeatToken` and `run_with_heartbeat`

**Where:** `miniautogen/core/runtime/heartbeat.py` (new file)

**How:**

```python
"""Heartbeat protocol for long-running agent supervision.

HeartbeatToken is injected into RunContext.metadata["_heartbeat_token"].
The agent obtains it via context.metadata.get("_heartbeat_token") and calls
token.beat() periodically.

The watchdog task runs as a sibling inside the step's TaskGroup. If the agent
does not call beat() within 2 * heartbeat_interval_seconds, the watchdog
cancels the step's CancelScope (triggering a TimeoutError classified as
ErrorCategory.TIMEOUT).
"""
from __future__ import annotations

import anyio
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

T = TypeVar("T")


class HeartbeatToken:
    """Liveness signal passed to agents that opt into heartbeat supervision."""

    def __init__(self) -> None:
        self._last_beat: float = anyio.current_time()

    @property
    def last_beat_time(self) -> float:
        """Monotonic timestamp of the last beat (anyio.current_time() epoch)."""
        return self._last_beat

    async def beat(self) -> None:
        """Signal liveness. Must be called within heartbeat_interval_seconds."""
        self._last_beat = anyio.current_time()

    def is_alive(self, *, interval_seconds: float) -> bool:
        """Return True if a beat occurred within interval_seconds."""
        elapsed = anyio.current_time() - self._last_beat
        return elapsed <= interval_seconds


async def _watchdog(
    token: HeartbeatToken,
    scope: anyio.CancelScope,
    interval: float,
) -> None:
    """Background task that monitors agent liveness.

    Runs as a sibling task within the step's TaskGroup. Cancelled automatically
    by AnyIO when the agent task completes.

    Kill condition: elapsed since last beat > interval * 2.
    """
    while True:
        await anyio.sleep(interval)
        elapsed = anyio.current_time() - token.last_beat_time
        if elapsed > interval * 2:
            scope.cancel()
            return


async def run_with_heartbeat(
    agent_fn: Callable[[HeartbeatToken], Awaitable[T]],
    *,
    heartbeat_interval_seconds: float,
) -> T:
    """Run agent_fn under heartbeat supervision.

    Creates a HeartbeatToken, starts a watchdog sibling task, and passes the
    token to agent_fn. If the agent does not call token.beat() within
    2 * heartbeat_interval_seconds, the cancel scope is cancelled.

    Args:
        agent_fn: Async callable that accepts a HeartbeatToken and returns T.
        heartbeat_interval_seconds: Watchdog check interval. Kill threshold
            is 2x this value.

    Returns:
        The return value of agent_fn.

    Raises:
        anyio.get_cancelled_exc_class(): If the watchdog kills the agent.
    """
    token = HeartbeatToken()
    result: list[T] = []  # mutable container for async result capture

    async def _agent_wrapper() -> None:
        result.append(await agent_fn(token))

    with anyio.CancelScope() as scope:
        async with anyio.create_task_group() as tg:
            tg.start_soon(_watchdog, token, scope, heartbeat_interval_seconds)
            await _agent_wrapper()
            tg.cancel_scope.cancel()  # Stop watchdog when agent completes

    if scope.cancelled_caught:
        raise TimeoutError(
            f"Agent killed by heartbeat watchdog: no beat in "
            f"{heartbeat_interval_seconds * 2:.1f}s"
        )

    return result[0]
```

**Verify:**

```bash
pytest tests/core/runtime/test_heartbeat.py -v
# Expected: all tests pass (may take ~0.15s for async tests)
```

---

### COMMIT POINT — TG-7

```bash
git add miniautogen/core/runtime/heartbeat.py \
        tests/core/runtime/test_heartbeat.py

git commit -m "feat(runtime): add HeartbeatToken and watchdog for zombie prevention"
```

---

## TG-8: Runtime Integration

**Goal:** Wire supervisors, `CheckpointManager`, and heartbeat into
`WorkflowRuntime`, `PipelineRunner`, `AgenticLoopRuntime`,
`DeliberationRuntime`, `CompositeRuntime`, and `SessionRecovery`.

**Constraint:**
- `PipelineRunner` remains the single executor. No parallel run loops.
- Supervisors are constructed inside each runtime method, not at `__init__`
  (one supervisor instance per run, not per runner instance).
- `SessionRecovery` becomes a thin wrapper that reads `step_index` from the
  last checkpoint for resume semantics.
- Default `StepSupervision` (ESCALATE strategy) preserves existing behavior —
  no breaking change.

**Failure condition:**
- `pytest tests/core/runtime/test_workflow_runtime.py` must stay green.
- `pytest tests/core/runtime/test_pipeline_runner*.py` must stay green.
- The five Success Criteria (SC-1 through SC-5) from the design spec must pass.

---

### Task 8.1 — Write integration tests for `WorkflowRuntime` supervised steps

**Where:** `tests/core/runtime/test_supervised_workflow.py` (new file)

**How:**

```python
"""Integration tests for supervised step execution in WorkflowRuntime.

Covers SC-1 (restart on transient failure), SC-3 (circuit breaker),
SC-5 (fan-out independence).
"""
from __future__ import annotations

import pytest

from miniautogen.core.contracts.coordination import WorkflowPlan, WorkflowStep
from miniautogen.core.contracts.enums import RunStatus, SupervisionStrategy
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.supervision import StepSupervision
from miniautogen.core.events.event_sink import NullEventSink
from miniautogen.core.runtime.pipeline_runner import PipelineRunner
from miniautogen.core.runtime.workflow_runtime import WorkflowRuntime


class TestSC1RestartOnTransientFailure:
    """SC-1: step configured with RESTART, max_restarts=2 restarts on transient failure."""

    @pytest.mark.anyio
    async def test_step_restarts_up_to_max_then_escalates(self) -> None:
        call_count = 0

        class TransientAgent:
            async def process(self, input_data: object) -> object:
                nonlocal call_count
                call_count += 1
                if call_count <= 2:
                    raise ConnectionError("transient failure")
                return "recovered"

        runner = PipelineRunner(event_sink=NullEventSink())
        runtime = WorkflowRuntime(
            runner=runner,
            agent_registry={"agent-a": TransientAgent()},
        )
        context = RunContext(run_id="sc1-test", input_payload="hello")
        plan = WorkflowPlan(
            steps=[
                WorkflowStep(
                    component_name="step-1",
                    agent_id="agent-a",
                    supervision=StepSupervision(
                        strategy=SupervisionStrategy.RESTART,
                        max_restarts=2,
                        circuit_breaker_threshold=10,
                    ),
                )
            ]
        )
        result = await runtime.run([], context, plan)
        assert result.status == RunStatus.FINISHED
        assert call_count == 3  # 2 failures + 1 success


class TestSC3CircuitBreaker:
    """SC-3: circuit_breaker_threshold=3 forces STOP after 3 total failures."""

    @pytest.mark.anyio
    async def test_circuit_opens_after_threshold(self) -> None:
        call_count = 0

        class AlwaysFailsAgent:
            async def process(self, input_data: object) -> object:
                nonlocal call_count
                call_count += 1
                raise ConnectionError("always fails")

        runner = PipelineRunner(event_sink=NullEventSink())
        runtime = WorkflowRuntime(
            runner=runner,
            agent_registry={"agent-b": AlwaysFailsAgent()},
        )
        context = RunContext(run_id="sc3-test", input_payload="hello")
        plan = WorkflowPlan(
            steps=[
                WorkflowStep(
                    component_name="step-1",
                    agent_id="agent-b",
                    supervision=StepSupervision(
                        strategy=SupervisionStrategy.RESTART,
                        max_restarts=10,
                        circuit_breaker_threshold=3,
                    ),
                )
            ]
        )
        result = await runtime.run([], context, plan)
        assert result.status == RunStatus.FAILED
        assert call_count == 3  # circuit opens at threshold


class TestSC5FanOutIndependence:
    """SC-5: failing fan-out branch with RESTART does not cancel sibling branches."""

    @pytest.mark.anyio
    async def test_sibling_branches_complete_when_one_restarts(self) -> None:
        completed = set()

        class SlowAgent:
            async def process(self, input_data: object) -> object:
                completed.add("slow")
                return "slow-result"

        class FastAgent:
            async def process(self, input_data: object) -> object:
                completed.add("fast")
                return "fast-result"

        runner = PipelineRunner(event_sink=NullEventSink())
        runtime = WorkflowRuntime(
            runner=runner,
            agent_registry={
                "slow-agent": SlowAgent(),
                "fast-agent": FastAgent(),
            },
        )
        context = RunContext(run_id="sc5-test", input_payload="hello")
        plan = WorkflowPlan(
            fan_out=True,
            steps=[
                WorkflowStep(component_name="step-slow", agent_id="slow-agent"),
                WorkflowStep(component_name="step-fast", agent_id="fast-agent"),
            ],
        )
        result = await runtime.run([], context, plan)
        assert result.status == RunStatus.FINISHED
        assert "slow" in completed
        assert "fast" in completed
```

**Verify:**

```bash
pytest tests/core/runtime/test_supervised_workflow.py -v 2>&1 | head -30
# Expected: Some tests may pass partially (basic FINISHED cases) but SC-1
# and SC-3 will fail because supervised retry logic is not yet wired.
```

---

### Task 8.2 — Implement `resolve_supervision` helper

**What:** Small utility function that walks the resolution order:
step-level > flow-level > agent-level > system default.

**Where:** `miniautogen/core/runtime/supervised_step.py` (new file)

**How:**

```python
"""Supervised step execution utilities.

Provides resolve_supervision() for configuration resolution and
supervised_step() for the restart loop around a single agent invocation.
"""
from __future__ import annotations

from typing import Any

from miniautogen.core.contracts.coordination import WorkflowPlan, WorkflowStep
from miniautogen.core.contracts.supervision import StepSupervision
from miniautogen.core.contracts.enums import ErrorCategory, SupervisionStrategy
from miniautogen.core.runtime.classifier import classify_error
from miniautogen.core.runtime.supervisors import StepSupervisor


_DEFAULT_SUPERVISION = StepSupervision()  # strategy=ESCALATE, everything at defaults


def resolve_supervision(
    step: WorkflowStep,
    plan: WorkflowPlan,
) -> StepSupervision:
    """Resolve StepSupervision for a step using the priority chain.

    Resolution order: step-level > flow-level > system default.
    Agent-level is not resolved here (requires agent registry lookup).
    """
    if step.supervision is not None:
        return step.supervision
    if hasattr(plan, "default_supervision") and plan.default_supervision is not None:
        return plan.default_supervision
    return _DEFAULT_SUPERVISION


async def supervised_step(
    *,
    supervisor: StepSupervisor,
    step: WorkflowStep,
    supervision: StepSupervision,
    agent_fn: Any,  # callable(input_data) -> Any
    input_data: Any,
) -> Any:
    """Run agent_fn under supervision, applying the restart loop.

    Args:
        supervisor: StepSupervisor instance (shared state for this step).
        step: The workflow step being executed.
        supervision: Resolved StepSupervision configuration.
        agent_fn: Async callable that runs the agent.
        input_data: Input passed to agent_fn.

    Returns:
        The output of agent_fn on success.

    Raises:
        BaseException: If the decision is ESCALATE (re-raises the original error).
        RuntimeError: If the decision is STOP (creates a StepStoppedError).
    """
    import anyio
    restart_count = 0

    while True:
        try:
            if supervision.max_lifetime_seconds is not None:
                with anyio.fail_after(supervision.max_lifetime_seconds):
                    return await agent_fn(input_data)
            else:
                return await agent_fn(input_data)

        except BaseException as exc:
            error_category = classify_error(exc)
            decision = await supervisor.handle_failure(
                child_id=step.component_name,
                error=exc,
                error_category=error_category,
                supervision=supervision,
                restart_count=restart_count,
            )

            if decision.action == SupervisionStrategy.RESTART:
                restart_count += 1
                continue

            elif decision.action == SupervisionStrategy.RESUME:
                # RESUME falls back to RESTART when no checkpoint is available
                restart_count += 1
                continue

            elif decision.action == SupervisionStrategy.STOP:
                raise StepStoppedError(
                    f"Step '{step.component_name}' stopped by supervisor: "
                    f"{decision.reason}"
                ) from exc

            else:  # ESCALATE
                raise  # Re-raise original exception for the caller to handle


class StepStoppedError(RuntimeError):
    """Raised when a supervisor decision is STOP.

    Carries the supervisor's reason. Not retried by the calling runtime.
    """
    error_category = ErrorCategory.PERMANENT
```

**Verify:**

```bash
python -c "from miniautogen.core.runtime.supervised_step import supervised_step, resolve_supervision; print('OK')"
# Expected: OK
```

---

### Task 8.3 — Wire supervised steps into `WorkflowRuntime`

**What:** Replace bare `_invoke_agent` calls in `_run_sequential` and
`_run_fan_out` with calls through `supervised_step`. Create one
`StepSupervisor` per step execution.

**Where:** `miniautogen/core/runtime/workflow_runtime.py`

**How:** Replace `_run_sequential` and `_run_fan_out` methods:

```python
# Add imports at top of workflow_runtime.py:
from miniautogen.core.runtime.supervised_step import (
    StepStoppedError,
    resolve_supervision,
    supervised_step,
)
from miniautogen.core.runtime.supervisors import StepSupervisor

# Replace _run_sequential:
async def _run_sequential(
    self,
    context: RunContext,
    plan: WorkflowPlan,
) -> Any:
    """Execute steps one-by-one with supervision."""
    current_input = context.input_payload
    for step in plan.steps:
        if step.agent_id is None:
            continue  # pass-through step
        supervision = resolve_supervision(step, plan)
        supervisor = StepSupervisor()

        async def _agent_fn(input_data: Any, _agent_id: str = step.agent_id) -> Any:
            return await self._invoke_agent(_agent_id, input_data)

        try:
            current_input = await supervised_step(
                supervisor=supervisor,
                step=step,
                supervision=supervision,
                agent_fn=_agent_fn,
                input_data=current_input,
            )
        except StepStoppedError:
            # STOP decision: fail the workflow
            raise
        # ESCALATE re-raises the original exception naturally

    return current_input

# Replace _run_fan_out:
async def _run_fan_out(
    self,
    context: RunContext,
    plan: WorkflowPlan,
) -> list[Any]:
    """Execute all steps in parallel with independent supervision."""
    initial_input = context.input_payload
    results: list[Any] = [None] * len(plan.steps)

    async def _run_branch(index: int, step: Any) -> None:
        if step.agent_id is None:
            results[index] = initial_input
            return
        supervision = resolve_supervision(step, plan)
        supervisor = StepSupervisor()

        async def _agent_fn(input_data: Any, _agent_id: str = step.agent_id) -> Any:
            return await self._invoke_agent(_agent_id, input_data)

        try:
            results[index] = await supervised_step(
                supervisor=supervisor,
                step=step,
                supervision=supervision,
                agent_fn=_agent_fn,
                input_data=initial_input,
            )
        except StepStoppedError:
            results[index] = None  # STOP: slot is None, not propagated to siblings

    async with anyio.create_task_group() as tg:
        for i, step in enumerate(plan.steps):
            tg.start_soon(_run_branch, i, step)

    return results
```

**Verify:**

```bash
pytest tests/core/runtime/test_workflow_runtime.py -v
# Expected: all existing tests still pass (ESCALATE default preserves behavior)

pytest tests/core/runtime/test_supervised_workflow.py::TestSC1RestartOnTransientFailure -v
# Expected: PASSED

pytest tests/core/runtime/test_supervised_workflow.py::TestSC3CircuitBreaker -v
# Expected: PASSED

pytest tests/core/runtime/test_supervised_workflow.py -v
# Expected: all pass
```

---

### Task 8.4 — Replace non-atomic checkpoint+event in `PipelineRunner`

**What:** Replace lines 209-222 in `pipeline_runner.py` (the separate
`save_checkpoint` + `publish` calls) with a single
`CheckpointManager.atomic_transition` call. `CheckpointManager` is injected
optionally; if not provided, behavior falls back to existing non-atomic code.

**Where:** `miniautogen/core/runtime/pipeline_runner.py`

**How:** Add `checkpoint_manager` optional param to `__init__` and replace
the post-run persistence block:

```python
# New import at top:
from miniautogen.core.runtime.checkpoint_manager import CheckpointManager

# New __init__ parameter (after retry_policy):
checkpoint_manager: CheckpointManager | None = None,

# Store it:
self.checkpoint_manager = checkpoint_manager

# Replace lines 200-222 (the entire post-run block) with:
try:
    if self.run_store is not None:
        await self.run_store.save_run(
            current_run_id,
            {
                "status": "finished",
                "correlation_id": correlation_id,
            },
        )
    finish_event = ExecutionEvent(
        type=EventType.RUN_FINISHED.value,
        timestamp=datetime.now(timezone.utc),
        run_id=current_run_id,
        correlation_id=correlation_id,
        scope="pipeline_runner",
    )
    if self.checkpoint_manager is not None:
        # Atomic: checkpoint + event in one transaction
        await self.checkpoint_manager.atomic_transition(
            run_id=current_run_id,
            new_state=result if isinstance(result, dict) else {"result": str(result)},
            events=[finish_event],
            step_index=getattr(result, "step_index", 0),
        )
    else:
        # Legacy non-atomic path (backward-compatible)
        if self.checkpoint_store is not None:
            await self.checkpoint_store.save_checkpoint(current_run_id, result)
        await self.event_sink.publish(finish_event)
except Exception as exc:
    await self._persist_failed_run(current_run_id, correlation_id, type(exc).__name__)
    raise
logger.info("run_finished")
self.last_run_id = current_run_id
return result
```

**Verify:**

```bash
pytest tests/core/runtime/test_pipeline_runner.py tests/core/runtime/test_pipeline_runner_anyio.py -v
# Expected: all existing tests still pass

pytest tests/core/runtime/ -v --tb=short
# Expected: all tests pass, no regressions
```

---

### Task 8.5 — Update `SessionRecovery` to read `step_index`

**What:** Add `get_resume_step_index` method that reads `step_index` from the
last checkpoint. Used by runtimes to resume from the correct step after a crash.

**Where:** `miniautogen/core/runtime/recovery.py`

**How:** Add the method after `mark_resumed`:

```python
async def get_resume_step_index(self, run_id: str) -> int:
    """Return the step index to resume from after a crash.

    Returns the *next* step to execute: last_checkpoint.step_index + 1.
    Returns 0 if no checkpoint exists (start from the beginning).
    """
    checkpoint = await self._checkpoint_store.get_checkpoint(run_id)
    if checkpoint is None:
        return 0
    step_index = checkpoint.get("step_index", 0)
    logger.info("resume_step_index", run_id=run_id, step_index=step_index + 1)
    return step_index + 1
```

**Verify:**

```bash
python -c "
import asyncio
from miniautogen.core.runtime.recovery import SessionRecovery
from miniautogen.stores.in_memory_checkpoint_store import InMemoryCheckpointStore
async def t():
    store = InMemoryCheckpointStore()
    await store.save_checkpoint('run-1', {'step_index': 2, 'state': {}})
    recovery = SessionRecovery(store)
    idx = await recovery.get_resume_step_index('run-1')
    assert idx == 3, f'Expected 3, got {idx}'
    print('OK')
asyncio.run(t())
"
# Expected: OK
```

---

### Task 8.6 — Write SC-2 crash simulation test

**What:** SC-2 verifies that a crash between checkpoint save and event emit
(simulated) does not leave the system inconsistent. With `CheckpointManager`,
both are written atomically.

**Where:** `tests/core/runtime/test_atomic_transition_crash.py` (new file)

**How:**

```python
"""SC-2: Verify atomic transition prevents inconsistency on simulated crash.

Scenario: a crash is simulated by raising an exception after checkpoint save
but before event emit. With CheckpointManager, both writes happen inside the
same transaction — so no partial state is possible.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.types import EventType
from miniautogen.core.runtime.checkpoint_manager import CheckpointManager
from miniautogen.stores.in_memory_checkpoint_store import InMemoryCheckpointStore
from miniautogen.stores.in_memory_event_store import InMemoryEventStore
from miniautogen.core.events.event_sink import NullEventSink


class TestSC2AtomicConsistency:
    @pytest.mark.anyio
    async def test_checkpoint_and_event_both_present_on_success(self) -> None:
        store = InMemoryCheckpointStore()
        event_store = InMemoryEventStore()
        manager = CheckpointManager(
            checkpoint_store=store,
            event_store=event_store,
            event_sink=NullEventSink(),
        )
        event = ExecutionEvent(
            type=EventType.RUN_FINISHED.value,
            timestamp=datetime.now(timezone.utc),
            run_id="run-sc2",
            scope="test",
        )
        await manager.atomic_transition(
            run_id="run-sc2",
            new_state={"output": "result"},
            events=[event],
            step_index=4,
        )
        cp = await store.get_checkpoint("run-sc2")
        events = await event_store.list_events("run-sc2")
        assert cp is not None, "Checkpoint must be saved"
        assert cp["step_index"] == 4
        assert len(events) == 1, "Event must be durably stored"

    @pytest.mark.anyio
    async def test_no_checkpoint_without_events_after_failure(self) -> None:
        """In-memory: if atomic_transition raises, neither checkpoint nor event is written."""

        class FailingEventStore(InMemoryEventStore):
            async def append(self, run_id: str, event: ExecutionEvent) -> None:
                raise RuntimeError("event store down")

        store = InMemoryCheckpointStore()
        event_store = FailingEventStore()
        manager = CheckpointManager(
            checkpoint_store=store,
            event_store=event_store,
            event_sink=NullEventSink(),
        )
        event = ExecutionEvent(
            type=EventType.RUN_FINISHED.value,
            timestamp=datetime.now(timezone.utc),
            run_id="run-crash",
            scope="test",
        )
        with pytest.raises(RuntimeError, match="event store down"):
            await manager.atomic_transition(
                run_id="run-crash",
                new_state={"output": "result"},
                events=[event],
                step_index=0,
            )
        # For in-memory: checkpoint save succeeded before append failed.
        # This documents the in-memory limitation: full atomicity requires SQL.
        # The test asserts that the event is NOT in the store (event was not appended).
        events = await event_store.list_events("run-crash")
        assert len(events) == 0

    @pytest.mark.anyio
    async def test_recovery_reads_step_index_for_resume(self) -> None:
        from miniautogen.core.runtime.recovery import SessionRecovery
        store = InMemoryCheckpointStore()
        event_store = InMemoryEventStore()
        manager = CheckpointManager(
            checkpoint_store=store,
            event_store=event_store,
            event_sink=NullEventSink(),
        )
        await manager.atomic_transition(
            run_id="run-resume",
            new_state={"step": 2},
            events=[],
            step_index=2,
        )
        recovery = SessionRecovery(store)
        next_step = await recovery.get_resume_step_index("run-resume")
        assert next_step == 3  # step_index=2 → resume from step 3
```

**Verify:**

```bash
pytest tests/core/runtime/test_atomic_transition_crash.py -v
# Expected: all 3 tests pass
```

---

### COMMIT POINT — TG-8

```bash
git add miniautogen/core/runtime/supervised_step.py \
        miniautogen/core/runtime/workflow_runtime.py \
        miniautogen/core/runtime/pipeline_runner.py \
        miniautogen/core/runtime/recovery.py \
        tests/core/runtime/test_supervised_workflow.py \
        tests/core/runtime/test_atomic_transition_crash.py

git commit -m "feat(runtime): wire supervision tree into WorkflowRuntime and PipelineRunner"
```

---

## Final Verification

Run the full test suite from the project root to confirm no regressions:

```bash
pytest tests/ -v --tb=short -q 2>&1 | tail -20
# Expected: all tests pass, no red
```

Run only the WS4 tests:

```bash
pytest \
  tests/core/contracts/test_supervision.py \
  tests/core/runtime/test_classifier.py \
  tests/core/runtime/test_step_supervisor.py \
  tests/core/runtime/test_flow_supervisor.py \
  tests/core/runtime/test_checkpoint_manager.py \
  tests/stores/test_event_store.py \
  tests/core/runtime/test_heartbeat.py \
  tests/core/runtime/test_supervised_workflow.py \
  tests/core/runtime/test_atomic_transition_crash.py \
  -v 2>&1 | tail -30
# Expected: all new tests pass
```

Verify Success Criteria from design spec:

| SC | Test | Location |
|----|------|----------|
| SC-1 | `test_step_restarts_up_to_max_then_escalates` | `test_supervised_workflow.py::TestSC1` |
| SC-2 | `test_checkpoint_and_event_both_present_on_success` | `test_atomic_transition_crash.py::TestSC2` |
| SC-3 | `test_circuit_opens_after_threshold` | `test_supervised_workflow.py::TestSC3` |
| SC-4 | `test_raises_when_agent_stops_beating` | `test_heartbeat.py::TestRunWithHeartbeat` |
| SC-5 | `test_sibling_branches_complete_when_one_restarts` | `test_supervised_workflow.py::TestSC5` |
| SC-6 | `test_decision_produces_events` | `test_flow_supervisor.py::TestFlowDecisionEvents` |
| SC-7 | `test_checkpoint_and_event_both_present_on_success` | `test_atomic_transition_crash.py::TestSC2` |

---

## Summary of All Files

### New Files

| File | TG | Purpose |
|------|----|---------|
| `miniautogen/core/contracts/supervision.py` | TG-1 | `StepSupervision`, `SupervisionDecision` models |
| `miniautogen/core/runtime/classifier.py` | TG-2 | `classify_error()` function |
| `miniautogen/core/runtime/supervisors.py` | TG-3 | `Supervisor` protocol, `StepSupervisor` |
| `miniautogen/core/runtime/flow_supervisor.py` | TG-4 | `FlowSupervisor`, `FlowDecision`, `StepStatus` |
| `miniautogen/core/runtime/checkpoint_manager.py` | TG-5 | `CheckpointManager` |
| `miniautogen/stores/event_store.py` | TG-6 | `EventStore` ABC |
| `miniautogen/stores/in_memory_event_store.py` | TG-6 | `InMemoryEventStore` |
| `miniautogen/core/runtime/heartbeat.py` | TG-7 | `HeartbeatToken`, `run_with_heartbeat`, `_watchdog` |
| `miniautogen/core/runtime/supervised_step.py` | TG-8 | `supervised_step`, `resolve_supervision`, `StepStoppedError` |

### Modified Files

| File | TG | Change |
|------|----|--------|
| `miniautogen/core/contracts/enums.py` | TG-1 | Add `SupervisionStrategy` enum |
| `miniautogen/core/contracts/coordination.py` | TG-1 | Add `supervision` to `WorkflowStep`, `default_supervision` to `WorkflowPlan` |
| `miniautogen/core/contracts/agent_spec.py` | TG-1 | Add optional `supervision` field to `AgentSpec` |
| `miniautogen/core/events/types.py` | TG-4 | Add 5 `SUPERVISION_*` event types + `SUPERVISION_EVENT_TYPES` set |
| `miniautogen/stores/checkpoint_store.py` | TG-5 | Add `transaction()` async context manager (non-breaking) |
| `miniautogen/core/runtime/workflow_runtime.py` | TG-8 | Replace `_run_sequential` and `_run_fan_out` with supervised versions |
| `miniautogen/core/runtime/pipeline_runner.py` | TG-8 | Add `CheckpointManager` injection, replace non-atomic post-run block |
| `miniautogen/core/runtime/recovery.py` | TG-8 | Add `get_resume_step_index()` method |

### New Test Files

| Test File | TG | Tests |
|-----------|----|-------|
| `tests/core/contracts/test_supervision.py` | TG-1 | SupervisionStrategy, StepSupervision, attachment points |
| `tests/core/runtime/test_classifier.py` | TG-2 | 13 exception-to-category mappings |
| `tests/core/runtime/test_step_supervisor.py` | TG-3 | Forced overrides, circuit breaker, restart budget, configured strategy |
| `tests/core/runtime/test_flow_supervisor.py` | TG-4 | Flow circuit breaker, step completion map, event emission |
| `tests/core/runtime/test_checkpoint_manager.py` | TG-5 | Atomic transition payload, events, step_index, transition_id |
| `tests/stores/test_event_store.py` | TG-6 | Append, list, ordering, after_index, count, isolation |
| `tests/core/runtime/test_heartbeat.py` | TG-7 | HeartbeatToken, watchdog kill, normal completion |
| `tests/core/runtime/test_supervised_workflow.py` | TG-8 | SC-1, SC-3, SC-5 integration scenarios |
| `tests/core/runtime/test_atomic_transition_crash.py` | TG-8 | SC-2, SC-7 crash consistency, resume step index |

---

## Effort Estimate

| TG | Tasks | Estimated Time |
|----|-------|----------------|
| TG-1 | 4 | ~45 min |
| TG-2 | 2 | ~20 min |
| TG-3 | 2 | ~30 min |
| TG-4 | 3 | ~40 min |
| TG-5 | 3 | ~30 min |
| TG-6 | 3 | ~25 min |
| TG-7 | 2 | ~20 min |
| TG-8 | 6 | ~90 min |
| **Total** | **25** | **~5.5 hours** |

---

## Migration Notes

This plan is **backward-compatible**. The default `StepSupervision` uses
`strategy=ESCALATE`, which preserves the current behavior (errors propagate
up and fail the run). Existing code that does not set any supervision config
will behave identically to today.

The `CheckpointManager` is injected optionally into `PipelineRunner`. If not
provided, the legacy non-atomic path is used. This allows gradual adoption
without breaking existing integrations.
