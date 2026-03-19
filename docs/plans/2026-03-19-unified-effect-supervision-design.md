# Unified Design Spec: Error Taxonomy, Effect Engine & Supervision Trees

**Date:** 2026-03-19
**Status:** Approved (reviewed: code-quality, business-logic, security)
**Replaces:** WS3 (Effect Engine) + WS4 (Supervision Trees) standalone specs
**Branch:** `feat/effect-supervision`

---

## 1. Problem Statement

MiniAutoGen lacks three interconnected capabilities:

1. **No structured error taxonomy.** Errors are classified by Python exception class name (`type(exc).__name__`), not by semantic category. The canonical categories documented in CLAUDE.md (`transient`, `permanent`, `validation`, `timeout`, `cancellation`, `adapter`, `configuration`, `state_consistency`) exist only in documentation.

2. **No idempotency for side effects.** If a pipeline fails after executing a tool call (e.g., charging a credit card) and is retried from checkpoint, the tool executes again. There is no deduplication mechanism.

3. **Flat error handling in runtimes.** All runtimes use `try/except` with fail-fast semantics. There is no hierarchical fault supervision, no per-step restart policy, and no circuit breakers.

These three problems are layered: error taxonomy enables effect classification, which enables supervision decisions.

---

## 2. Current State Assessment

### What works well
- Frozen `RunContext`, `ExecutionEvent`, `FrozenState` (WS2 complete)
- 3 coordination modes: Workflow, Deliberation, AgenticLoop
- Event system with composable sinks/filters and comprehensive event types
- 8 policy classes defined (ExecutionPolicy, RetryPolicy, BudgetPolicy, etc.)
- Store pattern: ABC + InMemory + SQLAlchemy for RunStore, CheckpointStore, MessageStore
- orjson integration, deepdiff immutability guards

### Structural gaps that constrain this work
- **Policies are directly injected, not event-driven.** `PipelineRunner` receives `RetryPolicy`, `ExecutionPolicy`, `ApprovalGate` as constructor args. `PolicyChain`, `BudgetTracker`, `ValidationPolicy`, `TimeoutScope` exist but are not wired to any runtime.
- **Each SQLAlchemy store declares its own `Base(DeclarativeBase)`.** Cannot share DB transactions across stores. Atomic checkpoint+event is impossible today.
- **Checkpointing is final-result-only.** No per-step checkpointing. `SessionRecovery` can load the last checkpoint but cannot resume from a specific workflow step.
- **`StoreProtocol` in contracts uses different method names than actual stores.** The protocol defines `save/get/exists/delete`; stores use `save_run/get_run`, `save_checkpoint/get_checkpoint`, etc.

### Design principle
This spec addresses the gaps **incrementally**: each phase delivers testable value and only depends on infrastructure that already exists or was created in a prior phase. Infrastructure debt (SQLAlchemy unification, atomic checkpoints) is deferred to Phase 4 after the core abstractions are proven with in-memory implementations.

---

## 3. Architecture: 4 Phases

```
Phase 1: Error Taxonomy & Foundation
    │
    ▼
Phase 2: Effect Engine (in-memory only)
    │
    ▼
Phase 3: Supervision Core (in-memory only)
    │
    ▼
Phase 4: Infrastructure Debt (SQLAlchemy unification, atomic checkpoints, durable stores)
```

Each phase is a separate branch/PR, squash-merged to main.

---

## 4. Phase 1 — Error Taxonomy & Shared Foundation

### Goal
Establish the canonical error classification system and shared contracts that Phase 2 and 3 depend on.

### 4.1 ErrorCategory Enum

**File:** `miniautogen/core/contracts/enums.py`

```python
class ErrorCategory(str, Enum):
    TRANSIENT = "transient"
    PERMANENT = "permanent"
    VALIDATION = "validation"
    TIMEOUT = "timeout"
    CANCELLATION = "cancellation"
    ADAPTER = "adapter"
    CONFIGURATION = "configuration"
    STATE_CONSISTENCY = "state_consistency"
```

Aligns with the 8 categories in CLAUDE.md section 4.2.

### 4.2 SupervisionStrategy Enum

**File:** `miniautogen/core/contracts/enums.py`

```python
class SupervisionStrategy(str, Enum):
    RESTART = "restart"
    RESUME = "resume"
    STOP = "stop"
    ESCALATE = "escalate"
```

### 4.3 Effect Exception Classes

**File:** `miniautogen/core/contracts/effect.py`

Three typed exception classes, each carrying an `ErrorCategory`:

| Exception | Category | When |
|-----------|----------|------|
| `EffectDeniedError` | `VALIDATION` | Effect type not allowed or max-per-step exceeded |
| `EffectDuplicateError` | `STATE_CONSISTENCY` | Idempotency key already COMPLETED |
| `EffectJournalUnavailableError` | `ADAPTER` | Journal store unreachable |

Base class `EffectError(Exception)` with `category: ErrorCategory` class attribute.

### 4.4 StepSupervision & SupervisionDecision

**File:** `miniautogen/core/contracts/supervision.py` (commit existing untracked file after fixing imports)

Both models must inherit from `MiniAutoGenBaseModel` with `ConfigDict(frozen=True)`, consistent with `ExecutionEvent` and `RunContext`.

- `StepSupervision`: frozen Pydantic model with strategy, max_restarts, circuit_breaker_threshold, etc.
- `SupervisionDecision`: frozen Pydantic model with action, reason, should_checkpoint. `metadata` must use `tuple[tuple[str, Any], ...]` (not `dict`) to preserve immutability, matching the `ExecutionEvent.payload` pattern.

**Note:** The existing untracked `supervision.py` uses plain `BaseModel` and a mutable `dict` for `SupervisionDecision.metadata`. Both must be fixed before committing: inherit from `MiniAutoGenBaseModel` and convert metadata to tuple-of-tuples.

### 4.5 Error Classifier Function

**File:** `miniautogen/core/runtime/classifier.py`

```python
# Default mappings (checked in order — subclasses BEFORE superclasses)
_DEFAULT_MAPPINGS: list[tuple[type, ErrorCategory]] = [...]

# User-extensible registry
_custom_mappings: list[tuple[type, ErrorCategory]] = []

def register_error_mapping(exc_class: type, category: ErrorCategory) -> None:
    """Register a custom exception-to-category mapping.

    Custom mappings are checked BEFORE default mappings, allowing users
    to override defaults for library-specific exceptions (e.g., httpx,
    aiohttp, gRPC) without importing those libraries in core.
    """

def classify_error(exc: BaseException) -> ErrorCategory:
    """Map Python exceptions to canonical ErrorCategory.

    Check order: custom mappings → default mappings → PERMANENT fallback.
    Within each group, isinstance checks run in list order.
    """
```

Default mapping rules (ORDER MATTERS — subclasses before superclasses):

| Priority | Python Exception | ErrorCategory | Notes |
|----------|-----------------|---------------|-------|
| 1 | `EffectError` subclasses | Use `exc.category` directly | Self-classifying |
| 2 | `TimeoutError` | `TIMEOUT` | |
| 3 | `anyio.get_cancelled_exc_class()` | `CANCELLATION` | `asyncio.CancelledError` on asyncio backends |
| 4 | `PermissionError` | `PERMANENT` | Subclass of `OSError` — MUST be checked before `OSError` |
| 5 | `ValueError`, `TypeError`, `ValidationError`, `PermissionDeniedError` | `VALIDATION` | |
| 6 | `BudgetExceededError` | `VALIDATION` | |
| 7 | `BackendUnavailableError` | `ADAPTER` | |
| 8 | `AgentDriverError` subclasses | `ADAPTER` | |
| 9 | `ConnectionError`, `OSError` | `TRANSIENT` | Covers `httpx.ConnectError` via MRO — no httpx import in core |
| 10 | `KeyError`, `AttributeError`, `NotImplementedError` | `PERMANENT` | |
| 11 | Default | `PERMANENT` | Fail-safe: unknown errors don't retry |

**Extensibility example** (user code, not in core):
```python
import httpx
from miniautogen.core.runtime.classifier import register_error_mapping
from miniautogen.core.contracts import ErrorCategory

register_error_mapping(httpx.TimeoutException, ErrorCategory.TIMEOUT)
register_error_mapping(httpx.HTTPStatusError, ErrorCategory.ADAPTER)
```

### 4.6 Fix Existing Test Failures

- 21 tests in `test_effect_foundation.py`: will pass once 4.1 + 4.3 are implemented
- 3 tests in `test_immutability.py`: investigate and fix `with_previous_result` / metadata isolation
- 1 test `test_import_boundary.py`: investigate CLI import leak
- 1 test `test_zero_coupling.py`: investigate TUI importing forbidden modules

### 4.7 Public API Updates

Export from `miniautogen/core/contracts/__init__.py`:
- `ErrorCategory`, `SupervisionStrategy`
- `EffectError`, `EffectDeniedError`, `EffectDuplicateError`, `EffectJournalUnavailableError`
- `StepSupervision`, `SupervisionDecision`

### Success Criteria
- All 1442 tests pass (0 failures)
- `ErrorCategory` and `SupervisionStrategy` importable from `miniautogen.core.contracts`
- `classify_error()` correctly maps all existing exception types
- `PermissionError` classified as `PERMANENT` (not `TRANSIENT` via `OSError` MRO)
- `register_error_mapping()` allows users to add custom mappings that take priority over defaults

---

## 5. Phase 2 — Effect Engine

### Goal
Prevent duplicate side effects on retry/replay through an optional idempotency middleware.

### 5.1 EffectStatus Enum

**File:** `miniautogen/core/contracts/effect.py` (extend existing)

```python
class EffectStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
```

### 5.2 EffectDescriptor & EffectRecord

**File:** `miniautogen/core/contracts/effect.py` (extend existing)

`EffectDescriptor` — inherits `MiniAutoGenBaseModel` with `ConfigDict(frozen=True)`:
- `effect_type: str` — "tool_call", "api_request", etc.
- `tool_name: str`
- `args_hash: str` — SHA-256 of canonical JSON of arguments
- `run_id: str`
- `step_id: str`
- `metadata: tuple[tuple[str, Any], ...]` — immutable, matches ExecutionEvent pattern

`EffectRecord` — inherits `MiniAutoGenBaseModel` with `ConfigDict(frozen=True)`:
- `idempotency_key: str` — SHA-256(run_id + step_id + tool_name + args_hash). Deterministic for the same logical operation regardless of retry attempt. `attempt` is explicitly EXCLUDED — including it would generate different keys per retry, defeating deduplication.
- `descriptor: EffectDescriptor`
- `status: EffectStatus`
- `created_at: datetime`
- `completed_at: datetime | None`
- `result_hash: str | None` — SHA-256 of result for audit
- `error_info: str | None` — sanitized: MUST NOT contain PII, credentials, or payment instrument details. Store exception type + generic message only.

### 5.3 EffectJournal ABC & InMemory Implementation

**ABC file:** `miniautogen/stores/effect_journal.py`

```python
class EffectJournal(ABC):
    async def register(self, record: EffectRecord) -> None: ...
    async def get(self, idempotency_key: str) -> EffectRecord | None: ...
    async def update_status(self, key: str, status: EffectStatus, ...) -> None: ...
    async def list_by_run(self, run_id: str, ...) -> list[EffectRecord]: ...
    async def delete_by_run(self, run_id: str) -> int: ...
```

**InMemory file:** `miniautogen/stores/in_memory_effect_journal.py`

Dict-backed implementation. Sufficient for testing and single-process use.

### 5.4 EffectPolicy

**File:** `miniautogen/policies/effect.py`

Pydantic `BaseModel` with `ConfigDict(frozen=True)`, consistent with other policies:
- `max_effects_per_step: int = 10`
- `allowed_effect_types: frozenset[str] | None = None` — None means all allowed
- `require_idempotency: bool = True`
- `stale_pending_timeout_seconds: float = 3600.0` — conservative default (1 hour). Must be >= 2x the maximum expected tool execution time. When a stale PENDING record is reclaimed, the system emits `EFFECT_STALE_RECLAIMED` event for audit.

### 5.5 EffectInterceptor

**File:** `miniautogen/core/effect_interceptor.py`

The central orchestrator. Wraps tool execution:

```
1. Check policy (max_effects, allowed_types)
   → EffectDeniedError if rejected
2. Compute idempotency_key = SHA-256(run_id + step_id + tool_name + args_hash)
3. Lookup journal
   → If COMPLETED: return cached result, emit EFFECT_SKIPPED
   → If PENDING + stale (age > stale_pending_timeout_seconds):
     emit EFFECT_STALE_RECLAIMED, treat as crashed, proceed
   → If PENDING + fresh: raise EffectDuplicateError (concurrent execution detected)
4. Register PENDING in journal, emit EFFECT_REGISTERED
5. Execute tool
6. On success: update COMPLETED, emit EFFECT_EXECUTED
7. On failure: update FAILED, emit EFFECT_FAILED
```

**Integration:** Optional middleware. `PipelineRunner` unchanged. Users wrap tool calls through the interceptor when they need idempotency. Not forced on all executions.

**Audit mode for unprotected retries:** When supervision (Phase 3) triggers a RESTART, a `_retry_attempt` flag is set in `RunContext.metadata`. If a tool call occurs during a retry without going through EffectInterceptor, the runtime emits `EFFECT_UNPROTECTED` at WARNING level. This makes gaps visible without forcing the interceptor on all operations.

**SHA-256 args hashing:** Uses `json.dumps(args, sort_keys=True)` (not orjson) for canonical key ordering. orjson preserves insertion order which is non-deterministic for idempotency key computation. The `_json` shim is for serialization performance; idempotency hashing needs determinism.

### 5.6 New Event Types

Add to `miniautogen/core/events/types.py`:

```python
EFFECT_REGISTERED = "effect_registered"
EFFECT_EXECUTED = "effect_executed"
EFFECT_SKIPPED = "effect_skipped"
EFFECT_FAILED = "effect_failed"
EFFECT_DENIED = "effect_denied"
EFFECT_STALE_RECLAIMED = "effect_stale_reclaimed"
EFFECT_UNPROTECTED = "effect_unprotected"
```

Plus convenience set `EFFECT_EVENT_TYPES` using enum members (not `.value` strings). Also normalize existing `AGENTIC_LOOP_EVENT_TYPES` and `BACKEND_EVENT_TYPES` to use enum members for consistency with `APPROVAL_EVENT_TYPES` and `DELIBERATION_EVENT_TYPES`.

### 5.7 What is NOT in Phase 2

- `SQLAlchemyEffectJournal` — requires shared SQLAlchemy Base (Phase 4)
- `EffectPolicyEvaluator` for PolicyChain — PolicyChain itself isn't wired (Phase 4)
- Automatic interception of all tool calls — opt-in only

### Success Criteria
- `EffectInterceptor` prevents duplicate execution in tests (register → skip on retry)
- Stale PENDING records are detected, `EFFECT_STALE_RECLAIMED` emitted, and re-executed
- All 7 event types emitted at correct lifecycle points (including STALE_RECLAIMED and UNPROTECTED)
- Policy enforcement blocks disallowed effect types and respects per-step limits

---

## 6. Phase 3 — Supervision Core

### Goal
Replace flat try/except with hierarchical fault supervision in WorkflowRuntime.

**Scope limitation:** Phase 3 supervision provides **in-process retry only**. If the process crashes mid-workflow, there is no per-step checkpoint — the entire workflow re-executes from step 1 on recovery. Crash recovery with per-step resume requires Phase 4 (`CheckpointManager`). Steps that have destructive side effects SHOULD use `EffectInterceptor` (Phase 2) to prevent duplicate execution on restart.

### 6.1 Supervisor Protocol

**File:** `miniautogen/core/runtime/supervisors.py`

```python
@runtime_checkable
class Supervisor(Protocol):
    async def handle_failure(
        self,
        *,
        child_id: str,
        error: BaseException,
        error_category: ErrorCategory,
        supervision: StepSupervision,
        restart_count: int,
    ) -> SupervisionDecision: ...
```

### 6.2 StepSupervisor

**File:** `miniautogen/core/runtime/supervisors.py`

Decision algorithm (priority order):
1. **Forced override by error category:**
   - `PERMANENT` → STOP (never retry programming errors)
   - `VALIDATION` → STOP (input is wrong)
   - `CONFIGURATION` → ESCALATE (needs human)
   - `STATE_CONSISTENCY` → ESCALATE (data integrity)
2. **Circuit breaker:** total failures >= `circuit_breaker_threshold` → STOP. Circuit breaker is **cumulative** (not windowed) — protects against intermittent failures over long workflows.
3. **Restart budget:** restarts within `restart_window_seconds` >= `max_restarts` → ESCALATE. Windowed — allows fresh restart budget after the window expires.
4. **Configured strategy:** apply `supervision.strategy`. If `RESUME` is configured, raise `NotImplementedError("RESUME requires Phase 4 CheckpointManager")` — fail explicitly rather than silently ignoring.

Internal state:
- `_failure_counts: dict[str, int]` — per child_id, cumulative (never reset)
- `_restart_timestamps: dict[str, list[datetime]]` — for windowed restart counting

**Audit trail requirements for every supervision decision:**
- `SUPERVISION_FAILURE_RECEIVED` event payload MUST include: exception type (qualified name), error category, exception message (sanitized — no PII/secrets), attempt number, step_id
- `SUPERVISION_DECISION_MADE` event payload MUST include: action, reason, restart_count, was_forced_override (bool)
- When a step succeeds after retry, emit `SUPERVISION_RETRY_SUCCEEDED` with total_attempts and error_categories_encountered
- All supervision events MUST also be logged via structlog at WARNING (retries) or ERROR (escalations/stops) — events are in-memory until Phase 4, logs are the durable fallback

### 6.3 FlowSupervisor

**File:** `miniautogen/core/runtime/flow_supervisor.py`

Manages a collection of StepSupervisors:
- Creates StepSupervisor per step on demand
- Tracks `total_flow_failures` across all steps
- Flow-level circuit breaker (default threshold: 10)
- Escalations from steps propagate up

### 6.4 Supervision Field on WorkflowStep

**File:** `miniautogen/core/contracts/coordination.py`

```python
class WorkflowStep(MiniAutoGenBaseModel):
    component_name: str
    agent_id: str | None = None
    config: dict[str, Any] = {}
    supervision: StepSupervision | None = None  # NEW
```

`WorkflowPlan` gains `default_supervision: StepSupervision | None = None` as fallback.

Resolution order: step.supervision > plan.default_supervision > system default (ESCALATE).

### 6.5 WorkflowRuntime Integration

**File:** `miniautogen/core/runtime/workflow_runtime.py`

Current sequential execution loop gains supervision wrapping:

```python
# Before (flat try/except):
try:
    result = await agent.process(input)
except Exception as exc:
    return RunResult(status=RunStatus.FAILED, error=str(exc))

# After (supervised):
supervisor = FlowSupervisor(event_sink=self._runner.event_sink)
for step in plan.steps:
    restart_count = 0
    while True:
        try:
            result = await agent.process(input)
            break  # success
        except BaseException as exc:
            if not isinstance(exc, Exception):
                raise  # Let KeyboardInterrupt, SystemExit, CancelledError propagate
            category = classify_error(exc)
            decision = await supervisor.handle_step_failure(
                step_id=step.component_name,
                error=exc,
                error_category=category,
                supervision=step.supervision or plan.default_supervision,
                restart_count=restart_count,
            )
            if decision.action == SupervisionStrategy.RESTART:
                restart_count += 1
                continue
            elif decision.action == SupervisionStrategy.STOP:
                return RunResult(status=RunStatus.FAILED, ...)
            elif decision.action == SupervisionStrategy.ESCALATE:
                return RunResult(status=RunStatus.FAILED, ...)
            # RESUME not supported without per-step checkpointing (Phase 4)
```

Fan-out steps: each parallel branch gets its own StepSupervisor. Failure in one branch does not cancel siblings unless FlowSupervisor's circuit breaker opens.

### 6.6 New Event Types

Add to `miniautogen/core/events/types.py`:

```python
SUPERVISION_FAILURE_RECEIVED = "supervision_failure_received"
SUPERVISION_DECISION_MADE = "supervision_decision_made"
SUPERVISION_RESTART_STARTED = "supervision_restart_started"
SUPERVISION_CIRCUIT_OPENED = "supervision_circuit_opened"
SUPERVISION_ESCALATED = "supervision_escalated"
SUPERVISION_RETRY_SUCCEEDED = "supervision_retry_succeeded"
```

Plus convenience set `SUPERVISION_EVENT_TYPES` using enum members.

### 6.7 What is NOT in Phase 3

- `CheckpointManager` with atomic transitions — requires shared SQLAlchemy Base (Phase 4)
- `HeartbeatToken` / watchdog — nice-to-have, not core (Phase 4)
- `EventStore` durável — requires shared SQLAlchemy Base (Phase 4)
- `RESUME` strategy implementation — requires per-step checkpointing (Phase 4)
- Supervision in `DeliberationRuntime` and `AgenticLoopRuntime` — starts with WorkflowRuntime only

### Success Criteria
- Step with `max_restarts=2` restarts transient failures up to 2 times, then escalates
- `PERMANENT` error forces STOP regardless of configured strategy
- Circuit breaker opens at threshold, emits `SUPERVISION_CIRCUIT_OPENED`
- All supervision decisions emit events
- Fan-out steps with different supervision strategies work independently
- Existing tests continue passing (backward compatible: no supervision field = ESCALATE on error)
- `WorkflowStep` deserialized from existing stored JSON (without supervision field) produces `supervision=None`

---

## 7. Phase 4 — Infrastructure Debt

### Goal
Resolve structural gaps that blocked durable/atomic features in Phases 2-3.

### 7.1 Unified SQLAlchemy Base

**File:** `miniautogen/stores/_base.py`

Single `Base(DeclarativeBase)` shared by all SQLAlchemy stores. All existing stores migrated to use it (`sqlalchemy_run_store.py`, `sqlalchemy_checkpoint_store.py`, `sqlalchemy.py`). Enables shared sessions, foreign keys, and transactions.

### 7.2 SQLAlchemyEffectJournal

**File:** `miniautogen/stores/sqlalchemy_effect_journal.py`

Durable implementation of `EffectJournal` ABC using shared Base.

### 7.3 EventStore

**ABC file:** `miniautogen/stores/event_store.py`
**InMemory file:** `miniautogen/stores/in_memory_event_store.py`
**SQLAlchemy file:** `miniautogen/stores/sqlalchemy_event_store.py`

Append-only durable event log:
- `append(run_id, event) -> None`
- `list_events(run_id, after_index) -> list[ExecutionEvent]`
- `count_events(run_id) -> int`

### 7.4 CheckpointManager

**File:** `miniautogen/core/runtime/checkpoint_manager.py`

Atomic checkpoint + events within a single transaction:

```python
async def atomic_transition(
    self,
    run_id: str,
    *,
    new_state: dict[str, Any],
    events: list[ExecutionEvent],
    step_index: int,
) -> None:
    # Single transaction: save checkpoint + append events + update step pointer
```

Enables `RESUME` strategy in supervision (load last checkpoint, skip completed steps).

### 7.5 HeartbeatToken & Watchdog

**File:** `miniautogen/core/runtime/heartbeat.py`

Injected into `RunContext.metadata`. Agent calls `token.beat()` to signal liveness. Watchdog task cancels scope if heartbeat interval exceeded.

### 7.6 PolicyChain Wiring

Connect `PolicyChain` to `PipelineRunner` as middleware evaluator. Wire `BudgetTracker`, `ValidationPolicy`, `TimeoutScope` through the chain. This finally aligns implementation with the CLAUDE.md "lateral, event-driven policies" vision.

### Success Criteria
- All SQLAlchemy stores share one `Base` and one session factory
- `atomic_transition` either commits all (checkpoint + events) or rolls back all
- `RESUME` strategy works: supervisor restarts from last checkpointed step
- HeartbeatToken kills zombie agents within configured interval
- PolicyChain evaluates before pipeline execution

---

## 8. File Map Summary

### Phase 1 (Foundation)
| Action | File |
|--------|------|
| Modify | `miniautogen/core/contracts/enums.py` |
| Create | `miniautogen/core/contracts/effect.py` |
| Commit | `miniautogen/core/contracts/supervision.py` (existing untracked) |
| Create | `miniautogen/core/runtime/classifier.py` |
| Commit | `tests/core/contracts/test_effect_foundation.py` (existing untracked) |
| Create | `tests/core/runtime/test_classifier.py` |
| Modify | `miniautogen/core/contracts/__init__.py` |

### Phase 2 (Effect Engine)
| Action | File |
|--------|------|
| Modify | `miniautogen/core/contracts/effect.py` |
| Create | `miniautogen/stores/effect_journal.py` |
| Create | `miniautogen/stores/in_memory_effect_journal.py` |
| Create | `miniautogen/policies/effect.py` |
| Create | `miniautogen/core/effect_interceptor.py` |
| Modify | `miniautogen/core/events/types.py` |

### Phase 3 (Supervision Core)
| Action | File |
|--------|------|
| Create | `miniautogen/core/runtime/supervisors.py` |
| Create | `miniautogen/core/runtime/flow_supervisor.py` |
| Modify | `miniautogen/core/contracts/coordination.py` |
| Modify | `miniautogen/core/runtime/workflow_runtime.py` |
| Modify | `miniautogen/core/events/types.py` |

### Phase 4 (Infrastructure Debt)
| Action | File |
|--------|------|
| Create | `miniautogen/stores/_base.py` |
| Modify | `miniautogen/stores/sqlalchemy_run_store.py` |
| Modify | `miniautogen/stores/sqlalchemy_checkpoint_store.py` |
| Modify | `miniautogen/stores/sqlalchemy.py` (current MessageStore location) |
| Create | `miniautogen/stores/sqlalchemy_effect_journal.py` |
| Create | `miniautogen/stores/event_store.py` |
| Create | `miniautogen/stores/in_memory_event_store.py` |
| Create | `miniautogen/stores/sqlalchemy_event_store.py` |
| Create | `miniautogen/core/runtime/checkpoint_manager.py` |
| Create | `miniautogen/core/runtime/heartbeat.py` |
| Modify | `miniautogen/core/runtime/pipeline_runner.py` |
| Modify | `miniautogen/policies/chain.py` |

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Phase 3 modifies WorkflowRuntime execution loop | Could break existing workflow tests | Backward compatible: no supervision field = current behavior (fail-fast) |
| Phase 3 supervision is in-process only (no crash recovery) | False sense of reliability if undocumented | Explicit doc: RESTART is in-process retry. Crash recovery requires Phase 4. Steps with side effects should use EffectInterceptor |
| Phase 4 SQLAlchemy Base unification | Could break existing SQL stores | Migration script + comprehensive store round-trip tests exist (WS1) |
| EffectInterceptor adds latency to tool calls | Performance degradation | Optional middleware, not forced on all executions |
| classify_error() misclassifies library-specific exceptions | httpx/aiohttp timeouts → PERMANENT by default | `register_error_mapping()` in Phase 1 for user-extensible classification |
| Stale PENDING race condition (slow-but-alive execution) | Duplicate execution of the operation the system is designed to prevent | Default 1h timeout, `EFFECT_STALE_RECLAIMED` audit event, HeartbeatToken in Phase 4 for definitive liveness detection |
| Unprotected tool calls during supervision retries | Duplicate side effects if developer forgets EffectInterceptor | `EFFECT_UNPROTECTED` warning event + structlog WARNING during retries. Audit mode, not enforcement |
| Phase 3 RESUME strategy deferred | Users configure RESUME, get undefined behavior | `NotImplementedError` raised explicitly if RESUME configured before Phase 4 |
| Circuit breaker per-flow (not shared) | Thundering herd: N concurrent flows × threshold failures before all breakers open | Acceptable for single-process. Shared registry in Phase 4 for multi-worker deployments |

---

## 10. Non-Goals (Explicit Exclusions)

- **Multi-process effect deduplication.** InMemory journal is per-process. Distributed deduplication requires external stores (Redis, PostgreSQL) which are out of scope.
- **Automatic tool interception.** EffectInterceptor is opt-in. Automatic wrapping of all ToolProtocol calls would require runtime changes that increase complexity disproportionately.
- **Cross-run supervision state.** Circuit breaker state is per-flow, not persisted. A new run starts with fresh counters.
- **DeliberationRuntime / AgenticLoopRuntime supervision.** Phase 3 targets WorkflowRuntime only. Other runtimes can be added incrementally after the pattern is proven.
- **Event-driven policy reactions.** Phase 4 wires PolicyChain but keeps it as synchronous middleware, not async event subscriptions. True reactive policies would require event bus infrastructure that doesn't exist yet.
