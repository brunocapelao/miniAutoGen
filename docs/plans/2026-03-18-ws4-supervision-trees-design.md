# WS4: Supervision Trees --- Design Spec

**Status:** Draft
**Author:** Engineering
**Date:** 2026-03-18
**Depends on:** WS2 (Frozen RunContext), WS3 (Effect Journal)

---

## Summary

This workstream introduces hierarchical fault supervision and atomic checkpointing
into MiniAutoGen's runtime layer. The goal is to enforce two core invariants:

- **Invariant 2 (Fault Delegation):** An agent never recovers from its own critical
  failures. Errors propagate upward to a Supervisor with enough context to decide
  between restart, resume, stop, or escalate.
- **Invariant 3 (Step Transactionality):** A flow's state transition is only valid
  when the new state, emitted events, and execution pointer are persisted atomically.

The design replaces the current flat `try/except` error handling with a structured
supervision tree, and replaces the non-atomic checkpoint-then-emit pattern with a
transactional `CheckpointManager`.

---

## Motivation (Why)

### 1. Flat error handling cannot express hierarchical recovery

Every runtime today (`WorkflowRuntime`, `AgenticLoopRuntime`, `DeliberationRuntime`,
`CompositeRuntime`) follows the same pattern: catch `Exception`, log it, emit a
`RUN_FAILED` event, and return `RunResult(status=FAILED)`. There is no mechanism to:

- Retry a single failed step while the rest of the flow continues.
- Restart a step with fresh state after a transient failure.
- Escalate from a step supervisor to a flow supervisor to a system supervisor.
- Apply different recovery strategies to different steps in the same plan.

For example, in `WorkflowRuntime._run_sequential` (line 146), if step 3 of 5 fails,
the entire workflow fails. There is no way to say "retry step 3 up to 3 times, then
skip it and continue" or "restart step 3 with a different agent."

### 2. Checkpoint and event emission are not atomic

In `PipelineRunner.run_pipeline` (lines 209-222), the checkpoint save and event
publish are separate `await` calls:

```python
if self.checkpoint_store is not None:
    await self.checkpoint_store.save_checkpoint(current_run_id, result)
# ... then separately ...
await self.event_sink.publish(ExecutionEvent(...))
```

If the process crashes between these two calls, the system is in an inconsistent
state: the checkpoint exists but the `RUN_FINISHED` event was never emitted, or
vice versa. This breaks replay safety and makes durable execution unreliable.

### 3. No zombie prevention

The `AgenticLoopRuntime` has a timeout (`anyio.fail_after`), but there is no circuit
breaker, no heartbeat protocol for long-running agents, and no max-lifetime
enforcement. A misbehaving agent that hangs just below the timeout threshold can
consume resources indefinitely across repeated invocations.

### 4. CompositeRuntime fail-fast is the only strategy

`CompositeRuntime` (line 117) checks `if result.status == RunStatus.FAILED` and
returns immediately. This is correct for some workflows but wrong for others. A
supervision tree lets the caller configure per-step behavior rather than hard-coding
fail-fast.

---

## Current State (What Exists)

| Component | File | Role | Limitation |
|---|---|---|---|
| `PipelineRunner` | `core/runtime/pipeline_runner.py` | Central executor with retry, timeout, checkpoint, events | Flat try/except; non-atomic checkpoint+event |
| `WorkflowRuntime` | `core/runtime/workflow_runtime.py` | Sequential/fan-out step execution | Entire workflow fails on any step error |
| `AgenticLoopRuntime` | `core/runtime/agentic_loop_runtime.py` | Router-driven conversation loop | Timeout only; no per-turn recovery |
| `DeliberationRuntime` | `core/runtime/deliberation_runtime.py` | Multi-round deliberation with peer review | Each phase failure kills the entire run |
| `CompositeRuntime` | `core/runtime/composite_runtime.py` | Sequential composition of coordination modes | Hard-coded fail-fast |
| `SessionRecovery` | `core/runtime/recovery.py` | Load checkpoint and mark run as resumed | No atomic guarantees; no strategy selection |
| `CheckpointStore` | `stores/checkpoint_store.py` | ABC for checkpoint persistence | No transaction concept |
| `RetryPolicy` | `policies/retry.py` | Tenacity-based retry wrapper | Applied to entire pipeline, not per-step |
| `ExecutionPolicy` | `policies/execution.py` | Timeout-only policy | No supervision strategy |

### Error taxonomy (from CLAUDE.md)

The canonical error categories are: `transient`, `permanent`, `validation`,
`timeout`, `cancellation`, `adapter`, `configuration`, `state_consistency`. These
categories are referenced across the codebase but are not yet formalized into an
enum or base exception hierarchy. This workstream depends on them being classifiable
so that the supervisor can map error categories to strategies.

#### ErrorCategory Enum (Shared Dependency: WS3 + WS4)

A `StrEnum` must be added to `miniautogen/core/contracts/enums.py` before either
WS3 or WS4 implementation begins. This is a shared dependency.

```python
from enum import StrEnum

class ErrorCategory(StrEnum):
    """Canonical error categories for supervision and effect journaling."""

    TRANSIENT         = "transient"
    PERMANENT         = "permanent"
    VALIDATION        = "validation"
    TIMEOUT           = "timeout"
    CANCELLATION      = "cancellation"
    ADAPTER           = "adapter"
    CONFIGURATION     = "configuration"
    STATE_CONSISTENCY = "state_consistency"
```

**Exception-to-Category mapping reference:**

| Category | Common Python Exceptions |
|---|---|
| `transient` | `ConnectionError`, `httpx.TimeoutException`, `aiosqlite.OperationalError` |
| `permanent` | `ValueError`, `TypeError`, `KeyError` (in agent logic) |
| `validation` | `pydantic.ValidationError` |
| `timeout` | `TimeoutError`, `anyio.get_cancelled_exc_class()` (when from deadline) |
| `cancellation` | `asyncio.CancelledError`, AnyIO cancellation (`Cancelled`) |
| `adapter` | `ImportError` (missing provider), provider-specific SDK errors |
| `configuration` | `KeyError` (missing config key), `FileNotFoundError` |
| `state_consistency` | Custom `StateConsistencyError` (to be defined in `core/contracts/errors.py`) |

The `classify_error` function (Section 2.5) uses this enum as its return type
instead of raw strings.

---

## 1. StepSupervision Model

### 1.1 Strategy Enum

```python
class SupervisionStrategy(str, Enum):
    """What the supervisor does when a child fails."""
    RESTART  = "restart"   # Re-run the step with fresh state
    RESUME   = "resume"    # Re-run the step from its last checkpoint
    STOP     = "stop"      # Terminate the step and the parent flow
    ESCALATE = "escalate"  # Propagate the error to the parent supervisor
```

### 1.2 StepSupervision Configuration

```python
class StepSupervision(BaseModel):
    model_config = ConfigDict(frozen=True)

    strategy: SupervisionStrategy = SupervisionStrategy.ESCALATE
    max_restarts: int = 3
    restart_window_seconds: float = 60.0
    circuit_breaker_threshold: int = 5
    heartbeat_interval_seconds: float | None = None
    max_lifetime_seconds: float | None = None
```

**Field semantics:**

| Field | Purpose |
|---|---|
| `strategy` | Default recovery action for this step |
| `max_restarts` | Maximum restart attempts within the restart window |
| `restart_window_seconds` | Sliding window for counting restarts |
| `circuit_breaker_threshold` | After N total failures (across all windows), switch to STOP |
| `heartbeat_interval_seconds` | If set, the step must report liveness at this interval or be killed |
| `max_lifetime_seconds` | Absolute wall-clock limit for the step, independent of the flow timeout |

### 1.3 Attachment Points

`StepSupervision` attaches at three levels, with inner levels overriding outer:

1. **Flow-level default** --- on `WorkflowPlan`, `AgenticLoopPlan`, `DeliberationPlan`:
   ```python
   class WorkflowPlan(CoordinationPlan):
       steps: list[WorkflowStep]
       fan_out: bool = False
       synthesis_agent: str | None = None
       default_supervision: StepSupervision = StepSupervision()  # NEW
   ```

2. **Step-level override** --- on `WorkflowStep`:
   ```python
   class WorkflowStep(BaseModel):
       component_name: str
       agent_id: str | None = None
       config: dict[str, Any] = Field(default_factory=dict)
       supervision: StepSupervision | None = None  # NEW: overrides plan default
   ```

3. **Agent-level default** --- on `AgentSpec` (optional, lowest priority):
   ```python
   class AgentSpec(BaseModel):
       # ... existing fields ...
       supervision: StepSupervision | None = None  # NEW
   ```

Resolution order: step-level > flow-level > agent-level > system default (ESCALATE).

### 1.4 Strategy-to-Error Mapping

Not every error should trigger the same strategy. The supervisor uses the error
taxonomy to override the configured strategy when appropriate:

| Error Category | Default Override | Rationale |
|---|---|---|
| `transient` | Use configured strategy | Transient errors are the primary restart candidate |
| `permanent` | Force STOP | No point retrying a permanent failure |
| `validation` | Force STOP | Input is wrong; retrying won't fix it |
| `timeout` | Use configured strategy | May succeed on retry with different conditions |
| `cancellation` | Force STOP | Explicit cancellation is intentional |
| `adapter` | Use configured strategy | External service may recover |
| `configuration` | Force ESCALATE | Needs human/system-level intervention |
| `state_consistency` | Force ESCALATE | Data integrity issue; unsafe to retry |

---

## 2. Supervisor Protocol

### 2.1 Hierarchy

```
SystemSupervisor (singleton, top-level)
  |
  +-- FlowSupervisor (one per CompositeRuntime / top-level run)
        |
        +-- StepSupervisor (one per WorkflowStep / AgenticLoop turn / Deliberation phase)
              |
              +-- AgentSupervisor (one per agent invocation within a step)
```

Each level follows the same protocol but has different scope:

- **AgentSupervisor** --- supervises a single `agent.process()` / `agent.reply()` /
  `agent.contribute()` call. Owns the cancel scope for that call.
- **StepSupervisor** --- supervises one step (which may contain multiple agent calls
  in fan-out). Owns restart counting and circuit breaker state.
- **FlowSupervisor** --- supervises the sequence of steps. Receives escalations from
  StepSupervisors. Decides whether the flow can continue after a step failure.
- **SystemSupervisor** --- receives escalations that no flow can handle. Responsible
  for logging, alerting, and graceful shutdown.

### 2.2 Supervisor Protocol Definition

```python
@runtime_checkable
class Supervisor(Protocol):
    """Receives errors from children and decides on a recovery action."""

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

```python
class SupervisionDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    action: SupervisionStrategy
    reason: str
    should_checkpoint: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
```

### 2.3 Decision Algorithm

The `StepSupervisor.handle_failure` implementation follows this logic:

```
1. Classify the error into a canonical category.
2. Check if the error category forces an override (see table in 1.4).
   - If forced to STOP or ESCALATE, return that immediately.
3. Check circuit breaker:
   - If total_failures >= circuit_breaker_threshold, return STOP.
4. Check restart budget:
   - Count restarts within the restart_window_seconds.
   - If restarts_in_window >= max_restarts, return ESCALATE.
5. Apply the configured strategy:
   - RESTART: increment restart counter, return RESTART.
   - RESUME: look up last checkpoint, return RESUME if checkpoint exists, else RESTART.
   - STOP: return STOP.
   - ESCALATE: propagate to parent supervisor.
```

### 2.4 FlowSupervisor Decision Algorithm

The `FlowSupervisor.handle_escalation` receives failures escalated from
`StepSupervisor` instances. It owns aggregate state across all steps in a flow.

**Owned state:**

- `total_flow_failures: int` --- count of all failures across all steps.
- `step_completion_map: dict[str, StepStatus]` --- tracks each step's terminal
  status (pending, running, completed, failed, skipped).
- `flow_circuit_breaker_threshold: int` --- configurable; default 10.

**Algorithm:**

```
1. Receive escalation from StepSupervisor:
   - step_id, error, error_category, exhausted_strategy
2. Increment total_flow_failures.
3. Check flow-level circuit breaker:
   - If total_flow_failures >= flow_circuit_breaker_threshold:
     → STOP the entire flow.
     → Emit SUPERVISION_CIRCUIT_OPEN event (flow-level).
     → Cancel all running step scopes.
     → Return.
4. Inspect the exhausted_strategy from the StepSupervisor:
   - If exhausted_strategy == ESCALATE:
     → Propagate to SystemSupervisor.
   - If exhausted_strategy == STOP:
     → Mark step as FAILED in step_completion_map.
     → If remaining steps are independent (fan-out or no data dependency):
       continue executing remaining steps.
     → If remaining steps depend on the failed step:
       STOP the entire flow.
5. Emit SUPERVISION_FLOW_DECISION event with:
   - step_id, decision, total_flow_failures, step_completion_map snapshot.
```

**Key distinction:** The StepSupervisor owns per-step state (restart count,
per-step circuit breaker). The FlowSupervisor owns aggregate state (total
failures across all steps, step completion map).

### 2.5 Integration with Existing Error Taxonomy

The supervisor needs a way to classify arbitrary exceptions into the canonical
categories. This requires a small classifier function:

```python
def classify_error(exc: BaseException) -> ErrorCategory:
    """Map an exception to a canonical ErrorCategory."""
```

Classification rules (in priority order):

1. If the exception has an `error_category` attribute, use it directly.
2. If it is a `TimeoutError` or `anyio.get_cancelled_exc_class()`, return `ErrorCategory.TIMEOUT` or `ErrorCategory.CANCELLATION`.
3. If it matches known adapter exception base classes, return `ErrorCategory.ADAPTER`.
4. If it is a `pydantic.ValidationError`, return `ErrorCategory.VALIDATION`.
5. Default: `ErrorCategory.TRANSIENT` (optimistic --- the supervisor's strategy-to-error mapping will catch permanent failures that self-identify).

Long-term, all framework exceptions should carry an `error_category` attribute.
This is a migration, not a prerequisite.

### 2.6 Event Emissions

The supervisor emits events at each decision point. New event types required:

```python
# New EventType members
SUPERVISION_FAILURE_RECEIVED = "supervision_failure_received"
SUPERVISION_DECISION_MADE    = "supervision_decision_made"
SUPERVISION_RESTART_STARTED  = "supervision_restart_started"
SUPERVISION_CIRCUIT_OPENED   = "supervision_circuit_opened"
SUPERVISION_ESCALATED        = "supervision_escalated"
```

---

## 3. Atomic Checkpoint (CheckpointManager)

### 3.1 Problem Statement

The current flow is:

```
save_checkpoint(run_id, result)  # await 1
event_sink.publish(RUN_FINISHED) # await 2
```

A crash between await 1 and await 2 leaves the system in an inconsistent state.
The `SessionRecovery` class in `recovery.py` can detect a checkpoint but has no way
to know whether the corresponding events were emitted.

### 3.2 Transaction Wrapper Design

```python
class CheckpointManager:
    """Wraps state + events + pointer into a single atomic transition."""

    def __init__(
        self,
        checkpoint_store: CheckpointStore,
        event_store: EventStore,   # NEW: append-only event persistence
        event_sink: EventSink,     # existing: for live pub/sub notification
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
        """Persist state, events, and pointer atomically.

        For SQL-backed stores, this uses a database transaction.
        For in-memory stores, this is a simple sequential write
        (atomicity is trivial in single-threaded async).
        """
        async with self._store.transaction() as txn:
            await txn.save_checkpoint(run_id, {
                "state": new_state,
                "step_index": step_index,
                "transition_id": str(uuid4()),
            })
            for event in events:
                await self._event_store.append(run_id, event)

        # After the transaction commits, fan out to live subscribers.
        # This is fire-and-forget: if pub/sub fails, the events are
        # already durably stored and can be replayed.
        for event in events:
            try:
                await self._sink.publish(event)
            except Exception:
                pass  # Logged by the sink; durable store is the source of truth
```

### 3.3 What Constitutes an Atomic Transition

An atomic transition is the unit of durable state change. It must include:

| Component | Purpose | Current Location |
|---|---|---|
| **Checkpoint payload** | Serialized `RunContext` + step outputs | `CheckpointStore.save_checkpoint` |
| **Step index / pointer** | Which step the flow is about to execute next | Not tracked today |
| **Emitted events** | All events generated during this step | `EventSink.publish` (non-durable) |

The step index is critical for resume: after a crash, the system loads the last
checkpoint, reads the step index, and resumes from that point.

**Atomic transition boundaries:**

```
Step N executes
  → Step N completes successfully
  → atomic_transition(step_index=N, new_state=..., events=[...])
      writes checkpoint + events + step_index in one transaction
  → step_index is now N (meaning "step N is complete")
  → Next iteration: execute step N+1

On crash DURING step N execution (before atomic_transition):
  → Last checkpoint has step_index = N-1
  → Resume reads step_index = N-1
  → Restarts from step N (= step_index + 1)
```

The checkpoint is saved AFTER step N completes successfully (post-step).
The `step_index` in the checkpoint represents the last *completed* step, not the
next step to execute. On resume: `next_step = last_checkpoint.step_index + 1`.

### 3.4 CheckpointStore Transaction Extension

The `CheckpointStore` ABC needs a `transaction()` context manager. This is a
non-breaking addition (default implementation can be a no-op passthrough):

```python
class CheckpointStore(ABC):
    # ... existing methods ...

    @contextlib.asynccontextmanager
    async def transaction(self) -> AsyncIterator[CheckpointStore]:
        """Yield a transactional view of this store.

        Default: yields self (no-op transaction, suitable for in-memory).
        SQL implementations override to use a database transaction.
        """
        yield self
```

### 3.5 SQLAlchemy Transaction Integration

`SQLAlchemyCheckpointStore` already uses `session.begin()` for individual operations.
The `transaction()` method would hold a single session open across multiple
operations:

```python
@contextlib.asynccontextmanager
async def transaction(self) -> AsyncIterator[CheckpointStore]:
    async with self.async_session() as session:
        async with session.begin():
            txn_store = _SQLAlchemyTransactionalView(session)
            yield txn_store
            # commit happens when session.begin() exits cleanly
```

### 3.6 EventStore (New ABC)

A durable, append-only store for events. Distinct from `EventSink` (which is
pub/sub for live notification).

```python
class EventStore(ABC):
    @abstractmethod
    async def append(self, run_id: str, event: ExecutionEvent) -> None:
        """Durably append an event. Assigns a monotonic event_id."""

    @abstractmethod
    async def list_events(
        self, run_id: str, *, after_index: int = 0
    ) -> list[ExecutionEvent]:
        """Return events with event_id > after_index, ordered by event_id ASC."""

    @abstractmethod
    async def count_events(self, run_id: str) -> int:
        """Return the total number of events for a run (for pagination)."""
```

**Operational semantics:**

| Property | Guarantee |
|---|---|
| **Append model** | Append-only; events are never updated or deleted |
| **Ordering** | Each event receives a monotonic auto-increment `event_id` (int). Ordering is guaranteed by `event_id` ASC |
| **Concurrency** | Writes are serialized within a transaction (SQLAlchemy session lock for SQL backends; GIL-trivial for in-memory) |
| **`list_events` contract** | Returns all events where `event_id > after_index`, ordered by `event_id` ASC. If `after_index=0`, returns all events |
| **`count_events` contract** | Returns `int` count for the given `run_id`. Used for pagination and progress tracking |
| **Compaction / snapshotting** | Deferred to Phase 3 (event log snapshotting). For now the log grows unbounded per run. A future compaction strategy will collapse old events into a snapshot marker |

This is required for replay safety (WS3 dependency) and for the atomic transition
to include events in the same database transaction as the checkpoint.

### 3.7 InMemory Implementation for Tests

```python
class InMemoryCheckpointManager:
    """Test double: sequential writes are atomic in single-threaded async."""
```

No special transaction handling needed. The `transaction()` context manager on
`InMemoryCheckpointStore` simply yields `self`.

---

## 4. AnyIO Integration

### 4.1 TaskGroup Patterns for Fan-Out Supervision

`WorkflowRuntime._run_fan_out` already uses `anyio.create_task_group()`. The
supervision layer wraps each branch in a supervised scope:

```python
async with anyio.create_task_group() as tg:
    for i, step in enumerate(plan.steps):
        supervision = resolve_supervision(step, plan)
        tg.start_soon(
            supervised_step,
            step_supervisor, step, supervision, i,
        )
```

The `supervised_step` function wraps the agent call in a cancel scope and delegates
failures to the `StepSupervisor`:

```python
async def supervised_step(
    supervisor: StepSupervisor,
    step: WorkflowStep,
    supervision: StepSupervision,
    index: int,
) -> None:
    restart_count = 0
    while True:
        try:
            with anyio.CancelScope() as scope:
                if supervision.max_lifetime_seconds:
                    scope.deadline = anyio.current_time() + supervision.max_lifetime_seconds
                result = await invoke_agent(step)
                return result
        except BaseException as exc:
            decision = await supervisor.handle_failure(
                child_id=step.component_name,
                error=exc,
                error_category=classify_error(exc),
                supervision=supervision,
                restart_count=restart_count,
            )
            if decision.action == SupervisionStrategy.RESTART:
                restart_count += 1
                continue
            elif decision.action == SupervisionStrategy.STOP:
                return  # Let the task group continue without this branch
            elif decision.action == SupervisionStrategy.ESCALATE:
                raise
```

### 4.2 CancelScope for Per-Step Timeouts

Today, `PipelineRunner` applies a single timeout to the entire pipeline. With
supervision, each step gets its own cancel scope:

- `StepSupervision.max_lifetime_seconds` sets the scope deadline.
- The flow-level timeout (from `ExecutionPolicy.timeout_seconds`) remains as an
  outer cancel scope wrapping all steps.
- AnyIO's structured cancellation guarantees that cancelling an outer scope
  automatically cancels all inner scopes.

### 4.3 Structured Cancellation Propagation

AnyIO's task group semantics already handle this correctly:

- If a step raises inside a task group, all sibling tasks are cancelled.
- The supervision layer intercepts the exception *before* it propagates to the
  task group, allowing restart/resume without cancelling siblings.
- If the decision is ESCALATE, the exception propagates normally, triggering
  AnyIO's built-in cancellation of siblings.

**Key constraint:** The supervisor's `handle_failure` must be called *inside* the
task but *outside* the cancel scope, so that the supervisor itself is not subject
to the step's timeout.

### 4.4 Cancel Scope Nesting Diagram

The full nesting includes the ApprovalGate (if present), which runs OUTSIDE the
FlowSupervisor scope. The FlowSupervisor scope starts only AFTER approval is
granted. This is important because the approval wait time should not count toward
the flow's timeout budget.

```
[ApprovalGate --- no timeout, waits for human/system approval]
  |
  → Approval granted
  |
  [FlowSupervisor cancel scope --- ExecutionPolicy.timeout_seconds]
    |
    +-- [StepSupervisor cancel scope --- StepSupervision.max_lifetime_seconds]
    |     |
    |     +-- [Watchdog task (if heartbeat enabled)]
    |     +-- [Agent invocation]
    |
    +-- [StepSupervisor cancel scope]
    |     |
    |     +-- [Agent invocation]
    ...
```

**Without ApprovalGate** (the common case), the diagram starts directly at the
FlowSupervisor cancel scope.

---

## 5. Zombie Prevention

### 5.1 Circuit Breaker Pattern

The circuit breaker is per-step, tracked by the `StepSupervisor`. It uses a simple
counter model (not a full state machine with half-open state), because steps are
not long-lived services:

```
total_failures = 0

on_failure:
    total_failures += 1
    if total_failures >= circuit_breaker_threshold:
        return STOP  # Circuit is open --- refuse to execute
    else:
        apply normal supervision strategy
```

The circuit breaker threshold is configured via `StepSupervision.circuit_breaker_threshold`
(default: 5). It persists only for the lifetime of the flow run. Cross-run circuit
breaker state is out of scope for this workstream.

### 5.2 Heartbeat Protocol for Long-Running Agents

For agents that run extended operations (e.g., multi-turn LLM conversations,
long tool executions), the supervisor can require periodic liveness signals:

```python
class HeartbeatToken:
    """Passed to agents that opt into heartbeat supervision."""

    async def beat(self) -> None:
        """Signal liveness. Must be called within heartbeat_interval_seconds."""
```

**HeartbeatToken distribution:**

The token is injected into `RunContext.metadata["_heartbeat_token"]`. The agent
obtains it via `context.metadata.get("_heartbeat_token")` and calls `token.beat()`
periodically. Agents that do not call `beat()` will be killed by the watchdog
after `2 * heartbeat_interval_seconds`.

**Watchdog task lifecycle:**

1. Created by `StepSupervisor` when the step starts and
   `heartbeat_interval_seconds is not None`.
2. Runs in a **separate task within the step's `TaskGroup`** (sibling to the
   agent task, inside the same cancel scope).
3. Loop: sleep for `heartbeat_interval_seconds`, then check `last_beat` timestamp.
4. If `now - last_beat > heartbeat_interval_seconds * 2`, cancel the step's
   `CancelScope` (triggering a `TimeoutError` classified as `"timeout"`).
5. When the agent task completes normally, the watchdog is cancelled automatically
   by AnyIO's structured concurrency (TaskGroup exit cancels all children).

```python
async def _watchdog(
    token: HeartbeatToken,
    scope: anyio.CancelScope,
    interval: float,
) -> None:
    """Background task that monitors agent liveness."""
    while True:
        await anyio.sleep(interval)
        elapsed = anyio.current_time() - token.last_beat_time
        if elapsed > interval * 2:
            scope.cancel()  # Kill the agent's cancel scope
            return
```

**Integration example:**

```python
async def supervised_step_with_heartbeat(
    step: WorkflowStep,
    supervision: StepSupervision,
    context: RunContext,
) -> Any:
    token = HeartbeatToken()
    context = context.model_copy(
        update={"metadata": {**context.metadata, "_heartbeat_token": token}}
    )
    async with anyio.create_task_group() as tg:
        with anyio.CancelScope() as scope:
            if supervision.heartbeat_interval_seconds:
                tg.start_soon(
                    _watchdog, token, scope, supervision.heartbeat_interval_seconds
                )
            result = await invoke_agent(step, context)
            tg.cancel_scope.cancel()  # Stop the watchdog
            return result
```

### 5.3 Max Lifetime Enforcement

`StepSupervision.max_lifetime_seconds` is enforced via `anyio.CancelScope.deadline`.
This is distinct from the flow-level timeout:

- **Flow timeout** (from `ExecutionPolicy`): total time for the entire run.
- **Step lifetime** (from `StepSupervision`): maximum time for a single step,
  including all restart attempts.

If `max_lifetime_seconds` is reached, the supervisor receives a `TimeoutError`
classified as `"timeout"` and applies the configured strategy.

### 5.4 Resource Cleanup on Crash

When a step is cancelled (via cancel scope or circuit breaker), the supervisor
must ensure cleanup:

1. **Cancel scope exit** --- AnyIO guarantees that `finally` blocks run in
   cancelled tasks. Agents should use `async with` for resource cleanup.
2. **Checkpoint rollback** --- If the step was mid-transition, the atomic
   checkpoint ensures no partial state is persisted. The last valid checkpoint
   remains intact.
3. **Event emission** --- The supervisor emits a `SUPERVISION_DECISION_MADE` event
   with the action taken, so observability is not lost even on crash.
4. **Task group cleanup** --- AnyIO's `create_task_group` guarantees that all child
   tasks are awaited before the group exits, preventing orphaned coroutines.

---

## Interaction with Other Workstreams

### WS2: Frozen RunContext

- `StepSupervision` is a frozen Pydantic model (`ConfigDict(frozen=True)`),
  consistent with WS2's immutability requirement.
- The `CheckpointManager.atomic_transition` accepts `dict[str, Any]` for state
  (serialized from `RunContext.model_dump()`). When WS2 finalizes the frozen
  `RunContext`, the manager will serialize it directly.

**`step_index` field dependency:**

The step index / execution pointer will be a field on `RunContext` added by WS2:

```python
class RunContext(BaseModel):
    # ... existing fields ...
    step_index: int = 0  # 0 = before any step executes
```

- **Initial value:** `0` (before any step executes).
- **Serialization:** Included in `model_dump()` naturally as a Pydantic field.
- **Interim strategy:** If WS2 is not complete when WS4 implementation begins,
  WS4 stores `step_index` inside the checkpoint payload directly:
  `checkpoint_payload["step_index"]`. When WS2 lands, this migrates to
  `RunContext.step_index` with no behavioral change (the atomic_transition
  method already receives `step_index` as an explicit parameter).

### WS3: Effect Journal

- The `EventStore` introduced in this workstream (Section 3.6) is the same
  append-only journal that WS3 needs for replay safety.
- Atomic transitions guarantee that the journal and checkpoint are always
  consistent, which is a prerequisite for deterministic replay.
- The `CheckpointManager` is the write path; WS3's replay engine is the read path.

### Existing Components

- **`SessionRecovery`** (`recovery.py`) becomes a thin wrapper around
  `CheckpointManager.load_last_transition()`, gaining atomic guarantees.
- **`RetryPolicy`** (`policies/retry.py`) continues to work at the pipeline level.
  `StepSupervision` operates at the step level. They are complementary, not
  competing. The retry policy handles retries *within* a single step execution;
  supervision handles what happens *after* a step definitively fails.
- **`ExecutionPolicy`** (`policies/execution.py`) remains the flow-level timeout
  source. The supervision tree adds per-step timeouts on top of it.

---

## Success Criteria

1. **SC-1:** A `WorkflowPlan` with 5 steps, where step 3 is configured with
   `strategy="restart", max_restarts=2`, successfully restarts step 3 up to 2
   times on transient failure before escalating.

2. **SC-2:** A crash between checkpoint save and event emit (simulated by raising
   after `save_checkpoint`) does not leave the system in an inconsistent state.
   Recovery loads the checkpoint and replays missing events from the durable
   `EventStore`.

3. **SC-3:** A step configured with `circuit_breaker_threshold=3` transitions to
   STOP after 3 total failures, regardless of the configured strategy.

4. **SC-4:** A step configured with `heartbeat_interval_seconds=5.0` is killed if
   the agent does not call `beat()` within 5 seconds.

5. **SC-5:** Fan-out steps in `WorkflowRuntime` can have independent supervision
   strategies. A failing branch does not cancel sibling branches when the strategy
   is RESTART (only ESCALATE cancels siblings).

6. **SC-6:** All supervision decisions emit the appropriate `SUPERVISION_*` events
   and are visible in structured logs.

7. **SC-7:** The `CheckpointManager.atomic_transition` passes with both
   `InMemoryCheckpointStore` and `SQLAlchemyCheckpointStore` backends, with
   transaction rollback verified on the SQL path.

---

## Estimated Effort

| Component | Effort | Notes |
|---|---|---|
| `StepSupervision` model + attachment | Small | Pydantic models, plan extensions |
| Error classifier (`classify_error`) | Small | Pattern matching on exception types |
| `Supervisor` protocol + `StepSupervisor` impl | Medium | Core decision algorithm, restart tracking |
| `FlowSupervisor` + `SystemSupervisor` | Medium | Escalation chain, integration with runtimes |
| `CheckpointStore.transaction()` extension | Small | ABC addition + in-memory no-op |
| `EventStore` ABC + in-memory impl | Small | New ABC, simple implementation |
| `CheckpointManager` | Medium | Transaction orchestration, event fan-out |
| SQLAlchemy transaction integration | Medium | Shared session across checkpoint + events |
| AnyIO supervised step wrapper | Medium | Cancel scope management, restart loop |
| Heartbeat protocol | Small | Watchdog task + token |
| Circuit breaker | Small | Counter with threshold |
| Runtime integration (Workflow, AgenticLoop, Deliberation, Composite) | Large | Threading supervision through all runtimes |
| New `EventType` members | Small | Enum additions |
| Tests | Large | Success criteria coverage, crash simulation |

**Total estimate:** 3-4 weeks for a single engineer, assuming WS2 and WS3
foundations are in place. The runtime integration (last row) is the bulk of the
work because each runtime has its own execution loop that must be refactored to
use supervised steps.

---

## Migration Path

This workstream is **backward-compatible**. The default `StepSupervision` uses
`strategy="escalate"`, which preserves the current behavior (errors propagate up
and fail the run). Existing code that does not set supervision will behave
identically.

Migration steps:

1. Add `StepSupervision` model and `Supervisor` protocol (no runtime changes).
2. Add `CheckpointStore.transaction()` with no-op default (no behavioral change).
3. Implement `CheckpointManager` and `EventStore`.
4. Refactor `PipelineRunner` to use `CheckpointManager` (replaces lines 209-222).
5. Add `supervised_step` wrapper and `StepSupervisor`.
6. Refactor `WorkflowRuntime` to use supervised steps.
7. Extend to `AgenticLoopRuntime`, `DeliberationRuntime`, `CompositeRuntime`.
8. Add heartbeat and circuit breaker (optional features, off by default).

Each step is independently deployable and testable.
