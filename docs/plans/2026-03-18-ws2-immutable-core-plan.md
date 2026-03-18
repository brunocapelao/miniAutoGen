# WS2: Immutable Core -- Implementation Plan

> **For Agents:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Eliminate all shared mutable state from MiniAutoGen's core execution path by making `RunContext` and `ExecutionEvent` frozen Pydantic models with copy-on-write propagation.

**Architecture:** Replace mutable `dict` fields on `RunContext` (`execution_state`, `metadata`) and `ExecutionEvent` (`payload`) with immutable tuple-of-tuples representations. Introduce a `FrozenState` model for typed state access. Move `ExecutionEvent`'s post-construction mutation into its `__init__` so the object is never mutated after creation. All production code that reads `payload` as a dict must migrate to `get_payload()` or `dict(event.payload)`.

**Tech Stack:** Python 3.13, Pydantic v2, pytest 8.x, AnyIO

**Global Prerequisites:**
- Environment: macOS, Python 3.13+
- Tools: `python --version`, `pytest --version`
- Branch: Create `feat/ws2-immutable-core` from `main`
- State: All tests currently passing on `main`

**Verification before starting:**
```bash
python --version          # Expected: Python 3.13+
python -m pytest --version # Expected: pytest 8.x
git status                # Expected: clean working tree
python -m pytest tests/ -x -q  # Expected: all tests pass
```

**Design spec:** `docs/plans/2026-03-18-ws2-immutable-core-design.md`

---

## Migration Site Inventory

This section lists every code site that must change, discovered by auditing the codebase. The plan references these by ID.

### RunContext `execution_state` sites (field rename to `state`)

| ID | File | Line | Pattern |
|----|------|------|---------|
| RC-1 | `miniautogen/core/contracts/run_context.py` | 13 | Field definition |
| RC-2 | `miniautogen/compat/state_bridge.py` | 30 | `execution_state=bridge_chat_pipeline_state(state)` |
| RC-3 | `tests/core/contracts/test_run_context.py` | 14 | `execution_state={}` |
| RC-4 | `tests/core/contracts/test_run_context.py` | 27 | `execution_state={}` |
| RC-5 | `tests/core/contracts/test_run_context_comprehensive.py` | 32 | `execution_state={"step": 1}` |
| RC-6 | `tests/core/contracts/test_run_context_comprehensive.py` | 33 | `ctx.execution_state["step"]` |
| RC-7 | `tests/compat/test_run_context_bridge.py` | 21 | `context.execution_state["group_chat"]` |

### RunContext `metadata` dict access sites

| ID | File | Line | Pattern |
|----|------|------|---------|
| MD-1 | `tests/core/contracts/test_run_context_comprehensive.py` | 28 | `new_ctx.metadata["previous_result"]` |

### ExecutionEvent `payload` dict subscript sites (on `ExecutionEvent` only)

| ID | File | Line | Pattern |
|----|------|------|---------|
| EP-1 | `tests/core/contracts/test_execution_event_comprehensive.py` | 13 | `event.payload == {}` |
| EP-2 | `tests/core/contracts/test_execution_event_comprehensive.py` | 24 | `event.payload["status"]` |
| EP-3 | `tests/core/contracts/test_execution_event_comprehensive.py` | 52 | `event.payload["nested"]["deep"]` |
| EP-4 | `tests/core/contracts/test_execution_event_comprehensive.py` | 57 | `event.payload == {}` |
| EP-5 | `tests/core/runtime/test_pipeline_runner_comprehensive.py` | 158 | `payload["error_type"]` |
| EP-6 | `tests/core/runtime/test_agentic_loop_runtime.py` | 570 | `payload["timeout_seconds"]` |

### ExecutionEvent `payload` dict method sites (production code -- NOT in design spec)

| ID | File | Line | Pattern |
|----|------|------|---------|
| PP-1 | `miniautogen/tui/event_mapper.py` | 80 | `event.payload.get("agent_id")` |
| PP-2 | `miniautogen/tui/notifications.py` | 58 | `event.payload.get("agent_id", "Agent")` |
| PP-3 | `miniautogen/observability/event_logging.py` | 46-50 | `**event.payload` (dict unpacking) |
| PP-4 | `miniautogen/tui/widgets/interaction_log.py` | 178-214 | `payload.get(...)` (multiple calls) |

### Documentation sites

| ID | File | Line | Pattern |
|----|------|------|---------|
| DOC-1 | `docs/pt/guides/gemini-cli-gateway.md` | 93 | `event.payload["text"]` |

---

## Task Groups

### TG-1: FrozenState Model

#### Task 1.1: Write failing tests for FrozenState

**What:** Create a new test file with tests for `FrozenState` construction, `.get()`, `.evolve()`, `.to_dict()`, immutability, and serialization.

**Where:** Create `tests/core/contracts/test_frozen_state.py`

**How:**

```python
"""Tests for FrozenState immutable state container."""

from typing import Any

import pytest
from pydantic import ValidationError

from miniautogen.core.contracts.run_context import FrozenState


class TestFrozenStateConstruction:
    def test_empty_construction(self) -> None:
        fs = FrozenState()
        assert fs.to_dict() == {}

    def test_keyword_construction(self) -> None:
        fs = FrozenState(step=1, agent="writer")
        assert fs.to_dict() == {"step": 1, "agent": "writer"}

    def test_data_is_sorted(self) -> None:
        fs = FrozenState(z=1, a=2)
        assert fs._data == (("a", 2), ("z", 1))


class TestFrozenStateGet:
    def test_get_existing_key(self) -> None:
        fs = FrozenState(name="alice")
        assert fs.get("name") == "alice"

    def test_get_missing_key_returns_default(self) -> None:
        fs = FrozenState()
        assert fs.get("missing") is None

    def test_get_missing_key_custom_default(self) -> None:
        fs = FrozenState()
        assert fs.get("missing", 42) == 42


class TestFrozenStateEvolve:
    def test_evolve_adds_new_key(self) -> None:
        fs = FrozenState(a=1)
        fs2 = fs.evolve(b=2)
        assert fs2.to_dict() == {"a": 1, "b": 2}

    def test_evolve_overrides_existing_key(self) -> None:
        fs = FrozenState(a=1)
        fs2 = fs.evolve(a=99)
        assert fs2.get("a") == 99

    def test_evolve_does_not_mutate_original(self) -> None:
        fs = FrozenState(a=1)
        fs.evolve(a=99)
        assert fs.get("a") == 1


class TestFrozenStateImmutability:
    def test_frozen_rejects_attribute_assignment(self) -> None:
        fs = FrozenState(a=1)
        with pytest.raises(ValidationError):
            fs._data = (("a", 2),)  # type: ignore[misc]


class TestFrozenStateSerialization:
    def test_model_dump_returns_dict(self) -> None:
        fs = FrozenState(step=1, agent="writer")
        dumped = fs.model_dump()
        assert dumped == {"agent": "writer", "step": 1}

    def test_round_trip(self) -> None:
        fs = FrozenState(step=1, agent="writer")
        dumped = fs.model_dump()
        restored = FrozenState(**dumped)
        assert restored == fs

    def test_empty_round_trip(self) -> None:
        fs = FrozenState()
        dumped = fs.model_dump()
        restored = FrozenState(**dumped)
        assert restored == fs
```

**Verify:**

```bash
python -m pytest tests/core/contracts/test_frozen_state.py -v 2>&1 | head -30
```

**Expected output:** All tests FAIL with `ImportError: cannot import name 'FrozenState'` because the class does not exist yet.

---

#### Task 1.2: Implement FrozenState class

**What:** Add the `FrozenState` class to the run_context module.

**Where:** Modify `miniautogen/core/contracts/run_context.py` -- add `FrozenState` above the `RunContext` class.

**How:** Insert the following code at the top of the file, after the existing imports:

```python
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_serializer


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
        """Look up a key, returning default if not found."""
        for k, v in self._data:
            if k == key:
                return v
        return default

    def evolve(self, **updates: Any) -> "FrozenState":
        """Return a new FrozenState with the given updates applied."""
        current = dict(self._data)
        current.update(updates)
        return FrozenState(**current)

    def to_dict(self) -> dict[str, Any]:
        """Return a plain dict copy of the state."""
        return dict(self._data)

    @model_serializer
    def ser_model(self) -> dict[str, Any]:
        """Serialize as a plain dict for Pydantic model_dump()."""
        return dict(self._data)
```

The full file after this change should have `FrozenState` defined first, then the existing `RunContext` class unchanged. Do NOT modify `RunContext` yet.

**Verify:**

```bash
python -m pytest tests/core/contracts/test_frozen_state.py -v
```

**Expected output:** All tests in `test_frozen_state.py` PASS.

---

#### Task 1.3: Verify no regressions

**What:** Run the full test suite to confirm `FrozenState` addition did not break anything.

**Where:** N/A (verification only)

**How:**

```bash
python -m pytest tests/ -x -q
```

**Expected output:** All existing tests still pass. Zero failures.

---

#### Task 1.4: Export FrozenState from contracts package

**What:** Add `FrozenState` to the `__init__.py` exports so consumers can import it.

**Where:** Modify `miniautogen/core/contracts/__init__.py`

**How:** Add the import and the `__all__` entry:

1. Change the import line:
   ```python
   from .run_context import RunContext
   ```
   to:
   ```python
   from .run_context import FrozenState, RunContext
   ```

2. Add `"FrozenState"` to the `__all__` list (in alphabetical position, after `"FinalDocument"`).

**Verify:**

```bash
python -c "from miniautogen.core.contracts import FrozenState; print(FrozenState(a=1).get('a'))"
```

**Expected output:** `1`

---

#### COMMIT POINT

```bash
git add tests/core/contracts/test_frozen_state.py miniautogen/core/contracts/run_context.py miniautogen/core/contracts/__init__.py
git commit -m "feat(core): add FrozenState immutable state container

Introduces FrozenState as a frozen Pydantic model that stores
key-value pairs as sorted tuples. Provides get(), evolve(), to_dict(),
and Pydantic serialization. This is the foundation for WS2 immutable core."
```

**If Task Fails:**

1. **FrozenState `_data` not serializing:** Pydantic may not include private attributes. Verify the `@model_serializer` decorator is present. Run `FrozenState(a=1).model_dump()` in a Python REPL to debug.
2. **Import error in `__init__.py`:** Check the exact class name matches `FrozenState` and the import path is `from .run_context import FrozenState, RunContext`.
3. **Can't recover:** `git checkout -- .` and re-examine the approach.

---

### TG-2: Frozen RunContext

#### Task 2.1: Write failing tests for frozen RunContext

**What:** Create tests that exercise the new `RunContext` API: frozen fields, `state` field (replacing `execution_state`), `with_state()`, `evolve_metadata()`, `get_metadata()`, and immutability enforcement.

**Where:** Create `tests/core/contracts/test_run_context_frozen.py`

**How:**

```python
"""Tests for frozen RunContext with FrozenState and tuple metadata."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from miniautogen.core.contracts.run_context import FrozenState, RunContext


def _make_ctx(**overrides: object) -> RunContext:
    defaults: dict[str, object] = {
        "run_id": "run-1",
        "started_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "correlation_id": "corr-1",
    }
    defaults.update(overrides)
    return RunContext(**defaults)  # type: ignore[arg-type]


class TestRunContextFrozen:
    def test_attribute_assignment_raises(self) -> None:
        ctx = _make_ctx()
        with pytest.raises(ValidationError):
            ctx.input_payload = "mutated"  # type: ignore[misc]

    def test_run_id_assignment_raises(self) -> None:
        ctx = _make_ctx()
        with pytest.raises(ValidationError):
            ctx.run_id = "changed"  # type: ignore[misc]


class TestRunContextState:
    def test_default_state_is_empty(self) -> None:
        ctx = _make_ctx()
        assert ctx.state.to_dict() == {}

    def test_construction_with_frozen_state(self) -> None:
        ctx = _make_ctx(state=FrozenState(step=1, agent="writer"))
        assert ctx.state.get("step") == 1
        assert ctx.state.get("agent") == "writer"

    def test_with_state_returns_new_context(self) -> None:
        ctx = _make_ctx(state=FrozenState(step=1))
        ctx2 = ctx.with_state(step=2)
        assert ctx2.state.get("step") == 2
        assert ctx.state.get("step") == 1  # original unchanged

    def test_with_state_preserves_other_fields(self) -> None:
        ctx = _make_ctx(input_payload="hello", state=FrozenState(a=1))
        ctx2 = ctx.with_state(b=2)
        assert ctx2.run_id == ctx.run_id
        assert ctx2.input_payload == "hello"
        assert ctx2.state.get("a") == 1
        assert ctx2.state.get("b") == 2


class TestRunContextMetadata:
    def test_default_metadata_is_empty_tuple(self) -> None:
        ctx = _make_ctx()
        assert ctx.metadata == ()

    def test_construction_with_metadata_tuple(self) -> None:
        ctx = _make_ctx(metadata=(("source", "cli"),))
        assert ctx.get_metadata("source") == "cli"

    def test_get_metadata_missing_returns_default(self) -> None:
        ctx = _make_ctx()
        assert ctx.get_metadata("missing") is None
        assert ctx.get_metadata("missing", "fallback") == "fallback"

    def test_evolve_metadata(self) -> None:
        ctx = _make_ctx(metadata=(("source", "cli"),))
        ctx2 = ctx.evolve_metadata(retry_count=3)
        assert ctx2.get_metadata("source") == "cli"
        assert ctx2.get_metadata("retry_count") == 3
        # Original unchanged
        assert ctx.get_metadata("retry_count") is None

    def test_with_previous_result(self) -> None:
        ctx = _make_ctx()
        ctx2 = ctx.with_previous_result({"output": "data"})
        assert ctx2.input_payload == {"output": "data"}
        assert ctx2.get_metadata("previous_result") == {"output": "data"}
        assert ctx2.run_id == ctx.run_id


class TestRunContextSerialization:
    def test_round_trip(self) -> None:
        ctx = _make_ctx(
            state=FrozenState(group_chat="chat"),
            metadata=(("source", "cli"),),
            input_payload={"text": "hello"},
        )
        dumped = ctx.model_dump()
        restored = RunContext.model_validate(dumped)
        assert restored.state.get("group_chat") == "chat"
        assert restored.get_metadata("source") == "cli"
        assert restored.input_payload == {"text": "hello"}
        assert restored.run_id == ctx.run_id

    def test_state_serializes_as_dict(self) -> None:
        ctx = _make_ctx(state=FrozenState(a=1))
        dumped = ctx.model_dump()
        assert isinstance(dumped["state"], dict)
        assert dumped["state"] == {"a": 1}


class TestRunContextConcurrencySafety:
    def test_concurrent_with_state_isolated(self) -> None:
        """Two branches from the same context do not see each other's state."""
        base = _make_ctx(state=FrozenState(counter=0))
        branch_a = base.with_state(counter=1, branch="a")
        branch_b = base.with_state(counter=2, branch="b")

        assert branch_a.state.get("counter") == 1
        assert branch_a.state.get("branch") == "a"
        assert branch_b.state.get("counter") == 2
        assert branch_b.state.get("branch") == "b"
        assert base.state.get("counter") == 0
        assert base.state.get("branch") is None
```

**Verify:**

```bash
python -m pytest tests/core/contracts/test_run_context_frozen.py -v 2>&1 | head -40
```

**Expected output:** Tests FAIL because `RunContext` does not yet have `frozen=True`, `state` field, `with_state()`, `evolve_metadata()`, or `get_metadata()`.

---

#### Task 2.2: Implement frozen RunContext

**What:** Replace the current `RunContext` class with the frozen version from the design spec.

**Where:** Modify `miniautogen/core/contracts/run_context.py`

**How:** Replace the entire `RunContext` class definition (keep `FrozenState` from TG-1 intact above it). The complete file should be:

```python
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_serializer


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
        """Look up a key, returning default if not found."""
        for k, v in self._data:
            if k == key:
                return v
        return default

    def evolve(self, **updates: Any) -> "FrozenState":
        """Return a new FrozenState with the given updates applied."""
        current = dict(self._data)
        current.update(updates)
        return FrozenState(**current)

    def to_dict(self) -> dict[str, Any]:
        """Return a plain dict copy of the state."""
        return dict(self._data)

    @model_serializer
    def ser_model(self) -> dict[str, Any]:
        """Serialize as a plain dict for Pydantic model_dump()."""
        return dict(self._data)


class RunContext(BaseModel):
    """Typed, frozen execution context for a single framework run."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    started_at: datetime
    correlation_id: str
    state: FrozenState = FrozenState()
    input_payload: Any = None
    timeout_seconds: float | None = None
    namespace: str | None = None
    metadata: tuple[tuple[str, Any], ...] = ()

    def with_state(self, **updates: Any) -> "RunContext":
        """Return a new RunContext with state evolved by the given updates."""
        new_state = self.state.evolve(**updates)
        return self.model_copy(update={"state": new_state})

    def with_previous_result(self, result: Any) -> "RunContext":
        """Return a new RunContext with the previous result injected.

        The previous result is set as ``input_payload`` and a reference
        is stored in ``metadata`` for traceability.
        """
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

**Verify:**

```bash
python -m pytest tests/core/contracts/test_run_context_frozen.py -v
```

**Expected output:** All frozen RunContext tests PASS.

```bash
python -m pytest tests/core/contracts/test_frozen_state.py -v
```

**Expected output:** All FrozenState tests still PASS.

---

#### Task 2.3: Verify new tests pass, old tests fail as expected

**What:** Confirm the new RunContext tests pass, and identify which old tests now fail (they should, because `execution_state` field no longer exists).

**Where:** N/A (verification only)

**How:**

```bash
python -m pytest tests/core/contracts/test_run_context_frozen.py tests/core/contracts/test_frozen_state.py -v
```

**Expected output:** All pass.

```bash
python -m pytest tests/core/contracts/test_run_context.py tests/core/contracts/test_run_context_comprehensive.py -v 2>&1 | tail -20
```

**Expected output:** Failures on tests using `execution_state={}` -- these will be fixed in TG-4.

---

#### COMMIT POINT

```bash
git add miniautogen/core/contracts/run_context.py tests/core/contracts/test_run_context_frozen.py
git commit -m "feat(core): make RunContext frozen with FrozenState, tuple metadata

RunContext now has frozen=True. execution_state is replaced by
state (FrozenState). metadata is tuple[tuple[str, Any], ...].
Adds with_state(), evolve_metadata(), get_metadata() methods.
Old tests will be migrated in the next commit."
```

**If Task Fails:**

1. **`model_copy` fails on frozen model:** Pydantic v2 `model_copy(update=...)` works on frozen models. Verify Pydantic version: `python -c "import pydantic; print(pydantic.__version__)"`. Must be 2.x.
2. **FrozenState serialization broken:** Check `@model_serializer` is present. Run `RunContext(...).model_dump()` in REPL to debug.
3. **Can't recover:** `git stash` and investigate.

---

### TG-3: Frozen ExecutionEvent

#### Task 3.1: Write failing tests for frozen ExecutionEvent

**What:** Create tests for the new frozen `ExecutionEvent`: frozen enforcement, payload as tuple, `get_payload()`, run_id inference from dict payload, round-trip serialization, and backward-compatible dict payload construction.

**Where:** Create `tests/core/contracts/test_execution_event_frozen.py`

**How:**

```python
"""Tests for frozen ExecutionEvent with tuple payload."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from miniautogen.core.contracts.events import ExecutionEvent


class TestExecutionEventFrozen:
    def test_attribute_assignment_raises(self) -> None:
        event = ExecutionEvent(type="run_started", run_id="r1")
        with pytest.raises(ValidationError):
            event.run_id = "changed"  # type: ignore[misc]

    def test_payload_attribute_assignment_raises(self) -> None:
        event = ExecutionEvent(type="run_started", run_id="r1")
        with pytest.raises(ValidationError):
            event.payload = ()  # type: ignore[misc]


class TestExecutionEventPayload:
    def test_dict_payload_converted_to_tuple(self) -> None:
        event = ExecutionEvent(
            type="run_started",
            run_id="r1",
            payload={"status": "ok", "count": 3},
        )
        assert isinstance(event.payload, tuple)

    def test_get_payload(self) -> None:
        event = ExecutionEvent(
            type="run_started",
            run_id="r1",
            payload={"status": "ok"},
        )
        assert event.get_payload("status") == "ok"

    def test_get_payload_missing_returns_default(self) -> None:
        event = ExecutionEvent(type="run_started", run_id="r1")
        assert event.get_payload("missing") is None
        assert event.get_payload("missing", "fallback") == "fallback"

    def test_empty_payload(self) -> None:
        event = ExecutionEvent(type="test", run_id="r1", payload={})
        assert event.payload == ()

    def test_empty_payload_default(self) -> None:
        event = ExecutionEvent(type="test", run_id="r1")
        assert event.payload == ()


class TestExecutionEventRunIdInference:
    def test_run_id_inferred_from_dict_payload(self) -> None:
        event = ExecutionEvent(
            type="run_started",
            payload={"run_id": "inferred-1"},
        )
        assert event.run_id == "inferred-1"

    def test_run_id_not_overridden_when_explicit(self) -> None:
        event = ExecutionEvent(
            type="run_started",
            run_id="explicit-1",
            payload={"run_id": "from-payload"},
        )
        assert event.run_id == "explicit-1"

    def test_run_id_not_inferred_from_non_string(self) -> None:
        event = ExecutionEvent(
            type="run_started",
            payload={"run_id": 123},
        )
        assert event.run_id is None


class TestExecutionEventAliases:
    def test_event_type_alias(self) -> None:
        event = ExecutionEvent(event_type="run_started", run_id="r1")
        assert event.type == "run_started"
        assert event.event_type == "run_started"

    def test_created_at_alias(self) -> None:
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        event = ExecutionEvent(type="test", run_id="r1", created_at=ts)
        assert event.timestamp == ts
        assert event.created_at == ts


class TestExecutionEventSerialization:
    def test_round_trip(self) -> None:
        event = ExecutionEvent(
            type="run_started",
            run_id="r1",
            correlation_id="c1",
            payload={"status": "ok", "count": 3},
        )
        dumped = event.model_dump()
        restored = ExecutionEvent.model_validate(dumped)
        assert restored.type == event.type
        assert restored.run_id == event.run_id
        assert restored.get_payload("status") == "ok"
        assert restored.get_payload("count") == 3

    def test_serialized_payload_from_tuple(self) -> None:
        """model_validate accepts the tuple-of-tuples form from model_dump."""
        event = ExecutionEvent(
            type="test",
            run_id="r1",
            payload={"a": 1},
        )
        dumped = event.model_dump()
        # payload in dumped form is a list of pairs
        assert isinstance(dumped["payload"], (list, tuple))
        restored = ExecutionEvent.model_validate(dumped)
        assert restored.get_payload("a") == 1
```

**Verify:**

```bash
python -m pytest tests/core/contracts/test_execution_event_frozen.py -v 2>&1 | head -40
```

**Expected output:** Tests FAIL because `ExecutionEvent` is not yet frozen and has no `get_payload()`.

---

#### Task 3.2: Implement frozen ExecutionEvent

**What:** Replace the current `ExecutionEvent` class with the frozen version from the design spec.

**Where:** Modify `miniautogen/core/contracts/events.py`

**How:** Replace the entire file contents with:

```python
from datetime import datetime, timezone
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class ExecutionEvent(BaseModel):
    """Canonical execution event emitted by the runtime."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

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

    def __init__(self, **data: Any) -> None:
        # Convert dict payload to tuple-of-tuples before freezing
        raw_payload = data.get("payload", {})
        if isinstance(raw_payload, dict):
            data["payload"] = tuple(sorted(raw_payload.items()))
            # Infer run_id from payload before freezing
            if data.get("run_id") is None and "run_id" in raw_payload:
                candidate = raw_payload["run_id"]
                if isinstance(candidate, str):
                    data["run_id"] = candidate
        elif isinstance(raw_payload, list):
            # Handle deserialized form: list of [key, value] pairs
            data["payload"] = tuple(tuple(pair) for pair in raw_payload)
        super().__init__(**data)

    @property
    def event_type(self) -> str:
        """Backward-compatible alias for type."""
        return self.type

    @property
    def created_at(self) -> datetime:
        """Backward-compatible alias for timestamp."""
        return self.timestamp

    def get_payload(self, key: str, default: Any = None) -> Any:
        """Look up a payload key without dict conversion."""
        for k, v in self.payload:
            if k == key:
                return v
        return default

    def payload_dict(self) -> dict[str, Any]:
        """Return payload as a plain dict for code that needs dict operations."""
        return dict(self.payload)
```

**Verify:**

```bash
python -m pytest tests/core/contracts/test_execution_event_frozen.py -v
```

**Expected output:** All frozen ExecutionEvent tests PASS.

---

#### Task 3.3: Verify new tests pass

**What:** Confirm all new tests pass and review which old tests now fail.

**Where:** N/A (verification only)

**How:**

```bash
python -m pytest tests/core/contracts/test_execution_event_frozen.py tests/core/contracts/test_execution_event_comprehensive.py -v 2>&1 | tail -20
```

**Expected output:** Frozen tests PASS. Comprehensive tests FAIL on `event.payload == {}` and `event.payload["key"]` assertions -- these will be migrated in TG-4.

---

#### COMMIT POINT

```bash
git add miniautogen/core/contracts/events.py tests/core/contracts/test_execution_event_frozen.py
git commit -m "feat(core): make ExecutionEvent frozen with tuple payload

ExecutionEvent now has frozen=True. payload is tuple[tuple[str, Any], ...].
Dict payloads are converted in __init__. run_id inference moved from
model_validator to __init__ (pre-freeze). Adds get_payload() and
payload_dict() helpers."
```

**If Task Fails:**

1. **`__init__` override + `frozen=True` conflict:** Pydantic v2 allows `__init__` on frozen models because the override runs before the object is frozen. If this fails, check Pydantic version.
2. **Alias validation fails:** The `AliasChoices` + `populate_by_name=True` combo must be on the `model_config`, not separate `ConfigDict` calls.
3. **Can't recover:** `git stash` and investigate.

---

### TG-4: Consumer Migration -- Production Code

#### Task 4.1: Migrate compat/state_bridge.py

**What:** Update the state bridge to use `FrozenState` instead of `execution_state`.

**Where:** Modify `miniautogen/compat/state_bridge.py` (site RC-2)

**How:** Replace the entire file with:

```python
from __future__ import annotations

from datetime import datetime
from typing import Any

from miniautogen.core.contracts.run_context import FrozenState, RunContext

RUNTIME_RUNNER_CUTOVER_READY = True


def bridge_chat_pipeline_state(state: Any) -> dict[str, Any]:
    """Convert legacy pipeline state into a mutable mapping."""
    if hasattr(state, "get_state"):
        return dict(state.get_state())
    return dict(state)


def bridge_chat_pipeline_state_to_run_context(
    state: Any,
    *,
    run_id: str,
    started_at: datetime,
    correlation_id: str,
) -> RunContext:
    """Lift legacy chat pipeline state into the typed run context."""
    legacy_state = bridge_chat_pipeline_state(state)
    return RunContext(
        run_id=run_id,
        started_at=started_at,
        correlation_id=correlation_id,
        state=FrozenState(**legacy_state),
    )
```

**Verify:**

```bash
python -c "from miniautogen.compat.state_bridge import bridge_chat_pipeline_state_to_run_context; print('import ok')"
```

**Expected output:** `import ok`

---

#### Task 4.2: Migrate TUI event_mapper.py

**What:** Update `event.payload.get()` to `event.get_payload()`.

**Where:** Modify `miniautogen/tui/event_mapper.py` line 80 (site PP-1)

**How:** Change line 80 from:

```python
        return event.payload.get("agent_id")
```

to:

```python
        return event.get_payload("agent_id")
```

**Verify:**

```bash
python -c "from miniautogen.tui.event_mapper import EventMapper; print('import ok')"
```

**Expected output:** `import ok`

---

#### Task 4.3: Migrate TUI notifications.py

**What:** Update `event.payload.get()` to `event.get_payload()`.

**Where:** Modify `miniautogen/tui/notifications.py` line 58 (site PP-2)

**How:** Change line 58 from:

```python
        agent_id = event.payload.get("agent_id", "Agent")
```

to:

```python
        agent_id = event.get_payload("agent_id", "Agent")
```

**Verify:**

```bash
python -c "from miniautogen.tui.notifications import NotificationSender; print('import ok')"
```

**Expected output:** `import ok`

---

#### Task 4.4: Migrate observability/event_logging.py

**What:** Update `**event.payload` (dict unpacking) to `**event.payload_dict()`.

**Where:** Modify `miniautogen/observability/event_logging.py` lines 46, 48, 50 (site PP-3)

**How:** Change the three lines from:

```python
            bound.error("execution_event", **event.payload)
        elif event.type in _WARNING_TYPES:
            bound.warning("execution_event", **event.payload)
        else:
            bound.info("execution_event", **event.payload)
```

to:

```python
            bound.error("execution_event", **event.payload_dict())
        elif event.type in _WARNING_TYPES:
            bound.warning("execution_event", **event.payload_dict())
        else:
            bound.info("execution_event", **event.payload_dict())
```

**Verify:**

```bash
python -c "from miniautogen.observability.event_logging import LoggingEventSink; print('import ok')"
```

**Expected output:** `import ok`

---

#### Task 4.5: Migrate TUI widgets/interaction_log.py

**What:** Update all `payload.get()` calls to work with tuple payload. The simplest approach is to convert to dict once at the top.

**Where:** Modify `miniautogen/tui/widgets/interaction_log.py` around lines 178-216 (site PP-4)

**How:** Change line 178 from:

```python
        payload = event.payload
```

to:

```python
        payload = event.payload_dict()
```

This single change makes all subsequent `payload.get(...)` calls work because `payload` is now a local dict variable. No other lines in this method need changing.

**Verify:**

```bash
python -c "from miniautogen.tui.widgets.interaction_log import InteractionLog; print('import ok')"
```

**Expected output:** `import ok`

---

#### COMMIT POINT

```bash
git add miniautogen/compat/state_bridge.py miniautogen/tui/event_mapper.py miniautogen/tui/notifications.py miniautogen/observability/event_logging.py miniautogen/tui/widgets/interaction_log.py
git commit -m "refactor(core): migrate production code to frozen event/context APIs

Updates state_bridge to use FrozenState. Migrates TUI and observability
code from event.payload dict access to get_payload() and payload_dict()."
```

**If Task Fails:**

1. **`payload_dict()` not found:** Verify TG-3 was committed and `events.py` has the `payload_dict()` method.
2. **Import errors:** Check all import paths are correct.
3. **Can't recover:** `git stash` and verify TG-3 commit is intact.

---

### TG-5: Consumer Migration -- Test Files

#### Task 5.1: Migrate test_run_context.py

**What:** Update test file to use `state=FrozenState()` instead of `execution_state={}`.

**Where:** Modify `tests/core/contracts/test_run_context.py` (sites RC-3, RC-4)

**How:** Replace the entire file with:

```python
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from miniautogen.core.contracts.run_context import FrozenState, RunContext


def test_run_context_requires_core_operational_fields():
    ctx = RunContext(
        run_id="run-1",
        started_at=datetime.now(UTC),
        correlation_id="corr-1",
        state=FrozenState(),
        input_payload={"message": "hello"},
    )

    assert ctx.run_id == "run-1"
    assert ctx.correlation_id == "corr-1"


def test_run_context_rejects_missing_run_id():
    with pytest.raises(ValidationError):
        RunContext(
            started_at=datetime.now(UTC),
            correlation_id="corr-1",
            state=FrozenState(),
            input_payload={},
        )
```

**Verify:**

```bash
python -m pytest tests/core/contracts/test_run_context.py -v
```

**Expected output:** Both tests PASS.

---

#### Task 5.2: Migrate test_run_context_comprehensive.py

**What:** Update test file to use `FrozenState`, `state`, `get_metadata()` instead of old dict patterns.

**Where:** Modify `tests/core/contracts/test_run_context_comprehensive.py` (sites RC-5, RC-6, MD-1)

**How:** Replace the entire file with:

```python
"""Comprehensive tests for RunContext."""

from datetime import datetime

from miniautogen.core.contracts.run_context import FrozenState, RunContext


def _make_context(**overrides: object) -> RunContext:
    defaults: dict[str, object] = {
        "run_id": "run-1",
        "started_at": datetime(2026, 1, 1),
        "correlation_id": "corr-1",
    }
    defaults.update(overrides)
    return RunContext(**defaults)  # type: ignore[arg-type]


def test_run_context_creation() -> None:
    ctx = _make_context()
    assert ctx.run_id == "run-1"


def test_run_context_with_previous_result() -> None:
    ctx = _make_context()
    new_ctx = ctx.with_previous_result({"output": "data"})
    assert new_ctx.run_id == ctx.run_id
    assert new_ctx.input_payload == {"output": "data"}
    assert new_ctx.get_metadata("previous_result") == {"output": "data"}


def test_run_context_state() -> None:
    ctx = _make_context(state=FrozenState(step=1))
    assert ctx.state.get("step") == 1


def test_run_context_serialization() -> None:
    ctx = _make_context()
    data = ctx.model_dump()
    restored = RunContext.model_validate(data)
    assert restored.run_id == ctx.run_id
```

**Verify:**

```bash
python -m pytest tests/core/contracts/test_run_context_comprehensive.py -v
```

**Expected output:** All 4 tests PASS.

---

#### Task 5.3: Migrate test_run_context_bridge.py

**What:** Update bridge test to use `state.get()` instead of `execution_state["key"]`.

**Where:** Modify `tests/compat/test_run_context_bridge.py` (site RC-7)

**How:** Replace the entire file with:

```python
from datetime import UTC, datetime

from miniautogen.core.contracts.run_context import RunContext
from miniautogen.pipeline.pipeline import ChatPipelineState


def test_bridge_chat_pipeline_state_to_run_context():
    from miniautogen.compat.state_bridge import bridge_chat_pipeline_state_to_run_context

    legacy = ChatPipelineState(group_chat="chat", chat_admin="admin")

    context = bridge_chat_pipeline_state_to_run_context(
        legacy,
        run_id="run-1",
        started_at=datetime.now(UTC),
        correlation_id="corr-1",
    )

    assert isinstance(context, RunContext)
    assert context.run_id == "run-1"
    assert context.state.get("group_chat") == "chat"
```

**Verify:**

```bash
python -m pytest tests/compat/test_run_context_bridge.py -v
```

**Expected output:** Test PASSES.

---

#### Task 5.4: Migrate test_execution_event_comprehensive.py

**What:** Update event tests to use `get_payload()` instead of `event.payload["key"]` and `event.payload == ()` instead of `event.payload == {}`.

**Where:** Modify `tests/core/contracts/test_execution_event_comprehensive.py` (sites EP-1 through EP-4)

**How:** Replace the entire file with:

```python
"""Comprehensive tests for ExecutionEvent."""

from datetime import datetime

from miniautogen.core.contracts.events import ExecutionEvent


def test_event_creation_minimal() -> None:
    event = ExecutionEvent(type="run_started", run_id="run-1")
    assert event.type == "run_started"
    assert event.run_id == "run-1"
    assert event.correlation_id is None
    assert event.payload == ()


def test_event_creation_full() -> None:
    event = ExecutionEvent(
        type="run_finished",
        run_id="run-1",
        correlation_id="corr-1",
        payload={"status": "completed"},
    )
    assert event.correlation_id == "corr-1"
    assert event.get_payload("status") == "completed"


def test_event_has_timestamp() -> None:
    event = ExecutionEvent(type="test", run_id="r1")
    assert isinstance(event.timestamp, datetime)


def test_event_serialization_roundtrip() -> None:
    event = ExecutionEvent(
        type="run_started",
        run_id="run-1",
        correlation_id="corr-1",
        payload={"key": "value"},
    )
    data = event.model_dump()
    restored = ExecutionEvent.model_validate(data)
    assert restored.type == event.type
    assert restored.run_id == event.run_id
    assert restored.correlation_id == event.correlation_id


def test_event_allows_arbitrary_payload() -> None:
    event = ExecutionEvent(
        type="custom",
        run_id="r1",
        payload={"nested": {"deep": [1, 2, 3]}},
    )
    assert event.get_payload("nested") == {"deep": [1, 2, 3]}


def test_event_with_empty_payload() -> None:
    event = ExecutionEvent(type="test", run_id="r1", payload={})
    assert event.payload == ()
```

**Verify:**

```bash
python -m pytest tests/core/contracts/test_execution_event_comprehensive.py -v
```

**Expected output:** All 6 tests PASS.

---

#### Task 5.5: Migrate test_pipeline_runner_comprehensive.py line 158

**What:** Update `payload["error_type"]` to `get_payload("error_type")`.

**Where:** Modify `tests/core/runtime/test_pipeline_runner_comprehensive.py` line 158 (site EP-5)

**How:** Change line 158 from:

```python
    assert failed_events[0].payload["error_type"] == "RuntimeError"
```

to:

```python
    assert failed_events[0].get_payload("error_type") == "RuntimeError"
```

**Verify:**

```bash
python -m pytest tests/core/runtime/test_pipeline_runner_comprehensive.py::test_runner_failed_event_contains_error_type -v
```

**Expected output:** Test PASSES.

---

#### Task 5.6: Migrate test_agentic_loop_runtime.py line 570

**What:** Update `payload["timeout_seconds"]` to `get_payload("timeout_seconds")`.

**Where:** Modify `tests/core/runtime/test_agentic_loop_runtime.py` line 570 (site EP-6)

**How:** Change line 570 from:

```python
    assert timed_out_events[0].payload["timeout_seconds"] == 0.1
```

to:

```python
    assert timed_out_events[0].get_payload("timeout_seconds") == 0.1
```

**Verify:**

```bash
python -m pytest tests/core/runtime/test_agentic_loop_runtime.py -k "timeout" -v
```

**Expected output:** Timeout-related tests PASS.

---

#### Task 5.7: Migrate test_execution_event_model.py (no changes needed, verify only)

**What:** Verify the legacy alias test in `test_execution_event_model.py` still works. It constructs events with dict payloads (which the `__init__` converts) and reads `event.type` / `event.run_id` (not payload subscript). No changes needed.

**Where:** `tests/core/events/test_execution_event_model.py`

**How:**

```bash
python -m pytest tests/core/events/test_execution_event_model.py -v
```

**Expected output:** All 3 tests PASS. The `payload={"run_id": "run-1"}` construction is handled by the `__init__` override and `run_id` inference still works.

---

#### Task 5.8: Migrate test_events.py (no changes needed, verify only)

**What:** Verify the basic event test still works. It constructs with dict payload and only checks `event.event_type` and `event.correlation_id`.

**Where:** `tests/core/contracts/test_events.py`

**How:**

```bash
python -m pytest tests/core/contracts/test_events.py -v
```

**Expected output:** Test PASSES.

---

#### Task 5.9: Migrate test_models.py (AgentEvent -- out of scope, verify no breakage)

**What:** Verify that `AgentEvent` tests still pass. `AgentEvent` is a separate model in `miniautogen/backends/models.py` and is NOT being frozen in WS2. Its `payload` remains `dict[str, Any]`.

**Where:** `tests/backends/test_models.py`

**How:**

```bash
python -m pytest tests/backends/test_models.py -v
```

**Expected output:** All tests PASS. `AgentEvent.payload` is unchanged.

---

#### COMMIT POINT

```bash
git add tests/core/contracts/test_run_context.py tests/core/contracts/test_run_context_comprehensive.py tests/compat/test_run_context_bridge.py tests/core/contracts/test_execution_event_comprehensive.py tests/core/runtime/test_pipeline_runner_comprehensive.py tests/core/runtime/test_agentic_loop_runtime.py
git commit -m "refactor(tests): migrate all tests to frozen RunContext/ExecutionEvent API

Updates execution_state -> state (FrozenState), metadata dict -> tuple,
payload dict subscript -> get_payload(). All 21 migration sites updated."
```

**If Task Fails:**

1. **Test still uses old API:** Search for `execution_state` or `\.payload\[` in test files to find remaining migration sites.
2. **Serialization round-trip broken:** Check that `model_dump()` / `model_validate()` work correctly by running the specific test in isolation.
3. **Can't recover:** `git stash` and re-examine which tests still reference old API.

---

### TG-6: Backward Compatibility Utility

#### Task 6.1: Write failing tests for migration utility

**What:** Create tests for the `migrate_run_context_v1_to_v2()` utility that converts old serialized format to new format.

**Where:** Create `tests/compat/test_migrate_run_context.py`

**How:**

```python
"""Tests for RunContext v1->v2 migration utility."""

from miniautogen.compat.migration import migrate_run_context_v1_to_v2


def test_migrate_execution_state_to_state() -> None:
    v1 = {
        "run_id": "r1",
        "started_at": "2026-01-01T00:00:00",
        "correlation_id": "c1",
        "execution_state": {"step": 1, "agent": "writer"},
        "metadata": {"source": "cli"},
    }
    v2 = migrate_run_context_v1_to_v2(v1)
    assert "execution_state" not in v2
    assert v2["state"] == {"step": 1, "agent": "writer"}
    assert v2["metadata"] == [("source", "cli")]


def test_migrate_already_v2_is_noop() -> None:
    v2 = {
        "run_id": "r1",
        "started_at": "2026-01-01T00:00:00",
        "correlation_id": "c1",
        "state": {"step": 1},
        "metadata": [("source", "cli")],
    }
    result = migrate_run_context_v1_to_v2(v2)
    assert result["state"] == {"step": 1}
    assert result["metadata"] == [("source", "cli")]


def test_migrate_metadata_dict_to_sorted_pairs() -> None:
    v1 = {
        "run_id": "r1",
        "started_at": "2026-01-01T00:00:00",
        "correlation_id": "c1",
        "metadata": {"z_key": "last", "a_key": "first"},
    }
    v2 = migrate_run_context_v1_to_v2(v1)
    assert v2["metadata"] == [("a_key", "first"), ("z_key", "last")]


def test_migrate_preserves_other_fields() -> None:
    v1 = {
        "run_id": "r1",
        "started_at": "2026-01-01T00:00:00",
        "correlation_id": "c1",
        "execution_state": {"k": "v"},
        "input_payload": {"text": "hello"},
        "timeout_seconds": 30,
    }
    v2 = migrate_run_context_v1_to_v2(v1)
    assert v2["input_payload"] == {"text": "hello"}
    assert v2["timeout_seconds"] == 30


def test_migrate_does_not_mutate_input() -> None:
    v1 = {
        "run_id": "r1",
        "started_at": "2026-01-01T00:00:00",
        "correlation_id": "c1",
        "execution_state": {"k": "v"},
    }
    original_keys = set(v1.keys())
    migrate_run_context_v1_to_v2(v1)
    assert set(v1.keys()) == original_keys


def test_migrated_data_deserializes_to_run_context() -> None:
    from miniautogen.core.contracts.run_context import RunContext

    v1 = {
        "run_id": "r1",
        "started_at": "2026-01-01T00:00:00",
        "correlation_id": "c1",
        "execution_state": {"step": 1},
        "metadata": {"source": "cli"},
    }
    v2 = migrate_run_context_v1_to_v2(v1)
    ctx = RunContext.model_validate(v2)
    assert ctx.state.get("step") == 1
    assert ctx.get_metadata("source") == "cli"
```

**Verify:**

```bash
python -m pytest tests/compat/test_migrate_run_context.py -v 2>&1 | head -20
```

**Expected output:** Tests FAIL with `ModuleNotFoundError: No module named 'miniautogen.compat.migration'`.

---

#### Task 6.2: Implement migration utility

**What:** Create the `migrate_run_context_v1_to_v2()` function.

**Where:** Create `miniautogen/compat/migration.py`

**How:**

```python
"""One-time migration utilities for serialized data format changes."""

from __future__ import annotations

from typing import Any


def migrate_run_context_v1_to_v2(data: dict[str, Any]) -> dict[str, Any]:
    """Transform a serialized v1 RunContext dict to v2 format.

    Handles:
    - execution_state (dict) -> state (dict, deserialized by FrozenState)
    - metadata (dict) -> metadata (list of [key, value] sorted pairs)

    Does not mutate the input dict.
    """
    migrated = dict(data)
    if "execution_state" in migrated:
        migrated["state"] = migrated.pop("execution_state")
    if isinstance(migrated.get("metadata"), dict):
        migrated["metadata"] = sorted(migrated["metadata"].items())
    return migrated
```

**Verify:**

```bash
python -m pytest tests/compat/test_migrate_run_context.py -v
```

**Expected output:** All 6 tests PASS.

---

#### COMMIT POINT

```bash
git add miniautogen/compat/migration.py tests/compat/test_migrate_run_context.py
git commit -m "feat(compat): add migrate_run_context_v1_to_v2 utility

Provides one-time migration for serialized RunContext payloads from
v1 (execution_state dict, metadata dict) to v2 (state dict, metadata
sorted pairs). Intended for checkpoint store migration."
```

**If Task Fails:**

1. **Import path wrong:** Verify file is at `miniautogen/compat/migration.py` and the `compat` directory has `__init__.py`.
2. **Can't recover:** `git checkout -- .` and recreate the file.

---

### TG-7: Documentation Update

#### Task 7.1: Update gemini-cli-gateway.md documentation example

**What:** Update the code example that uses `event.payload["text"]` to use `event.get_payload("text")`.

**Where:** Modify `docs/pt/guides/gemini-cli-gateway.md` line 93 (site DOC-1)

**How:** Change line 93 from:

```python
        print(event.payload["text"])
```

to:

```python
        print(event.get_payload("text"))
```

**Verify:** Visual inspection -- the file is documentation, not executable.

---

#### COMMIT POINT

```bash
git add docs/pt/guides/gemini-cli-gateway.md
git commit -m "docs: update gemini gateway example for frozen ExecutionEvent API

Changes event.payload[\"text\"] to event.get_payload(\"text\")
to match the new frozen tuple payload."
```

---

### TG-8: Code Review Checkpoint

#### Task 8.1: Run Code Review

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
   - All Low issues have `TODO(review):` comments added
   - All Cosmetic issues have `FIXME(nitpick):` comments added

---

## Final Verification

After all task groups are complete, run the full test suite:

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

**Expected output:** ALL tests pass. Zero failures. Zero errors.

Then verify the key invariants:

```bash
python -c "
from miniautogen.core.contracts.run_context import RunContext, FrozenState
from miniautogen.core.contracts.events import ExecutionEvent
from pydantic import ValidationError
from datetime import datetime, timezone

# 1. RunContext is frozen
ctx = RunContext(run_id='r1', started_at=datetime.now(timezone.utc), correlation_id='c1')
try:
    ctx.run_id = 'changed'
    print('FAIL: RunContext is not frozen')
except ValidationError:
    print('PASS: RunContext rejects attribute assignment')

# 2. ExecutionEvent is frozen
ev = ExecutionEvent(type='test', run_id='r1')
try:
    ev.run_id = 'changed'
    print('FAIL: ExecutionEvent is not frozen')
except ValidationError:
    print('PASS: ExecutionEvent rejects attribute assignment')

# 3. execution_state field gone
assert not hasattr(RunContext.model_fields, 'execution_state'), 'execution_state still exists'
print('PASS: execution_state field removed')

# 4. Copy-on-write isolation
base = RunContext(run_id='r1', started_at=datetime.now(timezone.utc), correlation_id='c1', state=FrozenState(x=0))
a = base.with_state(x=1)
b = base.with_state(x=2)
assert a.state.get('x') == 1
assert b.state.get('x') == 2
assert base.state.get('x') == 0
print('PASS: Copy-on-write isolation works')

# 5. Serialization round-trip
dumped = ctx.model_dump()
restored = RunContext.model_validate(dumped)
assert restored.run_id == ctx.run_id
print('PASS: RunContext round-trip works')

ev2 = ExecutionEvent(type='test', run_id='r1', payload={'k': 'v'})
dumped2 = ev2.model_dump()
restored2 = ExecutionEvent.model_validate(dumped2)
assert restored2.get_payload('k') == 'v'
print('PASS: ExecutionEvent round-trip works')

print()
print('All invariants verified.')
"
```

**Expected output:**

```
PASS: RunContext rejects attribute assignment
PASS: ExecutionEvent rejects attribute assignment
PASS: execution_state field removed
PASS: Copy-on-write isolation works
PASS: RunContext round-trip works
PASS: ExecutionEvent round-trip works

All invariants verified.
```

Then verify no `execution_state` references remain in core:

```bash
grep -r "execution_state" miniautogen/core/ miniautogen/compat/
```

**Expected output:** No matches (zero output). The field name is fully retired from production code.

---

## Summary of All Files Modified

### New files created:
- `tests/core/contracts/test_frozen_state.py`
- `tests/core/contracts/test_run_context_frozen.py`
- `tests/core/contracts/test_execution_event_frozen.py`
- `tests/compat/test_migrate_run_context.py`
- `miniautogen/compat/migration.py`

### Production files modified:
- `miniautogen/core/contracts/run_context.py` -- FrozenState + frozen RunContext
- `miniautogen/core/contracts/events.py` -- frozen ExecutionEvent
- `miniautogen/core/contracts/__init__.py` -- export FrozenState
- `miniautogen/compat/state_bridge.py` -- use FrozenState
- `miniautogen/tui/event_mapper.py` -- get_payload()
- `miniautogen/tui/notifications.py` -- get_payload()
- `miniautogen/tui/widgets/interaction_log.py` -- payload_dict()
- `miniautogen/observability/event_logging.py` -- payload_dict()

### Test files modified:
- `tests/core/contracts/test_run_context.py`
- `tests/core/contracts/test_run_context_comprehensive.py`
- `tests/compat/test_run_context_bridge.py`
- `tests/core/contracts/test_execution_event_comprehensive.py`
- `tests/core/runtime/test_pipeline_runner_comprehensive.py` (1 line)
- `tests/core/runtime/test_agentic_loop_runtime.py` (1 line)

### Documentation files modified:
- `docs/pt/guides/gemini-cli-gateway.md` (1 line)
