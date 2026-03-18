# WS2: Immutable Core -- Design Spec

**Date:** 2026-03-18
**Status:** Draft
**Invariant:** Zero Shared Mutable State

---

## Summary

This workstream eliminates all shared mutable state from the MiniAutoGen core execution path. `RunContext` and `ExecutionEvent` become frozen Pydantic models. All runtimes adopt a copy-on-write propagation pattern. The result is a core that is safe under concurrent fan-out (`anyio.create_task_group`) by construction, not by convention.

---

## Motivation (Why)

MiniAutoGen's runtimes execute agents in parallel via AnyIO task groups. Today, `RunContext.execution_state` is a plain `dict[str, Any]` -- a mutable reference shared across concurrent branches. Nothing prevents two agents in a fan-out from mutating the same dictionary simultaneously, producing data races invisible to Python's GIL and impossible to reproduce deterministically.

The `ExecutionEvent` model mutates itself inside a Pydantic `model_validator`, which violates the principle that data objects should be immutable after construction.

These are not theoretical risks. They are structural defects that become exploitable bugs the moment real workloads exercise fan-out parallelism or event replay.

---

## Current State (What's broken)

### RunContext (`miniautogen/core/contracts/run_context.py`)

Two mutable fields exist on an otherwise well-structured model:

```python
execution_state: dict[str, Any] = Field(default_factory=dict)  # MUTABLE
metadata: dict[str, Any] = Field(default_factory=dict)          # MUTABLE
```

`with_previous_result()` already uses copy-on-write (`model_copy`), proving the pattern is viable. But nothing prevents callers from doing `context.execution_state["key"] = value` directly.

**Consumers of `execution_state`:**
- `miniautogen/compat/state_bridge.py` -- `bridge_chat_pipeline_state_to_run_context()` injects a mutable dict from legacy state into `execution_state`.
- Tests (`test_run_context.py`, `test_run_context_comprehensive.py`, `test_run_context_bridge.py`) read from and assert against `execution_state`.

**Consumers of `metadata`:**
- `RunContext.with_previous_result()` spreads `self.metadata` and adds `previous_result`.
- `CompositeRuntime` calls `with_previous_result()` to thread results between composition steps.

### ExecutionEvent (`miniautogen/core/contracts/events.py`)

```python
@model_validator(mode="after")
def infer_run_id_from_payload(self) -> "ExecutionEvent":
    if self.run_id is None and "run_id" in self.payload:
        payload_run_id = self.payload["run_id"]
        if isinstance(payload_run_id, str):
            self.run_id = payload_run_id  # MUTATES SELF
    return self
```

This validator writes to `self.run_id` after construction. The `payload` field is also a mutable `dict[str, Any]`.

### Runtime Mutation Patterns

**PipelineRunner** -- Does not use `RunContext` directly. Receives an opaque `state: Any` and passes it to `pipeline.run(state)`. No mutation of `RunContext` fields. Low migration risk.

**WorkflowRuntime** -- Reads `context.input_payload` in both `_run_sequential` and `_run_fan_out`. Does not mutate `RunContext`. The fan-out path shares `initial_input` (read from `context.input_payload`) across branches via closure capture, but only reads it. Low migration risk.

**AgenticLoopRuntime** -- Reads `context.run_id`, `context.correlation_id`, and `context.input_payload` (implicitly, via conversation seeding). Does not mutate `RunContext` fields. Loop state is maintained in a local `AgenticLoopState` variable that is reassigned (not mutated) each turn. Low migration risk.

**DeliberationRuntime** -- Reads `context.run_id` and `context.correlation_id`. Does not mutate `RunContext`. Internal loop state (`DeliberationState`, `contributions`, `follow_ups`) is local to the `run()` method scope. Low migration risk.

**CompositeRuntime** -- The primary consumer of `RunContext` mutability. Calls `current_context.with_previous_result(result.output)` to produce a new context per step, and also supports `step.input_mapper(result, current_context)` for custom transformations. The `current_context` variable is reassigned, not mutated. Already follows copy-on-write. **Zero migration risk.**

**Key finding:** None of the runtimes mutate `execution_state` or `metadata` in-place. The mutation risk comes from external consumers (compat bridge, user code) that could write to these dicts after construction.

---

## Target State (What it becomes)

### 1. Frozen RunContext

```python
from pydantic import BaseModel, ConfigDict
from types import MappingProxyType
from typing import Any
from datetime import datetime


class FrozenState(BaseModel):
    """Typed, immutable state container replacing execution_state.

    Stores arbitrary key-value pairs as a tuple of pairs,
    ensuring no mutation after construction.
    """
    model_config = ConfigDict(frozen=True)

    _data: tuple[tuple[str, Any], ...] = ()

    def __init__(self, **kwargs: Any) -> None:
        pairs = tuple(sorted(kwargs.items()))
        super().__init__(_data=pairs)

    def get(self, key: str, default: Any = None) -> Any:
        for k, v in self._data:
            if k == key:
                return v
        return default

    def evolve(self, **updates: Any) -> "FrozenState":
        current = dict(self._data)
        current.update(updates)
        return FrozenState(**current)

    def to_dict(self) -> dict[str, Any]:
        return dict(self._data)


class RunContext(BaseModel):
    """Typed, frozen execution context for a single framework run."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    started_at: datetime
    correlation_id: str
    state: FrozenState = FrozenState()          # replaces execution_state
    input_payload: Any = None
    timeout_seconds: float | None = None
    namespace: str | None = None
    metadata: tuple[tuple[str, Any], ...] = ()   # replaces mutable dict

    def with_state(self, **updates: Any) -> "RunContext":
        """Return a new RunContext with state evolved by the given updates."""
        new_state = self.state.evolve(**updates)
        return self.model_copy(update={"state": new_state})

    def with_previous_result(self, result: Any) -> "RunContext":
        """Return a new RunContext with the previous result injected."""
        new_metadata = dict(self.metadata)
        new_metadata["previous_result"] = result
        return self.model_copy(
            update={
                "input_payload": result,
                "metadata": tuple(sorted(new_metadata.items())),
            },
        )

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Look up a metadata key without exposing the internal tuple."""
        for k, v in self.metadata:
            if k == key:
                return v
        return default
```

**Design decisions:**

- `FrozenState` uses a tuple-of-tuples internally. This is hashable, serializable by Pydantic, and avoids the complexity of `MappingProxyType` (which Pydantic cannot serialize natively).
- `metadata` follows the same tuple-of-tuples pattern for consistency.
- `with_state()` is the single mutation pathway -- it returns a new `RunContext`.
- `with_previous_result()` is preserved for backward compatibility with `CompositeRuntime`.
- `get_metadata()` provides ergonomic read access without dict unpacking.
- The `execution_state` field name is retired. `state` is shorter and the type (`FrozenState`) communicates intent.

**Migration path for `execution_state` consumers:**

| Current code | Replacement |
|---|---|
| `ctx.execution_state["key"]` | `ctx.state.get("key")` |
| `ctx.execution_state["key"] = val` | `ctx = ctx.with_state(key=val)` |
| `RunContext(execution_state={"k": "v"})` | `RunContext(state=FrozenState(k="v"))` |
| `ctx.metadata["key"]` | `ctx.get_metadata("key")` |
| `{**ctx.metadata, "k": "v"}` | `tuple(sorted({**dict(ctx.metadata), "k": "v"}.items()))` |

### 2. Frozen ExecutionEvent

```python
class ExecutionEvent(BaseModel):
    """Canonical execution event emitted by the runtime."""

    model_config = ConfigDict(frozen=True)

    type: str = Field(
        validation_alias=AliasChoices("type", "event_type"),
        serialization_alias="type",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        validation_alias=AliasChoices("timestamp", "created_at"),
        serialization_alias="timestamp",
    )
    run_id: str | None = None
    correlation_id: str | None = None
    scope: str | None = None
    payload: tuple[tuple[str, Any], ...] = ()

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    def __init__(self, **data: Any) -> None:
        # Infer run_id from payload before freezing
        raw_payload = data.get("payload", {})
        if isinstance(raw_payload, dict):
            data["payload"] = tuple(sorted(raw_payload.items()))
            if data.get("run_id") is None and "run_id" in raw_payload:
                candidate = raw_payload["run_id"]
                if isinstance(candidate, str):
                    data["run_id"] = candidate
        super().__init__(**data)

    @property
    def event_type(self) -> str:
        return self.type

    @property
    def created_at(self) -> datetime:
        return self.timestamp

    def get_payload(self, key: str, default: Any = None) -> Any:
        for k, v in self.payload:
            if k == key:
                return v
        return default
```

**Key changes:**

- The `model_validator` that mutated `self.run_id` is replaced by `__init__` logic that resolves `run_id` **before** calling `super().__init__()`, so the object is never mutated after construction.
- `payload` becomes `tuple[tuple[str, Any], ...]`. All runtime `_emit()` helpers currently pass `dict` payloads -- these are converted in `__init__`.
- `get_payload()` provides ergonomic access.

**Impact on EventSink consumers:**

All five runtimes construct `ExecutionEvent` with `payload={"key": "value"}` dict literals. The `__init__` override converts these transparently. No changes needed at call sites.

EventSink subscribers that read `event.payload["key"]` must migrate to `event.get_payload("key")` or `dict(event.payload)["key"]`. This is a breaking change for external consumers.

### 3. Runtime Migration

#### PipelineRunner

**Current pattern:** Does not interact with `RunContext` at all. Receives opaque `state: Any`.

**Migration:** None required. PipelineRunner is already compatible.

#### WorkflowRuntime

**Current pattern:** Reads `context.input_payload` and `context.run_id` / `context.correlation_id`. No mutation.

```python
# _run_sequential (line 145)
current_input = context.input_payload

# _run_fan_out (line 158)
initial_input = context.input_payload
```

**Migration:** None required. All access is read-only on fields that do not change type.

#### AgenticLoopRuntime

**Current pattern:** Reads `context.run_id`, `context.correlation_id`. Internal state is managed via local `AgenticLoopState` variable that is reassigned each turn (line 192):

```python
state = AgenticLoopState(
    active_agent=agent_id,
    turn_count=state.turn_count + 1,
    accepted_output=reply,
)
```

**Migration:** None required. The runtime already follows reassignment-not-mutation for its internal state. If `AgenticLoopState` should also be frozen, that is a separate concern (it is local, never shared).

#### DeliberationRuntime

**Current pattern:** Reads `context.run_id`, `context.correlation_id`. Internal state (`DeliberationState`, `contributions`, `reviews`) is local to the `run()` method.

**Migration:** None required. The runtime does not mutate `RunContext`.

#### CompositeRuntime

**Current pattern:** This is the most sophisticated consumer. It calls `with_previous_result()` to thread results:

```python
# line 96
current_context = current_context.with_previous_result(result.output)
```

And supports custom `input_mapper` functions:

```python
# line 94
current_context = step.input_mapper(result, current_context)
```

**Migration:** `with_previous_result()` is preserved with the same signature. Custom `input_mapper` functions must return a frozen `RunContext` -- since they already return `RunContext` today, and the new `RunContext` is constructed frozen, this is enforced by the type system. **No code changes needed** in the runtime itself. Custom `input_mapper` implementations that mutate the returned context will fail at runtime (Pydantic `frozen=True` raises `ValidationError` on attribute assignment).

### 4. Frozen Metadata

**Options evaluated:**

| Approach | Hashable | Pydantic-serializable | Ergonomic | Nested-safe |
|---|---|---|---|---|
| `tuple[tuple[str, Any], ...]` | Yes | Yes | Medium | No (inner values can be mutable) |
| `MappingProxyType` | No | No (needs custom serializer) | High | No |
| Typed Pydantic model | Yes (if frozen) | Yes | High | Yes |
| `frozenset[tuple[str, Any]]` | Yes | Yes | Low (unordered) | No |

**Recommendation: `tuple[tuple[str, Any], ...]` for both `RunContext.metadata` and `ExecutionEvent.payload`.**

Rationale:

1. **Consistency** -- Same representation for `FrozenState._data`, `metadata`, and `payload`. One pattern to learn.
2. **Serialization** -- Pydantic handles tuples natively. No custom validators or serializers.
3. **Hashability** -- Enables use as dict keys or in sets if needed for caching/dedup.
4. **Simplicity** -- No new dependencies, no complex type machinery.

The main trade-off is ergonomics: `dict(ctx.metadata)` is needed for dict-like access. The `get_metadata()` and `get_payload()` helpers mitigate this for the common single-key-lookup case.

**Nested mutability caveat:** The `Any` in `tuple[str, Any]` means inner values could be mutable (e.g., a list). For Phase 1, we accept this and rely on convention. Phase 2 could introduce a `freeze()` utility that deep-freezes values, but this adds complexity and is not required for the primary invariant (no shared mutable *references* between actors).

---

## Breaking Changes

| Change | Severity | Affected code |
|---|---|---|
| `execution_state` field renamed to `state` (type `FrozenState`) | **High** | `compat/state_bridge.py`, all tests referencing `execution_state`, user code |
| `metadata` field type changes from `dict` to `tuple[tuple[str, Any], ...]` | **Medium** | `RunContext.with_previous_result()` (internal, updated), user code that reads `ctx.metadata["key"]` |
| `ExecutionEvent.payload` type changes from `dict` to `tuple[tuple[str, Any], ...]` | **Medium** | EventSink subscribers that read `event.payload["key"]` |
| `RunContext` and `ExecutionEvent` become frozen (attribute assignment raises) | **Medium** | Any code that assigns `ctx.some_field = value` or `event.run_id = value` |
| `RunResult.metadata` remains `dict[str, Any]` (mutable) | **None** | `RunResult` is a terminal value, not shared across concurrent actors. Freezing it is a Phase 2 concern. |

---

## Migration Guide

### Step 1: Update RunContext construction

```python
# Before
ctx = RunContext(
    run_id="r1",
    started_at=now,
    correlation_id="c1",
    execution_state={"group_chat": "chat"},
    metadata={"source": "cli"},
)

# After
ctx = RunContext(
    run_id="r1",
    started_at=now,
    correlation_id="c1",
    state=FrozenState(group_chat="chat"),
    metadata=(("source", "cli"),),
)
```

### Step 2: Replace state mutation with copy-on-write

```python
# Before
ctx.execution_state["step"] = 2

# After
ctx = ctx.with_state(step=2)
```

### Step 3: Replace metadata reads

```python
# Before
value = ctx.metadata["previous_result"]

# After
value = ctx.get_metadata("previous_result")
# or
value = dict(ctx.metadata)["previous_result"]
```

### Step 4: Update compat bridge

```python
# Before (state_bridge.py)
return RunContext(
    ...,
    execution_state=bridge_chat_pipeline_state(state),
)

# After
legacy_state = bridge_chat_pipeline_state(state)
return RunContext(
    ...,
    state=FrozenState(**legacy_state),
)
```

### Step 5: Update ExecutionEvent payload reads

```python
# Before
event.payload["run_id"]

# After
event.get_payload("run_id")
```

### Step 6: Update tests

All tests that construct `RunContext` with `execution_state=` must use `state=FrozenState(...)`. All tests that assert `ctx.execution_state["key"]` must use `ctx.state.get("key")`.

---

## Success Criteria

1. `RunContext` has `model_config = ConfigDict(frozen=True)`. Assigning any attribute raises `ValidationError`.
2. `ExecutionEvent` has `model_config = ConfigDict(frozen=True)`. No `model_validator` mutates `self`.
3. `execution_state` field no longer exists anywhere in `miniautogen/core/`.
4. All existing tests pass (updated to use new API).
5. A new test proves that `RunContext` attribute assignment raises:
   ```python
   with pytest.raises(ValidationError):
       ctx.input_payload = "mutated"
   ```
6. A new test proves fan-out safety: two concurrent tasks receiving the same `RunContext` cannot observe each other's `with_state()` mutations.
7. Zero regressions in the five runtimes (PipelineRunner, WorkflowRuntime, AgenticLoopRuntime, DeliberationRuntime, CompositeRuntime).

---

## Estimated Effort

| Task | Estimate |
|---|---|
| Implement `FrozenState` and frozen `RunContext` | 2h |
| Implement frozen `ExecutionEvent` with `__init__` inference | 1h |
| Update `compat/state_bridge.py` | 30min |
| Update all tests (contracts, compat, runtimes) | 3h |
| Add new immutability and concurrency safety tests | 1h |
| Documentation updates (architecture docs, invariants) | 1h |
| **Total** | **~8.5h** |

**Risk:** Low. The runtime analysis shows that no runtime mutates `RunContext` fields. The blast radius is confined to construction sites (tests, compat bridge) and external consumers reading `execution_state` or `payload` as dicts.
