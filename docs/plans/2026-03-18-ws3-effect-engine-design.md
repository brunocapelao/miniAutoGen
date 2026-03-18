# WS3: Effect Engine -- Design Spec

**Workstream:** 3 -- Effect Engine (EffectPolicy + Idempotency)
**Status:** Draft
**Date:** 2026-03-18
**Invariant:** #4 -- Controlled Side Effects (Strict Idempotency)

---

## Summary

Every interaction with the external world (API calls, database writes, tool invocations) must be governed by an `EffectPolicy` and have an `idempotency_key` registered in an Effect Journal before execution. This workstream introduces the Effect Engine: a lateral policy subsystem that intercepts side-effecting operations, records intent before execution, and prevents duplicate effects on replay or retry.

---

## Motivation (Why)

Today, MiniAutoGen tool calls have **no deduplication**. If a run fails mid-execution and is replayed from a checkpoint, every tool call executes again -- including those that already succeeded. For pure computations this is harmless. For real-world operations (sending emails, charging credit cards, creating resources via APIs), replay causes **duplicate side effects** that cannot be reversed.

The existing `RetryPolicy` compounds the problem: a transient failure triggers re-execution of the entire step, including tool calls that already completed successfully within that step.

Concrete failure scenarios without the Effect Engine:

1. **Double purchase.** Agent calls a payment API, network timeout occurs after the payment succeeds but before the response arrives. Retry re-sends the payment.
2. **Duplicate notification.** Agent sends a Slack message, then the next tool call fails. Checkpoint restore replays the entire step, sending the message again.
3. **Phantom resource creation.** Agent provisions a cloud resource, run is cancelled, later resumed. The provisioning call runs again, creating a second resource.

The Effect Engine eliminates these classes of bugs by making side effects **observable, deduplicated, and auditable**.

---

## Current State

### Policies (8 existing, no effect governance)

| Policy | Module | Purpose |
|--------|--------|---------|
| `ExecutionPolicy` | `policies/execution.py` | Timeout configuration (frozen dataclass) |
| `BudgetPolicy` | `policies/budget.py` | Cost limits with `BudgetTracker` (frozen dataclass) |
| `RetryPolicy` | `policies/retry.py` | Retry attempts with tenacity (frozen dataclass) |
| `ApprovalPolicy` | `policies/approval.py` | Human-in-the-loop gates (frozen dataclass) |
| `PermissionPolicy` | `policies/permission.py` | Action allow/deny lists (frozen dataclass) |
| `ValidationPolicy` | `policies/validation.py` | Input/output validation |
| `TimeoutScope` | `policies/timeout.py` | Scoped timeout management |
| `PolicyChain` | `policies/chain.py` | Composition via `PolicyEvaluator` protocol |

All policies use frozen dataclasses or frozen Pydantic models. Policies operate laterally -- they observe and constrain but do not own the execution flow. The `PolicyChain` composes evaluators via a `PolicyEvaluator` protocol with `evaluate(context) -> PolicyResult`.

### Stores (ABC + InMemory + SQLAlchemy pattern)

The codebase follows a consistent store pattern:

- **ABC** in `stores/checkpoint_store.py` and `stores/run_store.py` -- defines the contract
- **InMemory** implementation in `stores/in_memory_checkpoint_store.py` -- dict-backed, for testing
- **SQLAlchemy** implementation in `stores/sqlalchemy_checkpoint_store.py` -- async engine, `DeclarativeBase` ORM model, JSON payload column

### Events (47+ types, EventSink protocol)

- `ExecutionEvent` is a Pydantic `BaseModel` with `type`, `timestamp`, `run_id`, `correlation_id`, `scope`, `payload`
- `EventSink` protocol exposes `async publish(event: ExecutionEvent) -> None`
- Composition via `CompositeEventSink`, filtering via `FilteredEventSink`
- Event types are grouped by category in `EventType` enum (e.g., `TOOL_INVOKED`, `TOOL_SUCCEEDED`, `TOOL_FAILED` for tool lifecycle)

### Gap

- No `EffectPolicy` exists
- No idempotency mechanism exists
- No Effect Journal or store exists
- Tool calls execute unconditionally with no deduplication
- No event types exist for effect lifecycle tracking

---

## Target Architecture

### Overview

The Effect Engine consists of four components that integrate with the existing architecture without modifying the core execution flow:

```
                          PolicyChain
                              |
                     +--------+--------+
                     |                 |
              EffectPolicy      (other policies)
                     |
              EffectInterceptor
               /           \
     EffectJournal      EventSink
     (persistence)      (observability)
```

The `EffectInterceptor` sits at the boundary where the runtime dispatches tool calls. Before any side-effecting operation:

1. Generate an `idempotency_key`
2. Check the `EffectJournal` for a prior execution with that key
3. If found and completed: skip execution, return cached result, emit `EFFECT_SKIPPED`
4. If not found: register intent as `pending`, execute, record outcome

---

### 1. EffectPolicy

A frozen configuration model that governs what effects are allowed and how they are tracked. Follows the existing policy pattern (frozen dataclass/model, no runtime state).

```python
@dataclass(frozen=True)
class EffectPolicy:
    """Governs side-effect execution and idempotency requirements."""

    # Maximum side effects permitted in a single pipeline step.
    # Prevents runaway tool-call loops from causing unbounded damage.
    max_effects_per_step: int = 10

    # Effect types that are permitted. Any effect whose type is not
    # in this set will be denied. Empty frozenset means "allow all".
    allowed_effect_types: frozenset[str] = frozenset()

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

**Integration with PolicyChain.** The `EffectPolicy` is a configuration object, not a `PolicyEvaluator`. The `EffectInterceptor` (see section 4) reads the policy to make decisions. This mirrors how `BudgetPolicy` configures `BudgetTracker` -- the policy is data, the tracker is behavior.

However, for integration with the `PolicyChain` composition model, an `EffectPolicyEvaluator` adapter is also provided:

```python
class EffectPolicyEvaluator:
    """Adapts EffectPolicy for use in a PolicyChain.

    Evaluates whether a proposed action is permitted under the
    current effect policy (type allowed, budget not exceeded).
    Implements the PolicyEvaluator protocol.
    """

    def __init__(self, policy: EffectPolicy, journal: EffectJournal) -> None: ...

    async def evaluate(self, context: PolicyContext) -> PolicyResult:
        # 1. Check if effect type is in allowed_effect_types
        # 2. Check if max_effects_per_step would be exceeded
        # 3. Return proceed/deny with reason
        ...
```

**Configuration options summary:**

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `max_effects_per_step` | `int` | `10` | Caps side effects per step to prevent runaway loops |
| `allowed_effect_types` | `frozenset[str]` | `frozenset()` (allow all) | Restricts which effect types can execute |
| `require_idempotency` | `bool` | `True` | Whether journal registration is mandatory before execution |
| `completed_ttl_seconds` | `float \| None` | `None` | Optional expiration for completed records |
| `stale_pending_timeout_seconds` | `float` | `300.0` | Max seconds a PENDING record can exist before being treated as stale |

#### PolicyContext Extensions

When the `EffectPolicyEvaluator` is invoked via the `PolicyChain`, the `PolicyContext` is populated as follows:

| Field | Value | Example |
|-------|-------|---------|
| `action` | The `effect_type` string from the descriptor | `"tool_call"`, `"api_request"`, `"db_write"` |
| `metadata` | Dict containing the full effect descriptor | `{"effect_descriptor": descriptor.model_dump()}` |

This allows the evaluator (and any other policy in the chain) to inspect the full effect details without coupling to `EffectDescriptor` directly.

---

### 2. EffectJournal (Store)

Persistent store for effect records. Follows the existing ABC + InMemory + SQLAlchemy pattern established by `CheckpointStore` and `RunStore`.

#### ABC Contract

```python
class EffectJournal(ABC):
    """Persistent journal for effect idempotency records."""

    @abstractmethod
    async def register(self, record: EffectRecord) -> None:
        """Register intent to execute an effect (status=pending).

        If a record with the same idempotency_key already exists,
        raises EffectAlreadyRegisteredError.
        """

    @abstractmethod
    async def get(self, idempotency_key: str) -> EffectRecord | None:
        """Fetch an effect record by its idempotency key."""

    @abstractmethod
    async def update_status(
        self,
        idempotency_key: str,
        status: EffectStatus,
        result_hash: str | None = None,
        error_info: str | None = None,
    ) -> None:
        """Update the status of a registered effect."""

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
        """

    @abstractmethod
    async def delete_by_run(self, run_id: str) -> int:
        """Delete all effect records for a run. Returns count deleted."""
```

#### InMemoryEffectJournal

Dict-backed implementation for testing. Keyed by `idempotency_key`.

```python
class InMemoryEffectJournal(EffectJournal):
    def __init__(self) -> None:
        self._records: dict[str, EffectRecord] = {}
```

#### SQLAlchemyEffectJournal

Async SQLAlchemy implementation following the pattern in `sqlalchemy_checkpoint_store.py`.

```python
class DBEffectRecord(Base):
    __tablename__ = "effect_journal"

    idempotency_key: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(String, index=True)
    step_id: Mapped[str] = mapped_column(String)
    effect_type: Mapped[str] = mapped_column(String)
    effect_descriptor_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String)  # pending | completed | failed
    result_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    error_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

#### Schema Design

The `effect_journal` table:

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| `idempotency_key` | `VARCHAR` | PRIMARY KEY | Unique identifier for this effect execution |
| `run_id` | `VARCHAR` | INDEX, NOT NULL | Associates effect with a pipeline run |
| `step_id` | `VARCHAR` | NOT NULL | Identifies the step within the run |
| `effect_type` | `VARCHAR` | NOT NULL | Classifies the effect (e.g., `tool_call`, `api_request`) |
| `effect_descriptor_json` | `TEXT` | NOT NULL | JSON-serialized effect descriptor (tool name, args hash, etc.) |
| `status` | `VARCHAR` | NOT NULL | One of: `pending`, `completed`, `failed` |
| `result_hash` | `VARCHAR` | NULLABLE | SHA-256 of the result payload (for verification on replay) |
| `error_info` | `TEXT` | NULLABLE | Error description if status is `failed` |
| `created_at` | `DATETIME` | NOT NULL | When the intent was registered |
| `completed_at` | `DATETIME` | NULLABLE | When execution completed or failed |

Composite index on `(run_id, status)` for efficient `list_by_run` queries with status filter.

---

### 3. Effect Protocol

#### EffectDescriptor

A typed, frozen model that declares the intent to perform a side effect. Created by the runtime before execution, it carries enough information to generate an idempotency key and to describe the effect for audit purposes.

```python
@dataclass(frozen=True)
class EffectDescriptor:
    """Declares the intent to perform a side-effecting operation."""

    effect_type: str          # e.g., "tool_call", "api_request", "db_write"
    tool_name: str            # e.g., "send_email", "create_order"
    args_hash: str            # SHA-256 of canonical JSON of arguments
    run_id: str               # Owning run
    step_id: str              # Owning step within the run
    metadata: dict[str, Any]  # Additional context (endpoint URL, etc.)
```

#### EffectRecord

The persisted record in the journal. Transitions through a strict lifecycle.

```python
class EffectStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass(frozen=True)
class EffectRecord:
    """Persisted record of an effect's lifecycle in the journal."""

    idempotency_key: str
    descriptor: EffectDescriptor
    status: EffectStatus
    created_at: datetime
    completed_at: datetime | None = None
    result_hash: str | None = None
    error_info: str | None = None
```

#### Effect Lifecycle

```
  [intent declared]
        |
        v
   +---------+     journal.register()     +----------+
   | (start) | -------------------------> | PENDING  |
   +---------+                             +----------+
                                            /        \
                              (success)    /          \  (failure)
                                          v            v
                                   +-----------+  +--------+
                                   | COMPLETED |  | FAILED |
                                   +-----------+  +--------+
```

State transitions:

| From | To | Trigger | Journal Operation |
|------|----|---------|-------------------|
| -- | `PENDING` | Intent registered before execution | `journal.register(record)` |
| `PENDING` | `COMPLETED` | Execution succeeded | `journal.update_status(key, COMPLETED, result_hash)` |
| `PENDING` | `FAILED` | Execution raised an exception | `journal.update_status(key, FAILED, error_info=...)` |

A `COMPLETED` record is terminal. A `FAILED` record is also terminal for that specific idempotency key. On retry, a new idempotency key is generated (incorporating the attempt number), so failed effects do not block re-execution.

#### Exception Types

The Effect Engine defines three exception types, each mapped to a category in the canonical error taxonomy (see `CLAUDE.md` section 4):

```python
class EffectDeniedError(MiniAutoGenError):
    """Raised when an effect is rejected by the EffectPolicy.

    Canonical category: validation
    Triggers: effect_type not in allowed_effect_types, or
              max_effects_per_step would be exceeded.
    """
    category = "validation"


class EffectDuplicateError(MiniAutoGenError):
    """Raised when registering an effect whose idempotency key
    already exists with status COMPLETED.

    Canonical category: state_consistency
    Triggers: journal.register() called with a key that is
              already in COMPLETED state.
    """
    category = "state_consistency"


class EffectJournalUnavailableError(MiniAutoGenError):
    """Raised when the EffectJournal store is unreachable.

    Canonical category: adapter
    Triggers: connection failure, timeout, or I/O error when
              communicating with the journal backend (e.g., database).
    """
    category = "adapter"
```

| Exception | Category | Raised When |
|-----------|----------|-------------|
| `EffectDeniedError` | `validation` | Effect type not in allowed list, or max effects per step exceeded |
| `EffectDuplicateError` | `state_consistency` | Idempotency key already exists with COMPLETED status |
| `EffectJournalUnavailableError` | `adapter` | Journal store unreachable (connection error, timeout) |

File placement: `miniautogen/core/contracts/effect.py` (alongside `EffectDescriptor`, `EffectRecord`, `EffectStatus`).

#### Idempotency Key Generation Strategy

The idempotency key must be **deterministic** for the same logical operation so that replays produce the same key:

```
idempotency_key = SHA-256(run_id + step_id + tool_name + args_hash + attempt_number)
```

Where `args_hash` is computed from a **canonical JSON serialization** of the tool arguments:

```python
import hashlib, json

def canonical_args_hash(args: dict) -> str:
    """Deterministic hash of tool arguments.

    Uses sorted keys and compact separators to ensure identical
    output for identical logical arguments regardless of dict ordering.
    The `default=str` fallback handles non-primitive types (e.g., datetime)
    by converting them to their string representation.
    """
    canonical = json.dumps(args, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()
```

This serialization is deterministic for all Python primitive types (`str`, `int`, `float`, `bool`, `None`, `list`, `dict`). Non-primitive types are coerced via `default=str`, which is stable but not invertible -- callers should prefer primitive arguments for maximum safety.

**Key properties:**

- **Same run, same step, same tool, same args, same attempt** -> same key (deduplication works)
- **Same run, same step, same tool, different args** -> different key (no false positives)
- **Different run** -> different key (runs do not interfere)
- **Same operation, different attempt** -> different key (retries get fresh keys)

#### Retry Counter and Attempt Tracking

The `attempt_number` component of the idempotency key tracks retry attempts. This is critical for allowing re-execution of failed effects while still deduplicating completed ones.

**Who increments the attempt counter?** The runtime's `RetryPolicy`. Each time the policy triggers a retry of a step, it increments the attempt counter.

**Where is it stored?** In the `RunContext.metadata` dict under the key `"attempt_number"` (integer, starting at 1). The `EffectInterceptor` reads this value when generating the idempotency key.

**How does it flow into the idempotency key?** The interceptor concatenates it as the final component before hashing:

```python
def generate_idempotency_key(descriptor: EffectDescriptor, attempt_number: int) -> str:
    raw = f"{descriptor.run_id}:{descriptor.step_id}:{descriptor.tool_name}:{descriptor.args_hash}:{attempt_number}"
    return hashlib.sha256(raw.encode()).hexdigest()
```

**Concrete example -- retry after transient failure:**

```
Attempt 1:
  key = SHA-256("run-abc:step-3:send_email:<args_hash>:1")
  -> register PENDING
  -> execute tool
  -> network timeout -> record FAILED
  -> emit EFFECT_FAILED

RetryPolicy triggers retry (attempt_number incremented to 2):

Attempt 2:
  key = SHA-256("run-abc:step-3:send_email:<args_hash>:2")  # different key!
  -> register PENDING (new key, no conflict with attempt 1)
  -> execute tool
  -> success -> record COMPLETED
  -> emit EFFECT_EXECUTED

If the run is replayed from checkpoint and reaches step-3 again:
  key = SHA-256("run-abc:step-3:send_email:<args_hash>:1")
  -> journal lookup -> FAILED (attempt 1) -> new retry key needed
  key = SHA-256("run-abc:step-3:send_email:<args_hash>:2")
  -> journal lookup -> COMPLETED -> skip execution, return cached result
  -> emit EFFECT_SKIPPED
```

This ensures failed effects do not block re-execution while completed effects remain deduplicated across replays.

---

### 4. Idempotency Interceptor

The `EffectInterceptor` is a **concrete class** that wraps tool execution calls. It does not inherit from or depend on any abstract interceptor protocol -- it is a self-contained middleware that the runtime composes around its tool dispatch path.

#### Class Signature

```python
class EffectInterceptor:
    """Wraps tool execution with idempotency checks and journal bookkeeping.

    The runtime calls `execute()` instead of invoking the tool directly.
    This method handles the full before/execute/after lifecycle.
    """

    def __init__(
        self,
        policy: EffectPolicy,
        journal: EffectJournal,
        event_sink: EventSink,
    ) -> None: ...

    async def execute(
        self,
        descriptor: EffectDescriptor,
        tool_fn: Callable[..., Awaitable[Any]],
        tool_args: dict[str, Any],
        attempt_number: int = 1,
    ) -> Any:
        """Execute a tool call with idempotency protection.

        1. Check policy (allowed type, budget)
        2. Check journal for prior execution
        3. Register intent as PENDING
        4. Call tool_fn(**tool_args)
        5. Record outcome (COMPLETED or FAILED)

        Returns the tool result (or cached result if duplicate).
        Raises EffectDeniedError if policy rejects the effect.
        """
        ...
```

#### Integration Point: How the Runtime Calls the Interceptor

The `EffectInterceptor` integrates as a **wrapper around tool dispatch**. The runtime holds a reference to the interceptor and delegates tool calls through it. This is not a decorator or monkey-patch; it is explicit composition:

```python
# In the runtime's tool dispatch path (pseudocode):

# WITHOUT Effect Engine (current behavior):
result = await tool_fn(**tool_args)

# WITH Effect Engine (new behavior):
descriptor = EffectDescriptor(
    effect_type="tool_call",
    tool_name=tool_name,
    args_hash=canonical_args_hash(tool_args),
    run_id=run_context.run_id,
    step_id=current_step_id,
    metadata={"endpoint": tool_fn.__name__},
)
attempt = run_context.metadata.get("attempt_number", 1)
result = await effect_interceptor.execute(descriptor, tool_fn, tool_args, attempt)
```

The interceptor is **optional**. If not configured, the runtime calls `tool_fn` directly (preserving backward compatibility). The runtime checks for the interceptor's presence:

```python
if self._effect_interceptor is not None:
    result = await self._effect_interceptor.execute(descriptor, tool_fn, tool_args, attempt)
else:
    result = await tool_fn(**tool_args)
```

#### Relationship to Existing Events

The interceptor operates at the boundary between the agent runtime and tool execution. It coordinates with the existing event flow:

- **`BACKEND_TOOL_CALL_REQUESTED`** -- emitted by the runtime before dispatching. The interceptor's `execute()` is called after this event.
- **Tool execution** -- the interceptor calls `tool_fn` internally and wraps it with journal bookkeeping.
- **`BACKEND_TOOL_CALL_EXECUTED`** -- emitted by the runtime after the interceptor returns. The interceptor has already recorded the outcome in the journal before this event fires.

#### Before/After Pattern

```
EffectInterceptor.before_execute(descriptor):
    1. Generate idempotency_key from descriptor
    2. Check EffectPolicy:
       - Is effect_type allowed? If not -> deny (raise EffectDeniedError)
       - Would max_effects_per_step be exceeded? If so -> deny
    3. Check EffectJournal:
       - journal.get(idempotency_key)
       - If found and COMPLETED -> return cached result, emit EFFECT_SKIPPED
       - If found and PENDING -> stale pending from prior crash, treat as new
       - If found and FAILED -> allow re-execution (new retry key)
       - If not found -> proceed
    4. Register intent:
       - journal.register(EffectRecord(key, descriptor, PENDING, now()))
       - Emit EFFECT_REGISTERED event

EffectInterceptor.after_execute(idempotency_key, result):
    1. Compute result_hash = SHA-256(canonical JSON of result)
    2. journal.update_status(key, COMPLETED, result_hash)
    3. Emit EFFECT_EXECUTED event

EffectInterceptor.on_failure(idempotency_key, error):
    1. journal.update_status(key, FAILED, error_info=str(error))
    2. Emit EFFECT_FAILED event
```

#### Duplicate Detection Flow

```
Tool call arrives
      |
      v
Generate idempotency_key
      |
      v
Query EffectJournal -----> Record found?
      |                        |
      | (no)                   | (yes)
      v                        v
Register PENDING          Check status
      |                    /    |    \
      v              COMPLETED PENDING FAILED
Execute tool          |        |       |
      |          Return    Clear &    New key
      v          cached   re-register  (retry)
Record result    result
```

#### Stale Pending Handling

A `PENDING` record whose `created_at` is older than `EffectPolicy.stale_pending_timeout_seconds` (default: 300 seconds / 5 minutes) is considered stale -- it indicates a prior crash where the execution never completed. The interceptor handles this by:

1. Checking `now() - record.created_at > policy.stale_pending_timeout_seconds`
2. If stale: logging a warning with the stale record details
3. Updating the record status to `FAILED` with `error_info="stale_pending_cleared"`
4. Proceeding with fresh registration under the current attempt's key

If the `PENDING` record is **not** stale (i.e., within the timeout window), the interceptor assumes another execution is in progress and raises `EffectDuplicateError` to prevent concurrent execution of the same effect.

This is safe because: if the original execution actually completed but the journal update was lost, the worst case is re-execution -- which is the same as having no idempotency at all. The journal provides best-effort deduplication, not distributed transaction guarantees.

---

### 5. Event Integration

#### New Event Types

Five new event types added to the `EventType` enum in `core/events/types.py`:

| Event | Value | Description |
|-------|-------|-------------|
| `EFFECT_REGISTERED` | `effect_registered` | Intent to execute a side effect recorded in journal |
| `EFFECT_EXECUTED` | `effect_executed` | Side effect executed successfully, result recorded |
| `EFFECT_SKIPPED` | `effect_skipped` | Duplicate detected, execution skipped, cached result returned |
| `EFFECT_FAILED` | `effect_failed` | Side effect execution failed, error recorded in journal |
| `EFFECT_DENIED` | `effect_denied` | EffectPolicy denied the effect (type not allowed or budget exceeded) |

Corresponding convenience set:

```python
EFFECT_EVENT_TYPES: set[EventType] = {
    EventType.EFFECT_REGISTERED,
    EventType.EFFECT_EXECUTED,
    EventType.EFFECT_SKIPPED,
    EventType.EFFECT_FAILED,
    EventType.EFFECT_DENIED,
}
```

#### Event Payloads

Each effect event carries a structured payload:

**EFFECT_REGISTERED:**
```python
{
    "idempotency_key": "sha256-...",
    "effect_type": "tool_call",
    "tool_name": "send_email",
    "run_id": "run-123",
    "step_id": "step-5",
}
```

**EFFECT_EXECUTED:**
```python
{
    "idempotency_key": "sha256-...",
    "effect_type": "tool_call",
    "tool_name": "send_email",
    "result_hash": "sha256-...",
    "duration_ms": 1450,
}
```

**EFFECT_SKIPPED:**
```python
{
    "idempotency_key": "sha256-...",
    "effect_type": "tool_call",
    "tool_name": "send_email",
    "reason": "duplicate_detected",
    "original_completed_at": "2026-03-18T14:30:00Z",
}
```

**EFFECT_FAILED:**
```python
{
    "idempotency_key": "sha256-...",
    "effect_type": "tool_call",
    "tool_name": "send_email",
    "error_category": "adapter",
    "error_info": "Connection refused",
}
```

**EFFECT_DENIED:**
```python
{
    "idempotency_key": "sha256-...",
    "effect_type": "db_write",
    "reason": "effect_type_not_allowed",
}
```

#### How Existing EventSink Consumers See Effects

Effect events flow through the standard `EventSink` pipeline. Existing consumers (`CompositeEventSink`, `FilteredEventSink`, `InMemoryEventSink`) require **no modifications**. Consumers that want to observe only effect events can use `FilteredEventSink` with a filter matching `EFFECT_EVENT_TYPES`.

The `BudgetTracker` pattern provides a precedent: a policy-specific observer that reacts to specific event types. An `EffectAuditor` can similarly subscribe to effect events for compliance logging.

---

## Interaction with Other Workstreams

### Depends on WS2 (Frozen State / Immutability)

- `EffectDescriptor` and `EffectRecord` are frozen dataclasses. If WS2 establishes a project-wide pattern for frozen value objects (e.g., a base class or mixin), these models should adopt it.
- `EffectPolicy` is a frozen dataclass, consistent with the existing policy pattern. WS2 may formalize this as a `FrozenPolicy` base.

### Feeds into WS4 (Supervision / Orchestration Awareness)

- Supervision needs to know which effects a run has executed. The `EffectJournal.list_by_run()` method provides this.
- A supervisor deciding whether to retry a failed run can inspect the journal to understand what effects already completed, avoiding unnecessary re-execution.
- The `EFFECT_DENIED` event may trigger supervisor escalation (e.g., if an agent repeatedly attempts disallowed effects).

### Relationship with Existing Tool Events

The effect event lifecycle **complements** the existing tool events (`TOOL_INVOKED`, `TOOL_SUCCEEDED`, `TOOL_FAILED`). Tool events describe what happened at the runtime level; effect events describe the idempotency and policy governance layer. Both are emitted for the same operation:

```
EFFECT_REGISTERED -> TOOL_INVOKED -> TOOL_SUCCEEDED -> EFFECT_EXECUTED
```

or:

```
EFFECT_REGISTERED -> TOOL_INVOKED -> TOOL_FAILED -> EFFECT_FAILED
```

or (duplicate):

```
EFFECT_SKIPPED  (no TOOL_* events -- execution was skipped)
```

---

## Success Criteria

1. **No duplicate effects on replay.** Given a run that fails after step N (where steps 1..N-1 included tool calls), replaying from checkpoint must skip already-completed effects and return their cached results.

2. **Journal-before-execution invariant.** Every side-effecting tool call must have a `PENDING` record in the `EffectJournal` before the tool function is invoked. Violation of this invariant is a `state_consistency` error.

3. **Policy enforcement.** Tool calls with disallowed `effect_type` or exceeding `max_effects_per_step` are denied before execution, with an `EFFECT_DENIED` event emitted.

4. **Full event observability.** Every effect lifecycle transition produces an `ExecutionEvent` visible to all `EventSink` consumers. An operator monitoring the event stream can reconstruct the complete effect history of any run.

5. **Store contract compliance.** `InMemoryEffectJournal` and `SQLAlchemyEffectJournal` both pass the same test suite, following the pattern established by `CheckpointStore` implementations.

6. **Zero core modifications.** The Effect Engine integrates via the existing lateral policy/interceptor/event architecture. No changes to `PipelineRunner`, `RunContext`, `RunResult`, or existing policies.

7. **Test coverage.** Unit tests for `EffectPolicy`, `EffectRecord` lifecycle, `EffectJournal` (both implementations), `EffectInterceptor` (including duplicate detection, stale pending, denied effects), and event emission.

---

## Estimated Effort

| Component | Size | Notes |
|-----------|------|-------|
| `EffectPolicy` + `EffectPolicyEvaluator` | Small | Frozen dataclass + adapter, follows existing pattern |
| `EffectDescriptor` + `EffectRecord` | Small | Frozen models, no behavior |
| `EffectJournal` ABC | Small | 5 abstract methods |
| `InMemoryEffectJournal` | Small | Dict-backed, for testing |
| `SQLAlchemyEffectJournal` | Medium | ORM model, async queries, follows existing SQLAlchemy pattern |
| `EffectInterceptor` | Medium | Core logic: key generation, journal check, before/after wrapping |
| Event types + payloads | Small | 5 new enum values, payload conventions |
| Test suite | Medium | Both journal implementations, interceptor scenarios, policy evaluation |
| **Total** | **Medium** | Estimated 3-5 days for implementation + tests |

---

## File Placement

Following existing project conventions:

| Artifact | Path |
|----------|------|
| `EffectPolicy` | `miniautogen/policies/effect.py` |
| `EffectPolicyEvaluator` | `miniautogen/policies/effect.py` |
| `EffectDescriptor`, `EffectRecord`, `EffectStatus` | `miniautogen/core/contracts/effect.py` |
| `EffectDeniedError`, `EffectDuplicateError`, `EffectJournalUnavailableError` | `miniautogen/core/contracts/effect.py` |
| `EffectJournal` (ABC) | `miniautogen/stores/effect_journal.py` |
| `InMemoryEffectJournal` | `miniautogen/stores/in_memory_effect_journal.py` |
| `SQLAlchemyEffectJournal` | `miniautogen/stores/sqlalchemy_effect_journal.py` |
| `EffectInterceptor` | `miniautogen/core/effect_interceptor.py` |
| New `EventType` entries | `miniautogen/core/events/types.py` (extend existing enum) |
| Tests | `tests/unit/test_effect_*.py` |
