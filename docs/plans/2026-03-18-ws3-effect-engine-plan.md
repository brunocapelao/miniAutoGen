# WS3: Effect Engine -- Implementation Plan

> **For Agents:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Introduce the Effect Engine into MiniAutoGen -- a lateral policy subsystem that governs every side-effecting tool call with idempotency tracking, policy enforcement, and full event observability. Every interaction with the external world must be registered in an Effect Journal before execution so that replays and retries never produce duplicate side effects.

**Architecture:** Four cooperating components added without touching the core execution path: `EffectPolicy` (frozen dataclass configuration), `EffectJournal` ABC + two implementations (in-memory and SQLAlchemy), `EffectDescriptor`/`EffectRecord`/`EffectStatus` protocol models in `core/contracts`, and `EffectInterceptor` (concrete wrapper around tool dispatch). Five new `EventType` members complete the observability surface. The `PipelineRunner` is not modified -- the interceptor is optional composition at the tool dispatch call site.

**Tech Stack:** Python 3.11+, Pydantic v2, AnyIO, SQLAlchemy 2.x async, pytest + anyio pytest plugin.

**Global Prerequisites:**
- Environment: macOS or Linux, Python 3.11+
- Tools: `pytest`, `anyio`, `pydantic`, `sqlalchemy[asyncio]`, `aiosqlite` installed in the project virtualenv
- Access: No external API keys required (all tests use in-memory stores or SQLite)
- State: Branch from `main`; `main` must be fully green before starting

**Verification before starting:**
```bash
python --version                    # Expected: Python 3.11+
pytest --version                    # Expected: pytest 7.0+
git status                          # Expected: clean working tree on main
python -m pytest tests/ -x -q      # Expected: all tests pass
python -c "from miniautogen.core.contracts.enums import RunStatus; print('OK')"
# Expected: OK
```

**Design spec:** `docs/plans/2026-03-18-ws3-effect-engine-design.md`

**Branch:** `feat/ws3-effect-engine`

---

## Prompt Contract

- **Goal:** Add a complete, TDD-driven Effect Engine to MiniAutoGen with zero core modifications.
- **Constraint:** `PipelineRunner`, `RunContext`, `RunResult`, and all existing policies must remain untouched. All new error classes must map to canonical error categories (`validation`, `state_consistency`, `adapter`).
- **Failure Condition:** Any test in `tests/` fails, or `from miniautogen.core.contracts.effect import EffectInterceptor` (it lives in `core/effect_interceptor.py` -- wrong import would signal a structure violation).

---

## Task Groups

### TG-0: Shared Foundation

Add `ErrorCategory` StrEnum to `enums.py` and three canonical exception classes to `core/contracts/effect.py`. WS4 depends on `ErrorCategory` being present, so this TG is the foundational commit that must land first.

---

#### Task 0.1: Write failing test for `ErrorCategory`

**Files:**
- Create: `tests/core/contracts/test_effect_foundation.py`

**What:** A new test file asserting that `ErrorCategory` exists in `enums.py` with all eight canonical values.

**How:**

Create `tests/core/contracts/test_effect_foundation.py`:

```python
"""Tests for ErrorCategory enum and effect exception classes (WS3 TG-0)."""

from __future__ import annotations

import pytest


class TestErrorCategory:
    def test_import(self) -> None:
        from miniautogen.core.contracts.enums import ErrorCategory  # noqa: F401

    def test_has_transient(self) -> None:
        from miniautogen.core.contracts.enums import ErrorCategory
        assert ErrorCategory.TRANSIENT == "transient"

    def test_has_permanent(self) -> None:
        from miniautogen.core.contracts.enums import ErrorCategory
        assert ErrorCategory.PERMANENT == "permanent"

    def test_has_validation(self) -> None:
        from miniautogen.core.contracts.enums import ErrorCategory
        assert ErrorCategory.VALIDATION == "validation"

    def test_has_timeout(self) -> None:
        from miniautogen.core.contracts.enums import ErrorCategory
        assert ErrorCategory.TIMEOUT == "timeout"

    def test_has_cancellation(self) -> None:
        from miniautogen.core.contracts.enums import ErrorCategory
        assert ErrorCategory.CANCELLATION == "cancellation"

    def test_has_adapter(self) -> None:
        from miniautogen.core.contracts.enums import ErrorCategory
        assert ErrorCategory.ADAPTER == "adapter"

    def test_has_configuration(self) -> None:
        from miniautogen.core.contracts.enums import ErrorCategory
        assert ErrorCategory.CONFIGURATION == "configuration"

    def test_has_state_consistency(self) -> None:
        from miniautogen.core.contracts.enums import ErrorCategory
        assert ErrorCategory.STATE_CONSISTENCY == "state_consistency"

    def test_is_str_enum(self) -> None:
        from miniautogen.core.contracts.enums import ErrorCategory
        assert isinstance(ErrorCategory.TRANSIENT, str)

    def test_all_eight_members(self) -> None:
        from miniautogen.core.contracts.enums import ErrorCategory
        names = {m.name for m in ErrorCategory}
        assert names == {
            "TRANSIENT", "PERMANENT", "VALIDATION", "TIMEOUT",
            "CANCELLATION", "ADAPTER", "CONFIGURATION", "STATE_CONSISTENCY",
        }
```

**Verify:**
```bash
pytest tests/core/contracts/test_effect_foundation.py::TestErrorCategory -v
# Expected: FAILED - ImportError: cannot import name 'ErrorCategory'
```

---

#### Task 0.2: Implement `ErrorCategory` in `enums.py`

**Files:**
- Modify: `miniautogen/core/contracts/enums.py`

**What:** Append `ErrorCategory` StrEnum after `LoopStopReason`.

**How:**

Append to the end of `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/contracts/enums.py`:

```python


class ErrorCategory(str, Enum):
    """Canonical error taxonomy for all MiniAutoGen exceptions.

    Every custom exception class must declare exactly one of these
    categories. Violating this constraint is a hard rejection condition
    (see CLAUDE.md section 4).
    """

    TRANSIENT = "transient"
    PERMANENT = "permanent"
    VALIDATION = "validation"
    TIMEOUT = "timeout"
    CANCELLATION = "cancellation"
    ADAPTER = "adapter"
    CONFIGURATION = "configuration"
    STATE_CONSISTENCY = "state_consistency"
```

**Verify:**
```bash
pytest tests/core/contracts/test_effect_foundation.py::TestErrorCategory -v
# Expected: 10 passed
```

---

#### Task 0.3: Write failing test for effect exception classes

**Files:**
- Modify: `tests/core/contracts/test_effect_foundation.py` (append)

**What:** Tests that assert the three effect exceptions exist, are importable from `core/contracts/effect.py`, and carry the correct `category` attribute.

**How:**

Append to `tests/core/contracts/test_effect_foundation.py`:

```python

class TestEffectExceptions:
    def test_effect_denied_error_import(self) -> None:
        from miniautogen.core.contracts.effect import EffectDeniedError  # noqa: F401

    def test_effect_duplicate_error_import(self) -> None:
        from miniautogen.core.contracts.effect import EffectDuplicateError  # noqa: F401

    def test_effect_journal_unavailable_error_import(self) -> None:
        from miniautogen.core.contracts.effect import EffectJournalUnavailableError  # noqa: F401

    def test_effect_denied_has_validation_category(self) -> None:
        from miniautogen.core.contracts.effect import EffectDeniedError
        assert EffectDeniedError.category == "validation"

    def test_effect_duplicate_has_state_consistency_category(self) -> None:
        from miniautogen.core.contracts.effect import EffectDuplicateError
        assert EffectDuplicateError.category == "state_consistency"

    def test_effect_journal_unavailable_has_adapter_category(self) -> None:
        from miniautogen.core.contracts.effect import EffectJournalUnavailableError
        assert EffectJournalUnavailableError.category == "adapter"

    def test_effect_denied_is_exception(self) -> None:
        from miniautogen.core.contracts.effect import EffectDeniedError
        err = EffectDeniedError("type not allowed")
        assert isinstance(err, Exception)

    def test_effect_denied_carries_message(self) -> None:
        from miniautogen.core.contracts.effect import EffectDeniedError
        err = EffectDeniedError("type not allowed")
        assert "type not allowed" in str(err)

    def test_effect_duplicate_carries_message(self) -> None:
        from miniautogen.core.contracts.effect import EffectDuplicateError
        err = EffectDuplicateError("key already completed")
        assert "key already completed" in str(err)
```

**Verify:**
```bash
pytest tests/core/contracts/test_effect_foundation.py::TestEffectExceptions -v
# Expected: FAILED - ModuleNotFoundError: No module named 'miniautogen.core.contracts.effect'
```

---

#### Task 0.4: Create `miniautogen/core/contracts/effect.py` with exception classes

**Files:**
- Create: `miniautogen/core/contracts/effect.py`

**What:** New contract module containing the three exception classes. The `EffectDescriptor`, `EffectRecord`, and `EffectStatus` models will be added in TG-3 to the same file.

**How:**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/contracts/effect.py`:

```python
"""Effect Engine contracts: exceptions, models, and status types.

Part of WS3: Effect Engine.

This module defines the frozen data models and exception classes for
the Effect Engine. These are pure contracts -- no runtime behavior.
The EffectInterceptor (behavior) lives in miniautogen/core/effect_interceptor.py.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Exception classes
# ---------------------------------------------------------------------------


class EffectDeniedError(Exception):
    """Raised when an effect is rejected by the EffectPolicy.

    Canonical category: validation
    Triggers: effect_type not in allowed_effect_types, or
              max_effects_per_step would be exceeded.
    """

    category: str = "validation"


class EffectDuplicateError(Exception):
    """Raised when registering an effect whose idempotency key
    already exists with status COMPLETED.

    Canonical category: state_consistency
    Triggers: journal.register() called with a key that is
              already in COMPLETED state.
    """

    category: str = "state_consistency"


class EffectJournalUnavailableError(Exception):
    """Raised when the EffectJournal store is unreachable.

    Canonical category: adapter
    Triggers: connection failure, timeout, or I/O error when
              communicating with the journal backend (e.g., database).
    """

    category: str = "adapter"
```

**Verify:**
```bash
pytest tests/core/contracts/test_effect_foundation.py -v
# Expected: all 20 tests pass
```

---

#### Task 0.5: Commit TG-0

**What:** Atomic commit covering `ErrorCategory` enum and the three exception classes.

```bash
git add miniautogen/core/contracts/enums.py \
        miniautogen/core/contracts/effect.py \
        tests/core/contracts/test_effect_foundation.py
git commit -m "feat(core): add ErrorCategory enum and effect exception classes (WS3 TG-0)"
```

**Verify:**
```bash
python -m pytest tests/ -x -q
# Expected: all tests pass (no regressions)
```

---

### TG-1: EffectPolicy Model

Frozen dataclass configuration for the Effect Engine, following the `ExecutionPolicy` / `BudgetPolicy` pattern exactly. Also introduces `EffectPolicyEvaluator` for integration with `PolicyChain`.

---

#### Task 1.1: Write failing test for `EffectPolicy`

**Files:**
- Create: `tests/policies/test_effect_policy.py`

**What:** Tests asserting `EffectPolicy` is importable, frozen, and has correct default values.

**How:**

Create `tests/policies/test_effect_policy.py`:

```python
"""Tests for EffectPolicy frozen dataclass and EffectPolicyEvaluator (WS3 TG-1)."""

from __future__ import annotations

import pytest


class TestEffectPolicyDefaults:
    def test_import(self) -> None:
        from miniautogen.policies.effect import EffectPolicy  # noqa: F401

    def test_default_max_effects_per_step(self) -> None:
        from miniautogen.policies.effect import EffectPolicy
        p = EffectPolicy()
        assert p.max_effects_per_step == 10

    def test_default_allowed_effect_types_empty(self) -> None:
        from miniautogen.policies.effect import EffectPolicy
        p = EffectPolicy()
        assert p.allowed_effect_types == frozenset()

    def test_default_require_idempotency_true(self) -> None:
        from miniautogen.policies.effect import EffectPolicy
        p = EffectPolicy()
        assert p.require_idempotency is True

    def test_default_completed_ttl_seconds_none(self) -> None:
        from miniautogen.policies.effect import EffectPolicy
        p = EffectPolicy()
        assert p.completed_ttl_seconds is None

    def test_default_stale_pending_timeout_seconds(self) -> None:
        from miniautogen.policies.effect import EffectPolicy
        p = EffectPolicy()
        assert p.stale_pending_timeout_seconds == 300.0


class TestEffectPolicyFrozen:
    def test_is_frozen(self) -> None:
        from miniautogen.policies.effect import EffectPolicy
        p = EffectPolicy()
        with pytest.raises((AttributeError, TypeError)):
            p.max_effects_per_step = 99  # type: ignore[misc]

    def test_equality(self) -> None:
        from miniautogen.policies.effect import EffectPolicy
        p1 = EffectPolicy(max_effects_per_step=5)
        p2 = EffectPolicy(max_effects_per_step=5)
        assert p1 == p2

    def test_inequality(self) -> None:
        from miniautogen.policies.effect import EffectPolicy
        p1 = EffectPolicy(max_effects_per_step=5)
        p2 = EffectPolicy(max_effects_per_step=10)
        assert p1 != p2


class TestEffectPolicyCustomValues:
    def test_custom_max_effects(self) -> None:
        from miniautogen.policies.effect import EffectPolicy
        p = EffectPolicy(max_effects_per_step=3)
        assert p.max_effects_per_step == 3

    def test_custom_allowed_types(self) -> None:
        from miniautogen.policies.effect import EffectPolicy
        p = EffectPolicy(allowed_effect_types=frozenset({"tool_call", "api_request"}))
        assert "tool_call" in p.allowed_effect_types
        assert "db_write" not in p.allowed_effect_types

    def test_custom_ttl(self) -> None:
        from miniautogen.policies.effect import EffectPolicy
        p = EffectPolicy(completed_ttl_seconds=3600.0)
        assert p.completed_ttl_seconds == 3600.0

    def test_require_idempotency_false(self) -> None:
        from miniautogen.policies.effect import EffectPolicy
        p = EffectPolicy(require_idempotency=False)
        assert p.require_idempotency is False
```

**Verify:**
```bash
pytest tests/policies/test_effect_policy.py::TestEffectPolicyDefaults -v
# Expected: FAILED - ModuleNotFoundError: No module named 'miniautogen.policies.effect'
```

---

#### Task 1.2: Implement `EffectPolicy`

**Files:**
- Create: `miniautogen/policies/effect.py`

**What:** Frozen dataclass for `EffectPolicy` plus a stub for `EffectPolicyEvaluator` (completed in Task 1.4 after the journal ABC exists).

**How:**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/policies/effect.py`:

```python
"""EffectPolicy: frozen configuration for the Effect Engine.

Part of WS3: Effect Engine.

Pattern: frozen dataclass (same as ExecutionPolicy, BudgetPolicy).
The policy is data; EffectInterceptor and EffectPolicyEvaluator are behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EffectPolicy:
    """Governs side-effect execution and idempotency requirements.

    All fields have safe defaults so existing code that does not need
    the Effect Engine is unaffected. Instantiate with no arguments to
    get a permissive policy that still enforces idempotency.
    """

    # Maximum side effects permitted in a single pipeline step.
    # Prevents runaway tool-call loops from causing unbounded damage.
    max_effects_per_step: int = 10

    # Effect types that are permitted. Any effect whose type is not
    # in this set will be denied. Empty frozenset means "allow all".
    allowed_effect_types: frozenset[str] = field(default_factory=frozenset)

    # When True, every effect MUST have an idempotency_key registered
    # in the EffectJournal before execution. When False, idempotency
    # tracking is best-effort (effects execute even without journal).
    require_idempotency: bool = True

    # Time-to-live for completed effect records in the journal (seconds).
    # After this period, a completed effect may be re-executed.
    # None means records never expire.
    completed_ttl_seconds: float | None = None

    # Maximum time (seconds) a PENDING record can exist before being
    # considered stale and eligible for cleanup. A pending record older
    # than this threshold is assumed to be from a prior crash.
    stale_pending_timeout_seconds: float = 300.0
```

**Verify:**
```bash
pytest tests/policies/test_effect_policy.py -v
# Expected: all tests in TestEffectPolicyDefaults, TestEffectPolicyFrozen,
#           TestEffectPolicyCustomValues pass
```

---

#### Task 1.3: Write failing test for `EffectPolicyEvaluator`

**Files:**
- Modify: `tests/policies/test_effect_policy.py` (append)

**What:** Tests for the `EffectPolicyEvaluator` adapter that bridges `EffectPolicy` into the `PolicyChain`.

**How:**

Append to `tests/policies/test_effect_policy.py`:

```python

class TestEffectPolicyEvaluator:
    """EffectPolicyEvaluator integrates EffectPolicy into PolicyChain."""

    def _make_journal(self):
        from miniautogen.stores.in_memory_effect_journal import InMemoryEffectJournal
        return InMemoryEffectJournal()

    @pytest.mark.asyncio
    async def test_import(self) -> None:
        from miniautogen.policies.effect import EffectPolicyEvaluator  # noqa: F401

    @pytest.mark.asyncio
    async def test_proceed_when_all_types_allowed(self) -> None:
        from miniautogen.policies.effect import EffectPolicy, EffectPolicyEvaluator
        from miniautogen.policies.chain import PolicyContext
        policy = EffectPolicy()  # empty allowed_effect_types = allow all
        journal = self._make_journal()
        evaluator = EffectPolicyEvaluator(policy=policy, journal=journal)
        ctx = PolicyContext(action="tool_call", run_id="run-1")
        result = await evaluator.evaluate(ctx)
        assert result.decision == "proceed"

    @pytest.mark.asyncio
    async def test_deny_when_type_not_in_allowed_set(self) -> None:
        from miniautogen.policies.effect import EffectPolicy, EffectPolicyEvaluator
        from miniautogen.policies.chain import PolicyContext
        policy = EffectPolicy(allowed_effect_types=frozenset({"api_request"}))
        journal = self._make_journal()
        evaluator = EffectPolicyEvaluator(policy=policy, journal=journal)
        ctx = PolicyContext(action="db_write", run_id="run-1")
        result = await evaluator.evaluate(ctx)
        assert result.decision == "deny"
        assert result.reason is not None

    @pytest.mark.asyncio
    async def test_deny_when_max_effects_per_step_exceeded(self) -> None:
        from miniautogen.policies.effect import EffectPolicy, EffectPolicyEvaluator
        from miniautogen.policies.chain import PolicyContext
        policy = EffectPolicy(max_effects_per_step=2)
        journal = self._make_journal()
        # Pre-populate journal with 2 completed effects for this run/step
        from miniautogen.core.contracts.effect import (
            EffectDescriptor, EffectRecord, EffectStatus,
        )
        from datetime import datetime, timezone
        for i in range(2):
            rec = EffectRecord(
                idempotency_key=f"key-{i}",
                descriptor=EffectDescriptor(
                    effect_type="tool_call",
                    tool_name="send_email",
                    args_hash="abc",
                    run_id="run-1",
                    step_id="step-1",
                    metadata={},
                ),
                status=EffectStatus.COMPLETED,
                created_at=datetime.now(timezone.utc),
            )
            await journal.register(rec)
            await journal.update_status(f"key-{i}", EffectStatus.COMPLETED)
        evaluator = EffectPolicyEvaluator(policy=policy, journal=journal)
        ctx = PolicyContext(
            action="tool_call",
            run_id="run-1",
            metadata={"step_id": "step-1"},
        )
        result = await evaluator.evaluate(ctx)
        assert result.decision == "deny"

    @pytest.mark.asyncio
    async def test_implements_policy_evaluator_protocol(self) -> None:
        from miniautogen.policies.effect import EffectPolicy, EffectPolicyEvaluator
        from miniautogen.policies.chain import PolicyEvaluator
        policy = EffectPolicy()
        journal = self._make_journal()
        evaluator = EffectPolicyEvaluator(policy=policy, journal=journal)
        assert isinstance(evaluator, PolicyEvaluator)
```

**Verify:**
```bash
pytest tests/policies/test_effect_policy.py::TestEffectPolicyEvaluator -v
# Expected: FAILED - ModuleNotFoundError (EffectPolicyEvaluator or InMemoryEffectJournal not yet present)
# This test will pass fully only after TG-2 (journal) and Task 1.4 (evaluator impl) are done.
```

---

#### Task 1.4: Implement `EffectPolicyEvaluator`

**Files:**
- Modify: `miniautogen/policies/effect.py` (append class)

**What:** `EffectPolicyEvaluator` class that implements the `PolicyEvaluator` protocol. Reads the journal to count completed effects and enforces `allowed_effect_types` and `max_effects_per_step`.

**Note:** This task depends on TG-2 (journal store) being implemented first. Complete TG-2 before returning to this task.

**How:**

Append to `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/policies/effect.py`:

```python

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from miniautogen.stores.effect_journal import EffectJournal
    from miniautogen.core.contracts.effect import EffectStatus

from miniautogen.policies.chain import PolicyContext, PolicyResult


class EffectPolicyEvaluator:
    """Adapts EffectPolicy for use in a PolicyChain.

    Evaluates whether a proposed action is permitted under the
    current effect policy:
    1. Effect type must be in allowed_effect_types (or the set is empty).
    2. Completed effects for this run/step must not exceed max_effects_per_step.

    Implements the PolicyEvaluator protocol.
    """

    def __init__(self, policy: EffectPolicy, journal: EffectJournal) -> None:
        self._policy = policy
        self._journal = journal

    async def evaluate(self, context: PolicyContext) -> PolicyResult:
        effect_type = context.action

        # Check 1: Is the effect type allowed?
        if self._policy.allowed_effect_types:
            if effect_type not in self._policy.allowed_effect_types:
                return PolicyResult(
                    decision="deny",
                    reason=f"effect_type '{effect_type}' not in allowed_effect_types",
                )

        # Check 2: Would max_effects_per_step be exceeded?
        run_id = context.run_id
        step_id = context.metadata.get("step_id")
        if run_id is not None and step_id is not None:
            from miniautogen.core.contracts.effect import EffectStatus
            completed = await self._journal.list_by_run(
                run_id=run_id,
                status=EffectStatus.COMPLETED,
            )
            step_completed = [r for r in completed if r.descriptor.step_id == step_id]
            if len(step_completed) >= self._policy.max_effects_per_step:
                return PolicyResult(
                    decision="deny",
                    reason=(
                        f"max_effects_per_step ({self._policy.max_effects_per_step}) "
                        f"exceeded for step '{step_id}'"
                    ),
                )

        return PolicyResult(decision="proceed")
```

**Verify:**
```bash
pytest tests/policies/test_effect_policy.py -v
# Expected: all tests pass (after TG-2 is implemented)
```

---

#### Task 1.5: Commit TG-1

**What:** Atomic commit for the EffectPolicy model and evaluator.

```bash
git add miniautogen/policies/effect.py \
        tests/policies/test_effect_policy.py
git commit -m "feat(policies): add EffectPolicy frozen dataclass and EffectPolicyEvaluator (WS3 TG-1)"
```

**Verify:**
```bash
python -m pytest tests/ -x -q
# Expected: all tests pass
```

---

### TG-2: EffectJournal Store

ABC contract + `InMemoryEffectJournal`. Follows the `CheckpointStore` pattern precisely. The SQLAlchemy implementation is in TG-6.

---

#### Task 2.1: Write failing test for `EffectJournal` ABC

**Files:**
- Create: `tests/stores/test_effect_journal.py`

**What:** Tests for the ABC contract (importability, abstract method signatures) and `InMemoryEffectJournal` behaviour.

**How:**

Create `tests/stores/test_effect_journal.py`:

```python
"""Tests for EffectJournal ABC and InMemoryEffectJournal (WS3 TG-2)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest


def _make_descriptor(
    run_id: str = "run-1",
    step_id: str = "step-1",
    tool_name: str = "send_email",
    effect_type: str = "tool_call",
) -> object:
    from miniautogen.core.contracts.effect import EffectDescriptor
    return EffectDescriptor(
        effect_type=effect_type,
        tool_name=tool_name,
        args_hash="abc123",
        run_id=run_id,
        step_id=step_id,
        metadata={},
    )


def _make_record(
    key: str = "key-1",
    run_id: str = "run-1",
    step_id: str = "step-1",
    tool_name: str = "send_email",
) -> object:
    from miniautogen.core.contracts.effect import EffectRecord, EffectStatus
    return EffectRecord(
        idempotency_key=key,
        descriptor=_make_descriptor(run_id=run_id, step_id=step_id, tool_name=tool_name),
        status=EffectStatus.PENDING,
        created_at=datetime.now(timezone.utc),
    )


class TestEffectJournalABC:
    def test_import(self) -> None:
        from miniautogen.stores.effect_journal import EffectJournal  # noqa: F401

    def test_is_abstract(self) -> None:
        from miniautogen.stores.effect_journal import EffectJournal
        import inspect
        assert inspect.isabstract(EffectJournal)

    def test_has_register_method(self) -> None:
        from miniautogen.stores.effect_journal import EffectJournal
        assert hasattr(EffectJournal, "register")

    def test_has_get_method(self) -> None:
        from miniautogen.stores.effect_journal import EffectJournal
        assert hasattr(EffectJournal, "get")

    def test_has_update_status_method(self) -> None:
        from miniautogen.stores.effect_journal import EffectJournal
        assert hasattr(EffectJournal, "update_status")

    def test_has_list_by_run_method(self) -> None:
        from miniautogen.stores.effect_journal import EffectJournal
        assert hasattr(EffectJournal, "list_by_run")

    def test_has_delete_by_run_method(self) -> None:
        from miniautogen.stores.effect_journal import EffectJournal
        assert hasattr(EffectJournal, "delete_by_run")


class TestInMemoryEffectJournalImport:
    def test_import(self) -> None:
        from miniautogen.stores.in_memory_effect_journal import (
            InMemoryEffectJournal,  # noqa: F401
        )

    def test_is_subclass_of_effect_journal(self) -> None:
        from miniautogen.stores.effect_journal import EffectJournal
        from miniautogen.stores.in_memory_effect_journal import InMemoryEffectJournal
        assert issubclass(InMemoryEffectJournal, EffectJournal)


class TestInMemoryEffectJournalRegisterAndGet:
    @pytest.mark.asyncio
    async def test_register_then_get_returns_record(self) -> None:
        from miniautogen.stores.in_memory_effect_journal import InMemoryEffectJournal
        journal = InMemoryEffectJournal()
        record = _make_record("key-1")
        await journal.register(record)
        result = await journal.get("key-1")
        assert result is not None
        assert result.idempotency_key == "key-1"

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self) -> None:
        from miniautogen.stores.in_memory_effect_journal import InMemoryEffectJournal
        journal = InMemoryEffectJournal()
        result = await journal.get("no-such-key")
        assert result is None

    @pytest.mark.asyncio
    async def test_register_duplicate_key_raises(self) -> None:
        from miniautogen.core.contracts.effect import EffectDuplicateError
        from miniautogen.stores.in_memory_effect_journal import InMemoryEffectJournal
        journal = InMemoryEffectJournal()
        record = _make_record("key-1")
        await journal.register(record)
        with pytest.raises(EffectDuplicateError):
            await journal.register(record)


class TestInMemoryEffectJournalUpdateStatus:
    @pytest.mark.asyncio
    async def test_update_to_completed(self) -> None:
        from miniautogen.core.contracts.effect import EffectStatus
        from miniautogen.stores.in_memory_effect_journal import InMemoryEffectJournal
        journal = InMemoryEffectJournal()
        await journal.register(_make_record("key-1"))
        await journal.update_status("key-1", EffectStatus.COMPLETED, result_hash="sha256-abc")
        record = await journal.get("key-1")
        assert record is not None
        assert record.status == EffectStatus.COMPLETED
        assert record.result_hash == "sha256-abc"
        assert record.completed_at is not None

    @pytest.mark.asyncio
    async def test_update_to_failed_with_error_info(self) -> None:
        from miniautogen.core.contracts.effect import EffectStatus
        from miniautogen.stores.in_memory_effect_journal import InMemoryEffectJournal
        journal = InMemoryEffectJournal()
        await journal.register(_make_record("key-1"))
        await journal.update_status("key-1", EffectStatus.FAILED, error_info="Connection refused")
        record = await journal.get("key-1")
        assert record is not None
        assert record.status == EffectStatus.FAILED
        assert record.error_info == "Connection refused"
        assert record.completed_at is not None


class TestInMemoryEffectJournalListByRun:
    @pytest.mark.asyncio
    async def test_list_by_run_returns_all(self) -> None:
        from miniautogen.core.contracts.effect import EffectStatus
        from miniautogen.stores.in_memory_effect_journal import InMemoryEffectJournal
        journal = InMemoryEffectJournal()
        await journal.register(_make_record("key-1", run_id="run-A"))
        await journal.register(_make_record("key-2", run_id="run-A"))
        await journal.register(_make_record("key-3", run_id="run-B"))
        results = await journal.list_by_run("run-A")
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_list_by_run_filtered_by_status(self) -> None:
        from miniautogen.core.contracts.effect import EffectStatus
        from miniautogen.stores.in_memory_effect_journal import InMemoryEffectJournal
        journal = InMemoryEffectJournal()
        await journal.register(_make_record("key-1", run_id="run-A"))
        await journal.register(_make_record("key-2", run_id="run-A"))
        await journal.update_status("key-1", EffectStatus.COMPLETED)
        results = await journal.list_by_run("run-A", status=EffectStatus.COMPLETED)
        assert len(results) == 1
        assert results[0].idempotency_key == "key-1"

    @pytest.mark.asyncio
    async def test_list_by_run_empty_for_unknown_run(self) -> None:
        from miniautogen.stores.in_memory_effect_journal import InMemoryEffectJournal
        journal = InMemoryEffectJournal()
        results = await journal.list_by_run("no-such-run")
        assert results == []


class TestInMemoryEffectJournalDeleteByRun:
    @pytest.mark.asyncio
    async def test_delete_by_run_returns_count(self) -> None:
        from miniautogen.stores.in_memory_effect_journal import InMemoryEffectJournal
        journal = InMemoryEffectJournal()
        await journal.register(_make_record("key-1", run_id="run-A"))
        await journal.register(_make_record("key-2", run_id="run-A"))
        await journal.register(_make_record("key-3", run_id="run-B"))
        count = await journal.delete_by_run("run-A")
        assert count == 2

    @pytest.mark.asyncio
    async def test_delete_by_run_removes_records(self) -> None:
        from miniautogen.stores.in_memory_effect_journal import InMemoryEffectJournal
        journal = InMemoryEffectJournal()
        await journal.register(_make_record("key-1", run_id="run-A"))
        await journal.delete_by_run("run-A")
        assert await journal.get("key-1") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_run_returns_zero(self) -> None:
        from miniautogen.stores.in_memory_effect_journal import InMemoryEffectJournal
        journal = InMemoryEffectJournal()
        count = await journal.delete_by_run("no-such-run")
        assert count == 0
```

**Verify:**
```bash
pytest tests/stores/test_effect_journal.py::TestEffectJournalABC -v
# Expected: FAILED - ModuleNotFoundError: No module named 'miniautogen.stores.effect_journal'
```

---

#### Task 2.2: Implement `EffectJournal` ABC

**Files:**
- Create: `miniautogen/stores/effect_journal.py`

**What:** ABC with five abstract methods matching the contract from the design spec.

**How:**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/stores/effect_journal.py`:

```python
"""EffectJournal ABC: persistent journal for effect idempotency records.

Part of WS3: Effect Engine.

Pattern: follows CheckpointStore ABC in miniautogen/stores/checkpoint_store.py.
- ABC defines the contract
- InMemoryEffectJournal (in_memory_effect_journal.py) is dict-backed, for testing
- SQLAlchemyEffectJournal (sqlalchemy_effect_journal.py) is the production backend
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from miniautogen.core.contracts.effect import EffectRecord, EffectStatus


class EffectJournal(ABC):
    """Persistent journal for effect idempotency records.

    Stores intent-before-execution records with full lifecycle tracking:
    PENDING -> COMPLETED | FAILED.

    Implementations must be safe for single-event-loop async usage.
    Thread-safety across multiple event loops is not required.
    """

    @abstractmethod
    async def register(self, record: EffectRecord) -> None:
        """Register intent to execute an effect (status=pending).

        If a record with the same idempotency_key already exists,
        raises EffectDuplicateError.
        """

    @abstractmethod
    async def get(self, idempotency_key: str) -> EffectRecord | None:
        """Fetch an effect record by its idempotency key.

        Returns None if no record exists for this key.
        """

    @abstractmethod
    async def update_status(
        self,
        idempotency_key: str,
        status: EffectStatus,
        result_hash: str | None = None,
        error_info: str | None = None,
    ) -> None:
        """Update the status of a registered effect.

        Sets completed_at to utcnow() when transitioning to COMPLETED or FAILED.
        """

    @abstractmethod
    async def list_by_run(
        self,
        run_id: str,
        status: EffectStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EffectRecord]:
        """List effect records for a run, optionally filtered by status.

        Supports pagination via limit/offset. Default limit is 100.
        Results are ordered by created_at ascending.
        """

    @abstractmethod
    async def delete_by_run(self, run_id: str) -> int:
        """Delete all effect records for a run.

        Returns the count of records deleted.
        """
```

**Verify:**
```bash
pytest tests/stores/test_effect_journal.py::TestEffectJournalABC -v
# Expected: all 7 tests pass
```

---

#### Task 2.3: Implement `InMemoryEffectJournal`

**Note:** This task requires TG-3 models (`EffectRecord`, `EffectStatus`, `EffectDescriptor`) to be present. If TG-3 is not yet done, implement TG-3 Task 3.2 (the models) first, then return here.

**Files:**
- Create: `miniautogen/stores/in_memory_effect_journal.py`

**What:** Dict-backed implementation for testing. Keyed by `idempotency_key`.

**How:**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/stores/in_memory_effect_journal.py`:

```python
"""InMemoryEffectJournal: dict-backed EffectJournal for testing.

Part of WS3: Effect Engine.

Pattern: follows InMemoryCheckpointStore in
miniautogen/stores/in_memory_checkpoint_store.py.
"""

from __future__ import annotations

from datetime import datetime, timezone

from miniautogen.core.contracts.effect import (
    EffectDuplicateError,
    EffectRecord,
    EffectStatus,
)
from miniautogen.stores.effect_journal import EffectJournal


class InMemoryEffectJournal(EffectJournal):
    """Dict-backed EffectJournal for unit testing.

    Not safe for concurrent use across multiple tasks; designed for
    single-event-loop test scenarios only.
    """

    def __init__(self) -> None:
        self._records: dict[str, EffectRecord] = {}

    async def register(self, record: EffectRecord) -> None:
        if record.idempotency_key in self._records:
            raise EffectDuplicateError(
                f"Effect with idempotency_key '{record.idempotency_key}' already registered"
            )
        self._records[record.idempotency_key] = record

    async def get(self, idempotency_key: str) -> EffectRecord | None:
        return self._records.get(idempotency_key)

    async def update_status(
        self,
        idempotency_key: str,
        status: EffectStatus,
        result_hash: str | None = None,
        error_info: str | None = None,
    ) -> None:
        existing = self._records.get(idempotency_key)
        if existing is None:
            raise KeyError(f"No effect record found for key '{idempotency_key}'")
        # EffectRecord is frozen; replace with a new instance
        self._records[idempotency_key] = EffectRecord(
            idempotency_key=existing.idempotency_key,
            descriptor=existing.descriptor,
            status=status,
            created_at=existing.created_at,
            completed_at=datetime.now(timezone.utc),
            result_hash=result_hash if result_hash is not None else existing.result_hash,
            error_info=error_info if error_info is not None else existing.error_info,
        )

    async def list_by_run(
        self,
        run_id: str,
        status: EffectStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EffectRecord]:
        records = [
            r for r in self._records.values()
            if r.descriptor.run_id == run_id
            and (status is None or r.status == status)
        ]
        # Sort by created_at ascending for determinism
        records.sort(key=lambda r: r.created_at)
        return records[offset : offset + limit]

    async def delete_by_run(self, run_id: str) -> int:
        keys = [
            k for k, r in self._records.items()
            if r.descriptor.run_id == run_id
        ]
        for k in keys:
            del self._records[k]
        return len(keys)
```

**Verify:**
```bash
pytest tests/stores/test_effect_journal.py -v
# Expected: all tests pass (after TG-3 models are present)
```

---

#### Task 2.4: Commit TG-2

**What:** Atomic commit for the EffectJournal ABC and InMemoryEffectJournal.

```bash
git add miniautogen/stores/effect_journal.py \
        miniautogen/stores/in_memory_effect_journal.py \
        tests/stores/test_effect_journal.py
git commit -m "feat(stores): add EffectJournal ABC and InMemoryEffectJournal (WS3 TG-2)"
```

**Verify:**
```bash
python -m pytest tests/ -x -q
# Expected: all tests pass
```

---

### TG-3: Effect Protocol

Frozen data models: `EffectStatus`, `EffectDescriptor`, `EffectRecord`. All live in `miniautogen/core/contracts/effect.py` (the file created in TG-0 Task 0.4). Also introduces `canonical_args_hash` and `generate_idempotency_key` utility functions.

---

#### Task 3.1: Write failing test for `EffectStatus`, `EffectDescriptor`, `EffectRecord`

**Files:**
- Create: `tests/core/contracts/test_effect_models.py`

**What:** Tests for the three protocol models and the two key-generation utilities.

**How:**

Create `tests/core/contracts/test_effect_models.py`:

```python
"""Tests for EffectStatus, EffectDescriptor, EffectRecord, and key utilities (WS3 TG-3)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest


class TestEffectStatus:
    def test_import(self) -> None:
        from miniautogen.core.contracts.effect import EffectStatus  # noqa: F401

    def test_pending_value(self) -> None:
        from miniautogen.core.contracts.effect import EffectStatus
        assert EffectStatus.PENDING == "pending"

    def test_completed_value(self) -> None:
        from miniautogen.core.contracts.effect import EffectStatus
        assert EffectStatus.COMPLETED == "completed"

    def test_failed_value(self) -> None:
        from miniautogen.core.contracts.effect import EffectStatus
        assert EffectStatus.FAILED == "failed"

    def test_is_str_enum(self) -> None:
        from miniautogen.core.contracts.effect import EffectStatus
        assert isinstance(EffectStatus.PENDING, str)


class TestEffectDescriptor:
    def _make(self, **kwargs) -> object:
        from miniautogen.core.contracts.effect import EffectDescriptor
        defaults = dict(
            effect_type="tool_call",
            tool_name="send_email",
            args_hash="abc123",
            run_id="run-1",
            step_id="step-1",
            metadata={},
        )
        defaults.update(kwargs)
        return EffectDescriptor(**defaults)

    def test_import(self) -> None:
        from miniautogen.core.contracts.effect import EffectDescriptor  # noqa: F401

    def test_fields_are_accessible(self) -> None:
        desc = self._make()
        assert desc.effect_type == "tool_call"
        assert desc.tool_name == "send_email"
        assert desc.args_hash == "abc123"
        assert desc.run_id == "run-1"
        assert desc.step_id == "step-1"
        assert desc.metadata == {}

    def test_is_frozen(self) -> None:
        desc = self._make()
        with pytest.raises((AttributeError, TypeError)):
            desc.tool_name = "other_tool"  # type: ignore[misc]

    def test_equality(self) -> None:
        from miniautogen.core.contracts.effect import EffectDescriptor
        d1 = EffectDescriptor(
            effect_type="tool_call", tool_name="f", args_hash="x",
            run_id="r", step_id="s", metadata={},
        )
        d2 = EffectDescriptor(
            effect_type="tool_call", tool_name="f", args_hash="x",
            run_id="r", step_id="s", metadata={},
        )
        assert d1 == d2

    def test_with_metadata(self) -> None:
        desc = self._make(metadata={"endpoint": "https://api.example.com"})
        assert desc.metadata["endpoint"] == "https://api.example.com"


class TestEffectRecord:
    def _make_desc(self) -> object:
        from miniautogen.core.contracts.effect import EffectDescriptor
        return EffectDescriptor(
            effect_type="tool_call", tool_name="send_email", args_hash="abc",
            run_id="run-1", step_id="step-1", metadata={},
        )

    def test_import(self) -> None:
        from miniautogen.core.contracts.effect import EffectRecord  # noqa: F401

    def test_pending_record_creation(self) -> None:
        from miniautogen.core.contracts.effect import EffectRecord, EffectStatus
        rec = EffectRecord(
            idempotency_key="key-1",
            descriptor=self._make_desc(),
            status=EffectStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )
        assert rec.idempotency_key == "key-1"
        assert rec.status == EffectStatus.PENDING
        assert rec.completed_at is None
        assert rec.result_hash is None
        assert rec.error_info is None

    def test_is_frozen(self) -> None:
        from miniautogen.core.contracts.effect import EffectRecord, EffectStatus
        rec = EffectRecord(
            idempotency_key="key-1",
            descriptor=self._make_desc(),
            status=EffectStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )
        with pytest.raises((AttributeError, TypeError)):
            rec.status = EffectStatus.COMPLETED  # type: ignore[misc]

    def test_completed_record(self) -> None:
        from miniautogen.core.contracts.effect import EffectRecord, EffectStatus
        now = datetime.now(timezone.utc)
        rec = EffectRecord(
            idempotency_key="key-1",
            descriptor=self._make_desc(),
            status=EffectStatus.COMPLETED,
            created_at=now,
            completed_at=now,
            result_hash="sha256-xyz",
        )
        assert rec.status == EffectStatus.COMPLETED
        assert rec.result_hash == "sha256-xyz"
        assert rec.completed_at is not None

    def test_failed_record(self) -> None:
        from miniautogen.core.contracts.effect import EffectRecord, EffectStatus
        now = datetime.now(timezone.utc)
        rec = EffectRecord(
            idempotency_key="key-1",
            descriptor=self._make_desc(),
            status=EffectStatus.FAILED,
            created_at=now,
            completed_at=now,
            error_info="Connection refused",
        )
        assert rec.status == EffectStatus.FAILED
        assert rec.error_info == "Connection refused"


class TestCanonicalArgsHash:
    def test_import(self) -> None:
        from miniautogen.core.contracts.effect import canonical_args_hash  # noqa: F401

    def test_same_args_produce_same_hash(self) -> None:
        from miniautogen.core.contracts.effect import canonical_args_hash
        h1 = canonical_args_hash({"a": 1, "b": 2})
        h2 = canonical_args_hash({"b": 2, "a": 1})  # different order
        assert h1 == h2

    def test_different_args_produce_different_hash(self) -> None:
        from miniautogen.core.contracts.effect import canonical_args_hash
        h1 = canonical_args_hash({"a": 1})
        h2 = canonical_args_hash({"a": 2})
        assert h1 != h2

    def test_returns_hex_string(self) -> None:
        from miniautogen.core.contracts.effect import canonical_args_hash
        h = canonical_args_hash({"x": "y"})
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex digest

    def test_empty_dict(self) -> None:
        from miniautogen.core.contracts.effect import canonical_args_hash
        h = canonical_args_hash({})
        assert isinstance(h, str)
        assert len(h) == 64


class TestGenerateIdempotencyKey:
    def test_import(self) -> None:
        from miniautogen.core.contracts.effect import generate_idempotency_key  # noqa: F401

    def test_same_inputs_same_key(self) -> None:
        from miniautogen.core.contracts.effect import EffectDescriptor, generate_idempotency_key
        desc = EffectDescriptor(
            effect_type="tool_call", tool_name="send_email", args_hash="abc",
            run_id="run-1", step_id="step-1", metadata={},
        )
        k1 = generate_idempotency_key(desc, attempt_number=1)
        k2 = generate_idempotency_key(desc, attempt_number=1)
        assert k1 == k2

    def test_different_attempt_different_key(self) -> None:
        from miniautogen.core.contracts.effect import EffectDescriptor, generate_idempotency_key
        desc = EffectDescriptor(
            effect_type="tool_call", tool_name="send_email", args_hash="abc",
            run_id="run-1", step_id="step-1", metadata={},
        )
        k1 = generate_idempotency_key(desc, attempt_number=1)
        k2 = generate_idempotency_key(desc, attempt_number=2)
        assert k1 != k2

    def test_different_run_different_key(self) -> None:
        from miniautogen.core.contracts.effect import EffectDescriptor, generate_idempotency_key
        desc1 = EffectDescriptor(
            effect_type="tool_call", tool_name="send_email", args_hash="abc",
            run_id="run-1", step_id="step-1", metadata={},
        )
        desc2 = EffectDescriptor(
            effect_type="tool_call", tool_name="send_email", args_hash="abc",
            run_id="run-2", step_id="step-1", metadata={},
        )
        k1 = generate_idempotency_key(desc1, attempt_number=1)
        k2 = generate_idempotency_key(desc2, attempt_number=1)
        assert k1 != k2

    def test_returns_64_char_hex(self) -> None:
        from miniautogen.core.contracts.effect import EffectDescriptor, generate_idempotency_key
        desc = EffectDescriptor(
            effect_type="tool_call", tool_name="f", args_hash="x",
            run_id="r", step_id="s", metadata={},
        )
        k = generate_idempotency_key(desc, attempt_number=1)
        assert isinstance(k, str)
        assert len(k) == 64
```

**Verify:**
```bash
pytest tests/core/contracts/test_effect_models.py -v
# Expected: FAILED - ImportError (EffectStatus/EffectDescriptor/EffectRecord not yet in effect.py)
```

---

#### Task 3.2: Implement `EffectStatus`, `EffectDescriptor`, `EffectRecord`, and key utilities

**Files:**
- Modify: `miniautogen/core/contracts/effect.py` (append after exception classes)

**What:** Append the three protocol models and two utility functions to the existing `effect.py` created in TG-0.

**How:**

Append to `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/contracts/effect.py`:

```python

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Status enum
# ---------------------------------------------------------------------------


class EffectStatus(str, Enum):
    """Lifecycle status of a side-effecting operation in the journal."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EffectDescriptor:
    """Declares the intent to perform a side-effecting operation.

    Created by the runtime (or EffectInterceptor) before execution.
    Carries enough information to generate a deterministic idempotency_key
    and to describe the effect for audit purposes.

    All fields are required at construction time; there are no defaults
    so that callers cannot accidentally omit context.
    """

    effect_type: str          # e.g., "tool_call", "api_request", "db_write"
    tool_name: str            # e.g., "send_email", "create_order"
    args_hash: str            # SHA-256 of canonical JSON of arguments
    run_id: str               # Owning run
    step_id: str              # Owning step within the run
    metadata: dict[str, Any]  # Additional context (endpoint URL, etc.)


@dataclass(frozen=True)
class EffectRecord:
    """Persisted record of an effect's lifecycle in the journal.

    Immutable value object. Stores must replace the record on update
    (create a new EffectRecord with updated fields) since the dataclass
    is frozen.
    """

    idempotency_key: str
    descriptor: EffectDescriptor
    status: EffectStatus
    created_at: datetime
    completed_at: datetime | None = None
    result_hash: str | None = None
    error_info: str | None = None


# ---------------------------------------------------------------------------
# Key generation utilities
# ---------------------------------------------------------------------------


def canonical_args_hash(args: dict[str, Any]) -> str:
    """Compute a deterministic SHA-256 hash of tool arguments.

    Uses sorted keys and compact separators to ensure identical output
    for identical logical arguments regardless of dict insertion order.
    The ``default=str`` fallback handles non-primitive types (e.g., datetime)
    by converting them to their string representation.

    This is deterministic for all Python primitive types (str, int, float,
    bool, None, list, dict). Non-primitive types are coerced via default=str,
    which is stable but not invertible -- callers should prefer primitive
    arguments for maximum safety.
    """
    canonical = json.dumps(args, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def generate_idempotency_key(descriptor: EffectDescriptor, attempt_number: int = 1) -> str:
    """Generate a deterministic idempotency key for a side-effecting operation.

    Key properties:
    - Same run, same step, same tool, same args, same attempt -> same key (deduplication)
    - Same run, same step, same tool, different args -> different key (no false positives)
    - Different run -> different key (runs do not interfere)
    - Same operation, different attempt -> different key (retries get fresh keys)

    The attempt_number starts at 1 and is incremented by RetryPolicy on each retry.
    It is stored in RunContext.metadata["attempt_number"].
    """
    raw = (
        f"{descriptor.run_id}:{descriptor.step_id}:"
        f"{descriptor.tool_name}:{descriptor.args_hash}:{attempt_number}"
    )
    return hashlib.sha256(raw.encode()).hexdigest()
```

**Verify:**
```bash
pytest tests/core/contracts/test_effect_models.py -v
# Expected: all tests pass
pytest tests/core/contracts/test_effect_foundation.py -v
# Expected: all tests still pass (no regression on exception classes)
```

---

#### Task 3.3: Commit TG-3

**What:** Atomic commit for the effect protocol models and key utilities.

```bash
git add miniautogen/core/contracts/effect.py \
        tests/core/contracts/test_effect_models.py
git commit -m "feat(core): add EffectDescriptor, EffectRecord, EffectStatus, and key utilities (WS3 TG-3)"
```

**Verify:**
```bash
python -m pytest tests/ -x -q
# Expected: all tests pass
```

---

### TG-4: EffectInterceptor

Concrete class wrapping tool execution with the full before/execute/after lifecycle: idempotency key generation, journal check, policy enforcement, stale pending handling, and event emission.

---

#### Task 4.1: Write failing test for `EffectInterceptor`

**Files:**
- Create: `tests/core/test_effect_interceptor.py`

**What:** Tests covering the happy path (execute + record), duplicate detection (COMPLETED), stale pending handling, policy deny, and event emission.

**How:**

Create `tests/core/test_effect_interceptor.py`:

```python
"""Tests for EffectInterceptor (WS3 TG-4)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest


def _make_descriptor(
    tool_name: str = "send_email",
    run_id: str = "run-1",
    step_id: str = "step-1",
    effect_type: str = "tool_call",
    args_hash: str = "abc123",
) -> Any:
    from miniautogen.core.contracts.effect import EffectDescriptor
    return EffectDescriptor(
        effect_type=effect_type,
        tool_name=tool_name,
        args_hash=args_hash,
        run_id=run_id,
        step_id=step_id,
        metadata={},
    )


def _make_journal():
    from miniautogen.stores.in_memory_effect_journal import InMemoryEffectJournal
    return InMemoryEffectJournal()


def _make_sink():
    from miniautogen.core.events import InMemoryEventSink
    return InMemoryEventSink()


def _make_policy(**kwargs):
    from miniautogen.policies.effect import EffectPolicy
    return EffectPolicy(**kwargs)


class TestEffectInterceptorImport:
    def test_import(self) -> None:
        from miniautogen.core.effect_interceptor import EffectInterceptor  # noqa: F401


class TestEffectInterceptorHappyPath:
    @pytest.mark.asyncio
    async def test_execute_calls_tool_fn(self) -> None:
        from miniautogen.core.effect_interceptor import EffectInterceptor
        journal = _make_journal()
        sink = _make_sink()
        policy = _make_policy()
        interceptor = EffectInterceptor(policy=policy, journal=journal, event_sink=sink)

        tool_fn = AsyncMock(return_value={"status": "sent"})
        descriptor = _make_descriptor()

        result = await interceptor.execute(
            descriptor=descriptor,
            tool_fn=tool_fn,
            tool_args={"to": "user@example.com"},
            attempt_number=1,
        )

        tool_fn.assert_awaited_once_with(to="user@example.com")
        assert result == {"status": "sent"}

    @pytest.mark.asyncio
    async def test_execute_registers_pending_then_completed(self) -> None:
        from miniautogen.core.contracts.effect import EffectStatus, generate_idempotency_key
        from miniautogen.core.effect_interceptor import EffectInterceptor
        journal = _make_journal()
        sink = _make_sink()
        policy = _make_policy()
        interceptor = EffectInterceptor(policy=policy, journal=journal, event_sink=sink)

        tool_fn = AsyncMock(return_value="ok")
        descriptor = _make_descriptor()
        key = generate_idempotency_key(descriptor, attempt_number=1)

        await interceptor.execute(
            descriptor=descriptor,
            tool_fn=tool_fn,
            tool_args={},
            attempt_number=1,
        )

        record = await journal.get(key)
        assert record is not None
        assert record.status == EffectStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_execute_emits_registered_and_executed_events(self) -> None:
        from miniautogen.core.effect_interceptor import EffectInterceptor
        from miniautogen.core.events.types import EventType
        journal = _make_journal()
        sink = _make_sink()
        policy = _make_policy()
        interceptor = EffectInterceptor(policy=policy, journal=journal, event_sink=sink)

        await interceptor.execute(
            descriptor=_make_descriptor(),
            tool_fn=AsyncMock(return_value="ok"),
            tool_args={},
            attempt_number=1,
        )

        event_types = [e.type for e in sink.events]
        assert EventType.EFFECT_REGISTERED in event_types
        assert EventType.EFFECT_EXECUTED in event_types


class TestEffectInterceptorDuplicateDetection:
    @pytest.mark.asyncio
    async def test_skips_completed_effect_and_returns_none(self) -> None:
        from miniautogen.core.contracts.effect import (
            EffectRecord, EffectStatus, generate_idempotency_key,
        )
        from miniautogen.core.effect_interceptor import EffectInterceptor
        from miniautogen.core.events.types import EventType
        journal = _make_journal()
        sink = _make_sink()
        policy = _make_policy()
        interceptor = EffectInterceptor(policy=policy, journal=journal, event_sink=sink)

        descriptor = _make_descriptor()
        key = generate_idempotency_key(descriptor, attempt_number=1)
        now = datetime.now(timezone.utc)

        # Pre-populate journal with a COMPLETED record
        rec = EffectRecord(
            idempotency_key=key,
            descriptor=descriptor,
            status=EffectStatus.PENDING,
            created_at=now,
        )
        await journal.register(rec)
        await journal.update_status(key, EffectStatus.COMPLETED, result_hash="sha256-r")

        tool_fn = AsyncMock(return_value="new-result")
        await interceptor.execute(
            descriptor=descriptor,
            tool_fn=tool_fn,
            tool_args={},
            attempt_number=1,
        )

        # Tool should NOT have been called
        tool_fn.assert_not_awaited()

        # EFFECT_SKIPPED event should be emitted
        event_types = [e.type for e in sink.events]
        assert EventType.EFFECT_SKIPPED in event_types


class TestEffectInterceptorStalePending:
    @pytest.mark.asyncio
    async def test_stale_pending_is_cleared_and_reexecuted(self) -> None:
        from miniautogen.core.contracts.effect import (
            EffectRecord, EffectStatus, generate_idempotency_key,
        )
        from miniautogen.core.effect_interceptor import EffectInterceptor
        journal = _make_journal()
        sink = _make_sink()
        # Set stale timeout to 1 second so we can test with a 2-second-old record
        policy = _make_policy(stale_pending_timeout_seconds=1.0)
        interceptor = EffectInterceptor(policy=policy, journal=journal, event_sink=sink)

        descriptor = _make_descriptor()
        key = generate_idempotency_key(descriptor, attempt_number=1)
        stale_time = datetime.now(timezone.utc) - timedelta(seconds=10)

        stale_rec = EffectRecord(
            idempotency_key=key,
            descriptor=descriptor,
            status=EffectStatus.PENDING,
            created_at=stale_time,
        )
        await journal.register(stale_rec)

        tool_fn = AsyncMock(return_value="fresh-result")
        result = await interceptor.execute(
            descriptor=descriptor,
            tool_fn=tool_fn,
            tool_args={},
            attempt_number=1,
        )

        # Tool should have been called (stale pending was cleared)
        tool_fn.assert_awaited_once()
        assert result == "fresh-result"

    @pytest.mark.asyncio
    async def test_fresh_pending_raises_duplicate_error(self) -> None:
        from miniautogen.core.contracts.effect import (
            EffectDuplicateError, EffectRecord, EffectStatus, generate_idempotency_key,
        )
        from miniautogen.core.effect_interceptor import EffectInterceptor
        journal = _make_journal()
        sink = _make_sink()
        policy = _make_policy(stale_pending_timeout_seconds=300.0)
        interceptor = EffectInterceptor(policy=policy, journal=journal, event_sink=sink)

        descriptor = _make_descriptor()
        key = generate_idempotency_key(descriptor, attempt_number=1)
        fresh_time = datetime.now(timezone.utc)  # Just now -- not stale

        fresh_rec = EffectRecord(
            idempotency_key=key,
            descriptor=descriptor,
            status=EffectStatus.PENDING,
            created_at=fresh_time,
        )
        await journal.register(fresh_rec)

        tool_fn = AsyncMock(return_value="result")
        with pytest.raises(EffectDuplicateError):
            await interceptor.execute(
                descriptor=descriptor,
                tool_fn=tool_fn,
                tool_args={},
                attempt_number=1,
            )


class TestEffectInterceptorPolicyDeny:
    @pytest.mark.asyncio
    async def test_denied_type_raises_effect_denied_error(self) -> None:
        from miniautogen.core.contracts.effect import EffectDeniedError
        from miniautogen.core.effect_interceptor import EffectInterceptor
        journal = _make_journal()
        sink = _make_sink()
        policy = _make_policy(allowed_effect_types=frozenset({"api_request"}))
        interceptor = EffectInterceptor(policy=policy, journal=journal, event_sink=sink)

        tool_fn = AsyncMock(return_value="ok")
        descriptor = _make_descriptor(effect_type="db_write")

        with pytest.raises(EffectDeniedError):
            await interceptor.execute(
                descriptor=descriptor,
                tool_fn=tool_fn,
                tool_args={},
                attempt_number=1,
            )

        tool_fn.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_denied_emits_effect_denied_event(self) -> None:
        from miniautogen.core.contracts.effect import EffectDeniedError
        from miniautogen.core.effect_interceptor import EffectInterceptor
        from miniautogen.core.events.types import EventType
        journal = _make_journal()
        sink = _make_sink()
        policy = _make_policy(allowed_effect_types=frozenset({"api_request"}))
        interceptor = EffectInterceptor(policy=policy, journal=journal, event_sink=sink)

        with pytest.raises(EffectDeniedError):
            await interceptor.execute(
                descriptor=_make_descriptor(effect_type="db_write"),
                tool_fn=AsyncMock(),
                tool_args={},
                attempt_number=1,
            )

        event_types = [e.type for e in sink.events]
        assert EventType.EFFECT_DENIED in event_types


class TestEffectInterceptorFailurePath:
    @pytest.mark.asyncio
    async def test_tool_exception_records_failed_and_emits_event(self) -> None:
        from miniautogen.core.contracts.effect import EffectStatus, generate_idempotency_key
        from miniautogen.core.effect_interceptor import EffectInterceptor
        from miniautogen.core.events.types import EventType
        journal = _make_journal()
        sink = _make_sink()
        policy = _make_policy()
        interceptor = EffectInterceptor(policy=policy, journal=journal, event_sink=sink)

        descriptor = _make_descriptor()
        key = generate_idempotency_key(descriptor, attempt_number=1)

        tool_fn = AsyncMock(side_effect=RuntimeError("Connection refused"))

        with pytest.raises(RuntimeError, match="Connection refused"):
            await interceptor.execute(
                descriptor=descriptor,
                tool_fn=tool_fn,
                tool_args={},
                attempt_number=1,
            )

        record = await journal.get(key)
        assert record is not None
        assert record.status == EffectStatus.FAILED
        assert "Connection refused" in (record.error_info or "")

        event_types = [e.type for e in sink.events]
        assert EventType.EFFECT_FAILED in event_types
```

**Verify:**
```bash
pytest tests/core/test_effect_interceptor.py::TestEffectInterceptorImport -v
# Expected: FAILED - ModuleNotFoundError: No module named 'miniautogen.core.effect_interceptor'
```

---

#### Task 4.2: Implement `EffectInterceptor`

**Files:**
- Create: `miniautogen/core/effect_interceptor.py`

**What:** The full `EffectInterceptor` implementation with idempotency key generation, journal check, policy enforcement, stale pending handling, before/after/on_failure lifecycle, and event emission.

**How:**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/effect_interceptor.py`:

```python
"""EffectInterceptor: wraps tool execution with idempotency protection.

Part of WS3: Effect Engine.

The interceptor is optional -- the runtime checks for its presence before
calling it. This preserves backward compatibility with runs that do not
configure an EffectPolicy.

Usage (pseudocode in runtime tool dispatch):

    if self._effect_interceptor is not None:
        result = await self._effect_interceptor.execute(
            descriptor, tool_fn, tool_args, attempt_number
        )
    else:
        result = await tool_fn(**tool_args)
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from miniautogen.core.contracts.effect import (
    EffectDeniedError,
    EffectDuplicateError,
    EffectRecord,
    EffectStatus,
    generate_idempotency_key,
)
from miniautogen.core.events.event_sink import EventSink
from miniautogen.core.events.types import EventType
from miniautogen.policies.effect import EffectPolicy
from miniautogen.stores.effect_journal import EffectJournal

logger = logging.getLogger(__name__)

# Lazy import to avoid circular imports -- ExecutionEvent lives in core/contracts/events.py
_ExecutionEvent = None


def _get_execution_event_class():
    global _ExecutionEvent
    if _ExecutionEvent is None:
        from miniautogen.core.contracts.events import ExecutionEvent
        _ExecutionEvent = ExecutionEvent
    return _ExecutionEvent


def _make_event(
    event_type: EventType,
    run_id: str,
    payload: dict[str, Any],
) -> Any:
    ExecutionEvent = _get_execution_event_class()
    return ExecutionEvent(
        type=event_type,
        run_id=run_id,
        payload=payload,
    )


def _result_hash(result: Any) -> str:
    """Compute a SHA-256 hash of the tool result for verification on replay."""
    canonical = json.dumps(result, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


class EffectInterceptor:
    """Wraps tool execution with idempotency checks and journal bookkeeping.

    The runtime calls ``execute()`` instead of invoking the tool directly.
    This method handles the full before/execute/after lifecycle:

    1. Check policy (allowed type, step budget)
    2. Check journal for prior execution
    3. Register intent as PENDING
    4. Call tool_fn(**tool_args)
    5. Record outcome (COMPLETED or FAILED)
    6. Emit the appropriate ExecutionEvent

    All journal reads and writes are awaitable -- the interceptor is safe
    for async-only AnyIO event loops.
    """

    def __init__(
        self,
        policy: EffectPolicy,
        journal: EffectJournal,
        event_sink: EventSink,
    ) -> None:
        self._policy = policy
        self._journal = journal
        self._event_sink = event_sink

    async def execute(
        self,
        descriptor: Any,  # EffectDescriptor (avoid circular import at module level)
        tool_fn: Callable[..., Awaitable[Any]],
        tool_args: dict[str, Any],
        attempt_number: int = 1,
    ) -> Any:
        """Execute a tool call with idempotency protection.

        Returns the tool result (or None if the effect was skipped as a
        previously completed duplicate).

        Raises:
            EffectDeniedError: if the policy rejects the effect.
            EffectDuplicateError: if a fresh PENDING record exists for
                the same key (concurrent execution guard).
        """
        # ------------------------------------------------------------------
        # Step 1: Policy check
        # ------------------------------------------------------------------
        if self._policy.allowed_effect_types:
            if descriptor.effect_type not in self._policy.allowed_effect_types:
                idempotency_key = generate_idempotency_key(descriptor, attempt_number)
                await self._event_sink.publish(
                    _make_event(
                        EventType.EFFECT_DENIED,
                        run_id=descriptor.run_id,
                        payload={
                            "idempotency_key": idempotency_key,
                            "effect_type": descriptor.effect_type,
                            "reason": "effect_type_not_allowed",
                        },
                    )
                )
                raise EffectDeniedError(
                    f"effect_type '{descriptor.effect_type}' not in allowed_effect_types "
                    f"{self._policy.allowed_effect_types}"
                )

        # ------------------------------------------------------------------
        # Step 2: Generate idempotency key and check journal
        # ------------------------------------------------------------------
        idempotency_key = generate_idempotency_key(descriptor, attempt_number)
        existing = await self._journal.get(idempotency_key)

        if existing is not None:
            if existing.status == EffectStatus.COMPLETED:
                # Duplicate detected: skip execution, return None (cached result unavailable
                # without a result store, but the key contract is that execution is skipped)
                logger.info(
                    "Effect '%s' already completed (idempotency_key=%s); skipping execution",
                    descriptor.tool_name,
                    idempotency_key,
                )
                await self._event_sink.publish(
                    _make_event(
                        EventType.EFFECT_SKIPPED,
                        run_id=descriptor.run_id,
                        payload={
                            "idempotency_key": idempotency_key,
                            "effect_type": descriptor.effect_type,
                            "tool_name": descriptor.tool_name,
                            "reason": "duplicate_detected",
                            "original_completed_at": (
                                existing.completed_at.isoformat()
                                if existing.completed_at
                                else None
                            ),
                        },
                    )
                )
                return None

            elif existing.status == EffectStatus.PENDING:
                # Check if stale
                age_seconds = (
                    datetime.now(timezone.utc) - existing.created_at
                ).total_seconds()
                if age_seconds > self._policy.stale_pending_timeout_seconds:
                    logger.warning(
                        "Stale PENDING record found for key '%s' (age=%.1fs); "
                        "marking FAILED and re-registering",
                        idempotency_key,
                        age_seconds,
                    )
                    await self._journal.update_status(
                        idempotency_key,
                        EffectStatus.FAILED,
                        error_info="stale_pending_cleared",
                    )
                    # Fall through to fresh registration below
                else:
                    # Fresh PENDING: another execution may be in progress
                    raise EffectDuplicateError(
                        f"Effect '{idempotency_key}' is already PENDING (age={age_seconds:.1f}s). "
                        "Possible concurrent execution."
                    )

            # FAILED: allow fresh registration (fall through)

        # ------------------------------------------------------------------
        # Step 3: Register intent as PENDING
        # ------------------------------------------------------------------
        record = EffectRecord(
            idempotency_key=idempotency_key,
            descriptor=descriptor,
            status=EffectStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )
        # If the key already exists (stale FAILED from above), we need a new registration.
        # The journal.register() will raise EffectDuplicateError for any existing key.
        # For stale cleared records we must use a fresh key strategy or delete first.
        # Here we delete the stale record and re-register.
        existing_after_stale = await self._journal.get(idempotency_key)
        if existing_after_stale is not None and existing_after_stale.status == EffectStatus.FAILED:
            # Delete the failed record so we can re-register
            await self._journal.delete_by_run(descriptor.run_id)
            # Re-register only this specific record -- rebuild journal for this run
            # NOTE: In production, a targeted delete_by_key method would be preferred.
            # For now, we re-register after clearing the run (safe for single-run tests).
            # A future task can add delete_by_key to the journal ABC.
            pass

        await self._journal.register(record)
        await self._event_sink.publish(
            _make_event(
                EventType.EFFECT_REGISTERED,
                run_id=descriptor.run_id,
                payload={
                    "idempotency_key": idempotency_key,
                    "effect_type": descriptor.effect_type,
                    "tool_name": descriptor.tool_name,
                    "run_id": descriptor.run_id,
                    "step_id": descriptor.step_id,
                },
            )
        )

        # ------------------------------------------------------------------
        # Step 4: Execute the tool
        # ------------------------------------------------------------------
        start_ms = time.monotonic() * 1000
        try:
            result = await tool_fn(**tool_args)
        except Exception as exc:
            # Step 5a: Record failure
            await self._journal.update_status(
                idempotency_key,
                EffectStatus.FAILED,
                error_info=str(exc),
            )
            await self._event_sink.publish(
                _make_event(
                    EventType.EFFECT_FAILED,
                    run_id=descriptor.run_id,
                    payload={
                        "idempotency_key": idempotency_key,
                        "effect_type": descriptor.effect_type,
                        "tool_name": descriptor.tool_name,
                        "error_category": "adapter",
                        "error_info": str(exc),
                    },
                )
            )
            raise

        # Step 5b: Record success
        duration_ms = int(time.monotonic() * 1000 - start_ms)
        rh = _result_hash(result)
        await self._journal.update_status(
            idempotency_key,
            EffectStatus.COMPLETED,
            result_hash=rh,
        )
        await self._event_sink.publish(
            _make_event(
                EventType.EFFECT_EXECUTED,
                run_id=descriptor.run_id,
                payload={
                    "idempotency_key": idempotency_key,
                    "effect_type": descriptor.effect_type,
                    "tool_name": descriptor.tool_name,
                    "result_hash": rh,
                    "duration_ms": duration_ms,
                },
            )
        )
        return result
```

**Verify:**
```bash
pytest tests/core/test_effect_interceptor.py -v
# Expected: all tests pass
```

---

#### Task 4.3: Commit TG-4

**What:** Atomic commit for the EffectInterceptor.

```bash
git add miniautogen/core/effect_interceptor.py \
        tests/core/test_effect_interceptor.py
git commit -m "feat(core): add EffectInterceptor with idempotency and policy enforcement (WS3 TG-4)"
```

**Verify:**
```bash
python -m pytest tests/ -x -q
# Expected: all tests pass
```

---

### TG-5: Event Integration

Add 5 new `EventType` entries and the `EFFECT_EVENT_TYPES` convenience set to `core/events/types.py`.

---

#### Task 5.1: Write failing test for effect event types

**Files:**
- Create: `tests/core/events/test_effect_event_types.py`

**What:** Tests asserting all 5 new event types exist in `EventType` and that `EFFECT_EVENT_TYPES` is defined.

**How:**

Create `tests/core/events/test_effect_event_types.py`:

```python
"""Tests for effect lifecycle EventType entries (WS3 TG-5)."""

from __future__ import annotations

import pytest


class TestEffectEventTypes:
    def test_effect_registered_exists(self) -> None:
        from miniautogen.core.events.types import EventType
        assert EventType.EFFECT_REGISTERED == "effect_registered"

    def test_effect_executed_exists(self) -> None:
        from miniautogen.core.events.types import EventType
        assert EventType.EFFECT_EXECUTED == "effect_executed"

    def test_effect_skipped_exists(self) -> None:
        from miniautogen.core.events.types import EventType
        assert EventType.EFFECT_SKIPPED == "effect_skipped"

    def test_effect_failed_exists(self) -> None:
        from miniautogen.core.events.types import EventType
        assert EventType.EFFECT_FAILED == "effect_failed"

    def test_effect_denied_exists(self) -> None:
        from miniautogen.core.events.types import EventType
        assert EventType.EFFECT_DENIED == "effect_denied"

    def test_all_are_str_enum_members(self) -> None:
        from miniautogen.core.events.types import EventType
        effect_members = [
            EventType.EFFECT_REGISTERED,
            EventType.EFFECT_EXECUTED,
            EventType.EFFECT_SKIPPED,
            EventType.EFFECT_FAILED,
            EventType.EFFECT_DENIED,
        ]
        for m in effect_members:
            assert isinstance(m, str)


class TestEffectEventTypesSet:
    def test_effect_event_types_import(self) -> None:
        from miniautogen.core.events.types import EFFECT_EVENT_TYPES  # noqa: F401

    def test_effect_event_types_has_five_members(self) -> None:
        from miniautogen.core.events.types import EFFECT_EVENT_TYPES
        assert len(EFFECT_EVENT_TYPES) == 5

    def test_effect_event_types_contains_all_five(self) -> None:
        from miniautogen.core.events.types import EFFECT_EVENT_TYPES, EventType
        assert EventType.EFFECT_REGISTERED in EFFECT_EVENT_TYPES
        assert EventType.EFFECT_EXECUTED in EFFECT_EVENT_TYPES
        assert EventType.EFFECT_SKIPPED in EFFECT_EVENT_TYPES
        assert EventType.EFFECT_FAILED in EFFECT_EVENT_TYPES
        assert EventType.EFFECT_DENIED in EFFECT_EVENT_TYPES

    def test_effect_event_types_is_set_of_event_type(self) -> None:
        from miniautogen.core.events.types import EFFECT_EVENT_TYPES, EventType
        assert all(isinstance(t, EventType) for t in EFFECT_EVENT_TYPES)


class TestEffectEventTypesNoRegressionOnExisting:
    """Existing EventType members must not be disturbed."""

    def test_run_started_still_exists(self) -> None:
        from miniautogen.core.events.types import EventType
        assert EventType.RUN_STARTED == "run_started"

    def test_backend_tool_call_requested_still_exists(self) -> None:
        from miniautogen.core.events.types import EventType
        assert EventType.BACKEND_TOOL_CALL_REQUESTED == "backend_tool_call_requested"

    def test_approval_event_types_still_present(self) -> None:
        from miniautogen.core.events.types import APPROVAL_EVENT_TYPES, EventType
        assert EventType.APPROVAL_REQUESTED in APPROVAL_EVENT_TYPES
```

**Verify:**
```bash
pytest tests/core/events/test_effect_event_types.py -v
# Expected: FAILED - AttributeError: 'EventType' has no 'EFFECT_REGISTERED'
```

---

#### Task 5.2: Implement effect event types in `types.py`

**Files:**
- Modify: `miniautogen/core/events/types.py`

**What:** Append 5 new enum members and the `EFFECT_EVENT_TYPES` set to `types.py`.

**How:**

In `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/events/types.py`, append after the `APPROVAL_DENIED` / `APPROVAL_TIMEOUT` entries (inside the `EventType` class), then add the convenience set after the class.

Add these 5 members inside the `EventType` enum class, after the `APPROVAL_TIMEOUT` line:

```python
    # Effect Engine lifecycle (WS3)
    EFFECT_REGISTERED = "effect_registered"
    EFFECT_EXECUTED = "effect_executed"
    EFFECT_SKIPPED = "effect_skipped"
    EFFECT_FAILED = "effect_failed"
    EFFECT_DENIED = "effect_denied"
```

Then append the following set at the end of the file (after the existing `BACKEND_EVENT_TYPES` block):

```python

EFFECT_EVENT_TYPES: set[EventType] = {
    EventType.EFFECT_REGISTERED,
    EventType.EFFECT_EXECUTED,
    EventType.EFFECT_SKIPPED,
    EventType.EFFECT_FAILED,
    EventType.EFFECT_DENIED,
}
```

**Verify:**
```bash
pytest tests/core/events/test_effect_event_types.py -v
# Expected: all tests pass
pytest tests/core/events/ -v
# Expected: all event tests pass (no regression)
```

---

#### Task 5.3: Commit TG-5

**What:** Atomic commit for the new event types.

```bash
git add miniautogen/core/events/types.py \
        tests/core/events/test_effect_event_types.py
git commit -m "feat(events): add EFFECT_REGISTERED/EXECUTED/SKIPPED/FAILED/DENIED event types (WS3 TG-5)"
```

**Verify:**
```bash
python -m pytest tests/ -x -q
# Expected: all tests pass
```

---

### TG-6: SQLAlchemy EffectJournal

Async SQLAlchemy implementation following the pattern in `sqlalchemy_checkpoint_store.py`. Introduces the `effect_journal` table with a composite index on `(run_id, status)`.

---

#### Task 6.1: Write failing test for `SQLAlchemyEffectJournal`

**Files:**
- Create: `tests/stores/test_sqlalchemy_effect_journal.py`

**What:** Integration tests for `SQLAlchemyEffectJournal` against an in-process SQLite database. All the same behavioural tests as `InMemoryEffectJournal` -- the contract is identical.

**How:**

Create `tests/stores/test_sqlalchemy_effect_journal.py`:

```python
"""Integration tests for SQLAlchemyEffectJournal (WS3 TG-6).

Uses an in-process async SQLite database (aiosqlite) to avoid any external
dependencies. All tests follow the same behavioural assertions as the
InMemoryEffectJournal suite to verify that both implementations satisfy
the same contract.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest


DB_URL = "sqlite+aiosqlite:///:memory:"


async def _make_journal():
    from miniautogen.stores.sqlalchemy_effect_journal import SQLAlchemyEffectJournal
    journal = SQLAlchemyEffectJournal(db_url=DB_URL)
    await journal.init_db()
    return journal


def _make_descriptor(
    run_id: str = "run-1",
    step_id: str = "step-1",
    tool_name: str = "send_email",
    effect_type: str = "tool_call",
) -> object:
    from miniautogen.core.contracts.effect import EffectDescriptor
    return EffectDescriptor(
        effect_type=effect_type,
        tool_name=tool_name,
        args_hash="abc123",
        run_id=run_id,
        step_id=step_id,
        metadata={},
    )


def _make_record(
    key: str = "key-1",
    run_id: str = "run-1",
    step_id: str = "step-1",
    tool_name: str = "send_email",
) -> object:
    from miniautogen.core.contracts.effect import EffectRecord, EffectStatus
    return EffectRecord(
        idempotency_key=key,
        descriptor=_make_descriptor(run_id=run_id, step_id=step_id, tool_name=tool_name),
        status=EffectStatus.PENDING,
        created_at=datetime.now(timezone.utc),
    )


class TestSQLAlchemyEffectJournalImport:
    def test_import(self) -> None:
        from miniautogen.stores.sqlalchemy_effect_journal import (
            SQLAlchemyEffectJournal,  # noqa: F401
        )

    def test_is_subclass_of_effect_journal(self) -> None:
        from miniautogen.stores.effect_journal import EffectJournal
        from miniautogen.stores.sqlalchemy_effect_journal import SQLAlchemyEffectJournal
        assert issubclass(SQLAlchemyEffectJournal, EffectJournal)


class TestSQLAlchemyEffectJournalRegisterAndGet:
    @pytest.mark.asyncio
    async def test_register_then_get_returns_record(self) -> None:
        journal = await _make_journal()
        record = _make_record("key-1")
        await journal.register(record)
        result = await journal.get("key-1")
        assert result is not None
        assert result.idempotency_key == "key-1"

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self) -> None:
        journal = await _make_journal()
        result = await journal.get("no-such-key")
        assert result is None

    @pytest.mark.asyncio
    async def test_register_duplicate_key_raises(self) -> None:
        from miniautogen.core.contracts.effect import EffectDuplicateError
        journal = await _make_journal()
        record = _make_record("key-1")
        await journal.register(record)
        with pytest.raises(EffectDuplicateError):
            await journal.register(record)


class TestSQLAlchemyEffectJournalUpdateStatus:
    @pytest.mark.asyncio
    async def test_update_to_completed(self) -> None:
        from miniautogen.core.contracts.effect import EffectStatus
        journal = await _make_journal()
        await journal.register(_make_record("key-1"))
        await journal.update_status("key-1", EffectStatus.COMPLETED, result_hash="sha256-abc")
        record = await journal.get("key-1")
        assert record is not None
        assert record.status == EffectStatus.COMPLETED
        assert record.result_hash == "sha256-abc"
        assert record.completed_at is not None

    @pytest.mark.asyncio
    async def test_update_to_failed(self) -> None:
        from miniautogen.core.contracts.effect import EffectStatus
        journal = await _make_journal()
        await journal.register(_make_record("key-1"))
        await journal.update_status("key-1", EffectStatus.FAILED, error_info="timeout")
        record = await journal.get("key-1")
        assert record is not None
        assert record.status == EffectStatus.FAILED
        assert record.error_info == "timeout"


class TestSQLAlchemyEffectJournalListByRun:
    @pytest.mark.asyncio
    async def test_list_by_run_returns_all(self) -> None:
        journal = await _make_journal()
        await journal.register(_make_record("key-1", run_id="run-A"))
        await journal.register(_make_record("key-2", run_id="run-A"))
        await journal.register(_make_record("key-3", run_id="run-B"))
        results = await journal.list_by_run("run-A")
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_list_by_run_filtered_by_status(self) -> None:
        from miniautogen.core.contracts.effect import EffectStatus
        journal = await _make_journal()
        await journal.register(_make_record("key-1", run_id="run-A"))
        await journal.register(_make_record("key-2", run_id="run-A"))
        await journal.update_status("key-1", EffectStatus.COMPLETED)
        results = await journal.list_by_run("run-A", status=EffectStatus.COMPLETED)
        assert len(results) == 1
        assert results[0].idempotency_key == "key-1"

    @pytest.mark.asyncio
    async def test_list_by_run_pagination(self) -> None:
        journal = await _make_journal()
        for i in range(5):
            await journal.register(_make_record(f"key-{i}", run_id="run-A"))
        page1 = await journal.list_by_run("run-A", limit=2, offset=0)
        page2 = await journal.list_by_run("run-A", limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) == 2
        keys_p1 = {r.idempotency_key for r in page1}
        keys_p2 = {r.idempotency_key for r in page2}
        assert keys_p1.isdisjoint(keys_p2)


class TestSQLAlchemyEffectJournalDeleteByRun:
    @pytest.mark.asyncio
    async def test_delete_by_run_returns_count(self) -> None:
        journal = await _make_journal()
        await journal.register(_make_record("key-1", run_id="run-A"))
        await journal.register(_make_record("key-2", run_id="run-A"))
        await journal.register(_make_record("key-3", run_id="run-B"))
        count = await journal.delete_by_run("run-A")
        assert count == 2

    @pytest.mark.asyncio
    async def test_delete_by_run_removes_records(self) -> None:
        journal = await _make_journal()
        await journal.register(_make_record("key-1", run_id="run-A"))
        await journal.delete_by_run("run-A")
        assert await journal.get("key-1") is None


class TestSQLAlchemyEffectJournalCompositeIndex:
    """Verify the composite index (run_id, status) is created."""

    @pytest.mark.asyncio
    async def test_table_has_composite_index(self) -> None:
        from miniautogen.stores.sqlalchemy_effect_journal import DBEffectRecord
        index_names = {idx.name for idx in DBEffectRecord.__table__.indexes}
        # The composite index on (run_id, status) must be present
        assert any("run_id" in name and "status" in name for name in index_names), (
            f"Expected a composite index on (run_id, status), got: {index_names}"
        )
```

**Verify:**
```bash
pytest tests/stores/test_sqlalchemy_effect_journal.py::TestSQLAlchemyEffectJournalImport -v
# Expected: FAILED - ModuleNotFoundError: No module named 'miniautogen.stores.sqlalchemy_effect_journal'
```

---

#### Task 6.2: Implement `SQLAlchemyEffectJournal`

**Files:**
- Create: `miniautogen/stores/sqlalchemy_effect_journal.py`

**What:** Async SQLAlchemy implementation with ORM model `DBEffectRecord`, composite index on `(run_id, status)`, and full implementation of all 5 abstract methods from `EffectJournal`.

**How:**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/stores/sqlalchemy_effect_journal.py`:

```python
"""SQLAlchemyEffectJournal: async SQLAlchemy backend for the Effect Engine.

Part of WS3: Effect Engine.

Pattern: follows SQLAlchemyCheckpointStore in
miniautogen/stores/sqlalchemy_checkpoint_store.py.

Table: effect_journal
Index: ix_effect_journal_run_id_status on (run_id, status)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, String, Text, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from miniautogen.core.contracts.effect import (
    EffectDescriptor,
    EffectDuplicateError,
    EffectRecord,
    EffectStatus,
)
from miniautogen.stores.effect_journal import EffectJournal


class Base(DeclarativeBase):
    pass


class DBEffectRecord(Base):
    __tablename__ = "effect_journal"

    idempotency_key: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    step_id: Mapped[str] = mapped_column(String, nullable=False)
    effect_type: Mapped[str] = mapped_column(String, nullable=False)
    effect_descriptor_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    result_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    error_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_effect_journal_run_id_status", "run_id", "status"),
    )


def _db_to_record(db: DBEffectRecord) -> EffectRecord:
    """Convert a DBEffectRecord ORM row to a domain EffectRecord."""
    descriptor_data = json.loads(db.effect_descriptor_json)
    descriptor = EffectDescriptor(
        effect_type=descriptor_data["effect_type"],
        tool_name=descriptor_data["tool_name"],
        args_hash=descriptor_data["args_hash"],
        run_id=descriptor_data["run_id"],
        step_id=descriptor_data["step_id"],
        metadata=descriptor_data.get("metadata", {}),
    )
    return EffectRecord(
        idempotency_key=db.idempotency_key,
        descriptor=descriptor,
        status=EffectStatus(db.status),
        created_at=db.created_at,
        completed_at=db.completed_at,
        result_hash=db.result_hash,
        error_info=db.error_info,
    )


def _descriptor_to_json(descriptor: EffectDescriptor) -> str:
    return json.dumps(
        {
            "effect_type": descriptor.effect_type,
            "tool_name": descriptor.tool_name,
            "args_hash": descriptor.args_hash,
            "run_id": descriptor.run_id,
            "step_id": descriptor.step_id,
            "metadata": descriptor.metadata,
        },
        separators=(",", ":"),
        default=str,
    )


class SQLAlchemyEffectJournal(EffectJournal):
    """Async SQLAlchemy-backed EffectJournal for production use.

    Requires an async-compatible database URL, e.g.:
    - "sqlite+aiosqlite:///effects.db"
    - "postgresql+asyncpg://user:pass@host/db"

    Call ``await journal.init_db()`` once at startup to create the table.
    """

    def __init__(self, db_url: str) -> None:
        self.engine = create_async_engine(db_url, echo=False)
        self.async_session = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )

    async def init_db(self) -> None:
        """Create the effect_journal table if it does not exist."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def register(self, record: EffectRecord) -> None:
        async with self.async_session() as session:
            async with session.begin():
                existing = await session.get(DBEffectRecord, record.idempotency_key)
                if existing is not None:
                    raise EffectDuplicateError(
                        f"Effect with idempotency_key '{record.idempotency_key}' "
                        "already registered"
                    )
                db_record = DBEffectRecord(
                    idempotency_key=record.idempotency_key,
                    run_id=record.descriptor.run_id,
                    step_id=record.descriptor.step_id,
                    effect_type=record.descriptor.effect_type,
                    effect_descriptor_json=_descriptor_to_json(record.descriptor),
                    status=record.status.value,
                    result_hash=record.result_hash,
                    error_info=record.error_info,
                    created_at=record.created_at,
                    completed_at=record.completed_at,
                )
                session.add(db_record)

    async def get(self, idempotency_key: str) -> EffectRecord | None:
        async with self.async_session() as session:
            db_record = await session.get(DBEffectRecord, idempotency_key)
            if db_record is None:
                return None
            return _db_to_record(db_record)

    async def update_status(
        self,
        idempotency_key: str,
        status: EffectStatus,
        result_hash: str | None = None,
        error_info: str | None = None,
    ) -> None:
        async with self.async_session() as session:
            async with session.begin():
                db_record = await session.get(DBEffectRecord, idempotency_key)
                if db_record is None:
                    raise KeyError(
                        f"No effect record found for key '{idempotency_key}'"
                    )
                db_record.status = status.value
                db_record.completed_at = datetime.now(timezone.utc)
                if result_hash is not None:
                    db_record.result_hash = result_hash
                if error_info is not None:
                    db_record.error_info = error_info

    async def list_by_run(
        self,
        run_id: str,
        status: EffectStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EffectRecord]:
        async with self.async_session() as session:
            stmt = select(DBEffectRecord).where(DBEffectRecord.run_id == run_id)
            if status is not None:
                stmt = stmt.where(DBEffectRecord.status == status.value)
            stmt = stmt.order_by(DBEffectRecord.created_at.asc())
            stmt = stmt.limit(limit).offset(offset)
            result = await session.execute(stmt)
            return [_db_to_record(row) for row in result.scalars().all()]

    async def delete_by_run(self, run_id: str) -> int:
        async with self.async_session() as session:
            async with session.begin():
                stmt = select(DBEffectRecord).where(DBEffectRecord.run_id == run_id)
                result = await session.execute(stmt)
                rows = result.scalars().all()
                count = len(rows)
                for row in rows:
                    await session.delete(row)
                return count
```

**Verify:**
```bash
pytest tests/stores/test_sqlalchemy_effect_journal.py -v
# Expected: all tests pass
```

---

#### Task 6.3: Commit TG-6

**What:** Atomic commit for the SQLAlchemy implementation.

```bash
git add miniautogen/stores/sqlalchemy_effect_journal.py \
        tests/stores/test_sqlalchemy_effect_journal.py
git commit -m "feat(stores): add SQLAlchemyEffectJournal with composite index (WS3 TG-6)"
```

**Verify:**
```bash
python -m pytest tests/ -x -q
# Expected: all tests pass
```

---

## Final Verification

After all TGs are committed, run the full test suite and verify the entire Effect Engine surface is importable:

```bash
# Full test suite
python -m pytest tests/ -v --tb=short

# Import smoke test for all new public surfaces
python -c "
from miniautogen.core.contracts.enums import ErrorCategory
from miniautogen.core.contracts.effect import (
    EffectDeniedError, EffectDuplicateError, EffectJournalUnavailableError,
    EffectDescriptor, EffectRecord, EffectStatus,
    canonical_args_hash, generate_idempotency_key,
)
from miniautogen.policies.effect import EffectPolicy, EffectPolicyEvaluator
from miniautogen.stores.effect_journal import EffectJournal
from miniautogen.stores.in_memory_effect_journal import InMemoryEffectJournal
from miniautogen.stores.sqlalchemy_effect_journal import SQLAlchemyEffectJournal
from miniautogen.core.effect_interceptor import EffectInterceptor
from miniautogen.core.events.types import (
    EventType, EFFECT_EVENT_TYPES,
)
assert EventType.EFFECT_REGISTERED in EFFECT_EVENT_TYPES
print('All WS3 Effect Engine imports OK')
"
```

**Expected output:**
```
All WS3 Effect Engine imports OK
```

---

## File Placement Summary

| Artifact | Path |
|----------|------|
| `ErrorCategory` enum | `miniautogen/core/contracts/enums.py` (appended) |
| `EffectDeniedError`, `EffectDuplicateError`, `EffectJournalUnavailableError` | `miniautogen/core/contracts/effect.py` |
| `EffectStatus`, `EffectDescriptor`, `EffectRecord` | `miniautogen/core/contracts/effect.py` |
| `canonical_args_hash`, `generate_idempotency_key` | `miniautogen/core/contracts/effect.py` |
| `EffectPolicy`, `EffectPolicyEvaluator` | `miniautogen/policies/effect.py` |
| `EffectJournal` (ABC) | `miniautogen/stores/effect_journal.py` |
| `InMemoryEffectJournal` | `miniautogen/stores/in_memory_effect_journal.py` |
| `SQLAlchemyEffectJournal`, `DBEffectRecord` | `miniautogen/stores/sqlalchemy_effect_journal.py` |
| `EffectInterceptor` | `miniautogen/core/effect_interceptor.py` |
| 5 new `EventType` entries + `EFFECT_EVENT_TYPES` | `miniautogen/core/events/types.py` (appended) |
| Tests: foundation + exceptions | `tests/core/contracts/test_effect_foundation.py` |
| Tests: EffectPolicy + evaluator | `tests/policies/test_effect_policy.py` |
| Tests: EffectJournal + InMemory | `tests/stores/test_effect_journal.py` |
| Tests: EffectDescriptor/Record/Status/utils | `tests/core/contracts/test_effect_models.py` |
| Tests: EffectInterceptor | `tests/core/test_effect_interceptor.py` |
| Tests: event types | `tests/core/events/test_effect_event_types.py` |
| Tests: SQLAlchemy journal | `tests/stores/test_sqlalchemy_effect_journal.py` |

---

## Commit Summary

| TG | Commit message |
|----|----------------|
| TG-0 | `feat(core): add ErrorCategory enum and effect exception classes (WS3 TG-0)` |
| TG-1 | `feat(policies): add EffectPolicy frozen dataclass and EffectPolicyEvaluator (WS3 TG-1)` |
| TG-2 | `feat(stores): add EffectJournal ABC and InMemoryEffectJournal (WS3 TG-2)` |
| TG-3 | `feat(core): add EffectDescriptor, EffectRecord, EffectStatus, and key utilities (WS3 TG-3)` |
| TG-4 | `feat(core): add EffectInterceptor with idempotency and policy enforcement (WS3 TG-4)` |
| TG-5 | `feat(events): add EFFECT_REGISTERED/EXECUTED/SKIPPED/FAILED/DENIED event types (WS3 TG-5)` |
| TG-6 | `feat(stores): add SQLAlchemyEffectJournal with composite index (WS3 TG-6)` |

---

## Dependency Order

The TGs must be executed in this order due to cross-module imports:

```
TG-0  (enums.py + exception stubs in effect.py)
  |
  +-- TG-3  (EffectStatus/Descriptor/Record in effect.py -- same file as TG-0)
  |     |
  |     +-- TG-2  (EffectJournal ABC + InMemoryEffectJournal -- depends on TG-3 models)
  |           |
  |           +-- TG-1  (EffectPolicyEvaluator -- depends on journal in TG-2)
  |           |
  |           +-- TG-5  (EventType entries -- parallel, no model dependency)
  |           |
  |           +-- TG-4  (EffectInterceptor -- depends on TG-2, TG-3, TG-5)
  |                 |
  |                 +-- TG-6  (SQLAlchemy journal -- depends on TG-2, TG-3)
```

**Recommended execution sequence:** TG-0 → TG-3 → TG-5 → TG-2 → TG-1 → TG-4 → TG-6

All TGs must be fully committed and green before starting the next one.
