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

    def evolve_metadata(self, **updates: Any) -> "RunContext":
        """Return a new RunContext with metadata evolved by the given updates."""
        current = dict(self.metadata)
        current.update(updates)
        return self.model_copy(
            update={"metadata": tuple(sorted(current.items()))},
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

**`evolve_metadata()` helper:**

`RunContext` also provides an `evolve_metadata()` method symmetric with `with_state()`, so callers do not need to manually construct metadata tuples:

```python
def evolve_metadata(self, **updates: Any) -> "RunContext":
    """Return a new RunContext with metadata evolved by the given updates."""
    current = dict(self.metadata)
    current.update(updates)
    return self.model_copy(
        update={"metadata": tuple(sorted(current.items()))},
    )
```

Usage:

```python
# Instead of manual tuple construction:
ctx2 = ctx.evolve_metadata(source="cli", retry_count=3)

# Equivalent to (but much more ergonomic than):
md = dict(ctx.metadata)
md["source"] = "cli"
md["retry_count"] = 3
ctx2 = ctx.model_copy(update={"metadata": tuple(sorted(md.items()))})
```

**Migration path for `execution_state` consumers:**

| Current code | Replacement |
|---|---|
| `ctx.execution_state["key"]` | `ctx.state.get("key")` |
| `ctx.execution_state["key"] = val` | `ctx = ctx.with_state(key=val)` |
| `RunContext(execution_state={"k": "v"})` | `RunContext(state=FrozenState(k="v"))` |
| `ctx.metadata["key"]` | `ctx.get_metadata("key")` |
| `{**ctx.metadata, "k": "v"}` | `ctx.evolve_metadata(k="v")` |

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

### 5. Serialization Contract

Pydantic's `model_dump()` and `model_validate()` must round-trip correctly for persistence (checkpoint stores, event replay, run stores). This section defines the canonical JSON representation.

**`FrozenState` serialization:**

`FrozenState._data` is a private attribute (prefixed with `_`). By default, Pydantic excludes private attributes from `model_dump()`. To ensure serialization works, `FrozenState` must either:

1. Use `to_dict()` explicitly at serialization boundaries, or
2. Override `model_dump()` / implement a custom serializer.

**Recommended approach:** Add a Pydantic `model_serializer` to `FrozenState`:

```python
from pydantic import model_serializer

class FrozenState(BaseModel):
    # ... existing code ...

    @model_serializer
    def ser_model(self) -> dict[str, Any]:
        return dict(self._data)
```

This ensures `FrozenState(key="value").model_dump()` produces `{"key": "value"}` -- a plain dict, the same shape as the old `execution_state`.

**Round-trip invariant:** `model_validate(model_dump())` must reconstruct an equivalent object.

```python
# FrozenState round-trip
fs = FrozenState(step=1, agent="writer")
assert FrozenState(**fs.model_dump()) == fs

# RunContext round-trip
ctx = RunContext(
    run_id="r1",
    started_at=datetime(2026, 3, 18, tzinfo=timezone.utc),
    correlation_id="c1",
    state=FrozenState(group_chat="chat"),
    metadata=(("source", "cli"),),
    input_payload={"text": "hello"},
)
dumped = ctx.model_dump()
restored = RunContext.model_validate(dumped)
assert restored.state.get("group_chat") == "chat"
assert restored.get_metadata("source") == "cli"
```

**Concrete `RunContext.model_dump()` output:**

```json
{
  "run_id": "r1",
  "started_at": "2026-03-18T00:00:00Z",
  "correlation_id": "c1",
  "state": {"group_chat": "chat"},
  "input_payload": {"text": "hello"},
  "timeout_seconds": null,
  "namespace": null,
  "metadata": [["source", "cli"]]
}
```

Note: `metadata` serializes as an array of 2-element arrays (JSON representation of `tuple[tuple[str, Any], ...]`). `RunContext.model_validate()` must accept this form. Pydantic handles this natively for `tuple` types.

**`ExecutionEvent` round-trip:**

```python
event = ExecutionEvent(
    type="run_started",
    run_id="r1",
    payload={"status": "ok", "count": 3},
)
dumped = event.model_dump()
restored = ExecutionEvent.model_validate(dumped)
assert restored.get_payload("status") == "ok"
```

The `__init__` override converts dict payloads to tuples on construction. For `model_validate()`, the serialized form (array of pairs) is passed directly as a tuple -- no dict conversion needed. However, for backward compatibility with persisted events that stored `payload` as a dict, the `__init__` override handles both forms transparently.

### 6. PipelineRunner Compatibility

**Source:** `miniautogen/core/runtime/pipeline_runner.py`

Detailed trace of how `state: Any` flows through PipelineRunner:

1. `run_pipeline(pipeline, state, *, timeout_seconds)` receives `state: Any` (line 80).
2. `run_id` is extracted via `getattr(state, "run_id", None)` (line 84) -- a read-only attribute access. If `state` is a frozen `RunContext`, `getattr` works identically. No mutation.
3. `state` is passed unchanged to `_execute_pipeline(pipeline, state)` (lines 171, 174).
4. `_execute_pipeline` calls `pipeline.run(state)` (line 49) -- pure pass-through. PipelineRunner never indexes into, assigns to, or modifies `state`.
5. PipelineRunner constructs `ExecutionEvent` instances with dict `payload` literals (e.g., `payload={"error_type": error_type}` at line 73). These are converted by the frozen `ExecutionEvent.__init__` transparently.
6. PipelineRunner writes to `self.last_run_id` (line 87, 224) -- this is runner-level mutable state, not `RunContext` state. Unaffected by this workstream.

**Verdict:** PipelineRunner is fully compatible with frozen `RunContext` and frozen `ExecutionEvent`. Zero code changes required. The runner never reads `execution_state`, `metadata`, or `payload` via dict subscript. Its `ExecutionEvent` construction sites all pass dict literals, which the `__init__` override handles.

---

## Breaking Changes

**Note on `RunResult.metadata`:** Several test files access `result.metadata["key"]` (e.g., `result.metadata["stop_reason"]` in agentic loop tests, `result.metadata["final_document"]` in deliberation tests). These are **not affected** by this workstream -- `RunResult.metadata` remains `dict[str, Any]` as stated in the table below.

| Change | Severity | Affected code (codebase audit) |
|---|---|---|
| `execution_state` field renamed to `state` (type `FrozenState`) | **High** | **4 files, 8 sites:** `miniautogen/core/contracts/run_context.py` (1 field def), `miniautogen/compat/state_bridge.py` (1 construction site), `tests/core/contracts/test_run_context.py` (2 construction sites), `tests/core/contracts/test_run_context_comprehensive.py` (2 sites: construction + assertion), `tests/compat/test_run_context_bridge.py` (1 assertion) |
| `metadata` field type changes from `dict` to `tuple[tuple[str, Any], ...]` | **Medium** | **2 files, 2 sites:** `tests/core/contracts/test_run_context_comprehensive.py:28` (`new_ctx.metadata["previous_result"]`), `miniautogen/core/contracts/run_context.py` (internal `with_previous_result`, updated) |
| `ExecutionEvent.payload` type changes from `dict` to `tuple[tuple[str, Any], ...]` | **Medium** | **8 files, 13 sites:** `tests/backends/google_genai/test_driver.py:71`, `tests/backends/test_transformer.py:41`, `tests/backends/anthropic_sdk/test_driver.py:77`, `tests/backends/test_models.py:151`, `tests/backends/openai_sdk/test_driver.py:91`, `tests/backends/agentapi/test_mapper.py:27-28`, `tests/backends/agentapi/test_driver.py:101`, `tests/core/runtime/test_pipeline_runner_comprehensive.py:158`, `tests/core/runtime/test_agentic_loop_runtime.py:570`, `tests/core/contracts/test_execution_event_comprehensive.py:24,52`, `docs/pt/guides/gemini-cli-gateway.md:93` (documentation example) |
| `RunContext` and `ExecutionEvent` become frozen (attribute assignment raises) | **Medium** | Any code that assigns `ctx.some_field = value` or `event.run_id = value` (no direct assignment sites found in current codebase outside `events.py` model_validator) |
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

### Step 3: Replace metadata reads and writes

```python
# Before (read)
value = ctx.metadata["previous_result"]

# After (read)
value = ctx.get_metadata("previous_result")
# or
value = dict(ctx.metadata)["previous_result"]

# Before (write)
ctx.metadata["source"] = "cli"

# After (write -- copy-on-write)
ctx = ctx.evolve_metadata(source="cli")
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

## Backward Compatibility

### External code deserializing old `execution_state` dicts

**This is a breaking change. Old serialized `RunContext` payloads will not deserialize into the new model without transformation.**

Specifically:

- Old serialized form: `{"execution_state": {"step": 1, "agent": "writer"}, "metadata": {"source": "cli"}, ...}`
- New expected form: `{"state": {"step": 1, "agent": "writer"}, "metadata": [["source", "cli"]], ...}`

**Migration strategy:**

1. **No automatic backward compatibility.** The field rename (`execution_state` -> `state`) and type change (`dict` -> `FrozenState` / `tuple`) make old payloads incompatible with `RunContext.model_validate()`.

2. **Provide a one-time migration utility** in `miniautogen/compat/`:

```python
def migrate_run_context_v1_to_v2(data: dict[str, Any]) -> dict[str, Any]:
    """Transform a serialized v1 RunContext dict to v2 format.

    Handles:
    - execution_state (dict) -> state (dict, deserialized by FrozenState)
    - metadata (dict) -> metadata (list of [key, value] pairs)
    """
    migrated = dict(data)
    if "execution_state" in migrated:
        migrated["state"] = migrated.pop("execution_state")
    if isinstance(migrated.get("metadata"), dict):
        migrated["metadata"] = sorted(migrated["metadata"].items())
    return migrated
```

3. **Deprecation timeline:**
   - **v0.next (this release):** Ship frozen models + migration utility. Document the breaking change in CHANGELOG.
   - **v0.next+1:** Remove migration utility. All persisted data must be in v2 format.

4. **Checkpoint store migration:** If `CheckpointStore` has persisted `RunContext` objects via `model_dump()`, those checkpoints must be migrated using the utility above before loading with the new model. The `run_store` saves opaque status dicts (not `RunContext`), so it is unaffected.

5. **Event replay:** Persisted `ExecutionEvent` payloads stored as dicts will deserialize correctly -- the `ExecutionEvent.__init__` override accepts both dict and tuple-of-tuples for `payload`. No migration needed for events. However, any code that reads replayed `event.payload["key"]` must still be updated to `event.get_payload("key")`.

---

## Estimated Effort

| Task | Estimate |
|---|---|
| Implement `FrozenState` (with `model_serializer`) and frozen `RunContext` (incl. `evolve_metadata()`) | 2.5h |
| Implement frozen `ExecutionEvent` with `__init__` inference | 1h |
| Update `compat/state_bridge.py` | 30min |
| Write `migrate_run_context_v1_to_v2()` compat utility | 30min |
| Update all tests -- 8 files, ~21 sites for `execution_state`/`metadata`/`payload` subscript access | 3h |
| Update documentation example (`docs/pt/guides/gemini-cli-gateway.md:93`) | 15min |
| Add new immutability and concurrency safety tests | 1h |
| Add serialization round-trip tests (`model_dump` / `model_validate`) | 1h |
| Documentation updates (architecture docs, invariants, CHANGELOG) | 1h |
| **Total** | **~10.75h** |

**Risk:** Low-Medium. The runtime analysis confirms no runtime mutates `RunContext` fields. The blast radius is confined to construction sites (tests, compat bridge) and external consumers reading `execution_state` or `payload` as dicts. The codebase audit identified 21 specific migration sites across 8 test files, 1 compat module, and 1 documentation file. The `event.payload["key"]` pattern (13 sites across 8 test files) is the largest single migration category. A `migrate_run_context_v1_to_v2()` utility addresses the serialization backward-compatibility gap.
