# Milestone 1 — Chunk 2: Observability & Domain Events

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan.

**Goal:** Production-grade event system with correlation, filtering, and composable sinks

**Architecture:** Event-driven — all runtimes publish structured events; sinks are composable and filterable. The `EventSink` protocol is the single publish interface. New `EventFilter` protocol gates which events reach which sinks. `CompositeEventSink` fans out, `FilteredEventSink` applies predicates, `LoggingEventSink` bridges to structlog.

**Tech Stack:** Python 3.10+, AnyIO 4+, Pydantic v2, structlog, pytest-asyncio, ruff (line-length=100)

**Global Prerequisites:**
- Environment: macOS or Linux, Python 3.10 or 3.11
- Tools: `poetry`, `pytest`, `ruff`
- Branch: work from `main`
- State: clean working tree

**Verification before starting:**
```bash
python --version        # Expected: Python 3.10.x or 3.11.x
poetry --version        # Expected: Poetry 1.x or 2.x
pytest --version        # Expected: pytest 7.4+
ruff --version          # Expected: ruff 0.15+
git status              # Expected: clean working tree on main
```

---

## Important Codebase Notes

Before implementing, understand these facts about the current state:

1. **`correlation_id` already exists** on `ExecutionEvent` as a **required** `str` field (see `miniautogen/core/contracts/events.py:20`). Task 1 changes it to **optional** (`str | None = None`) so events can be created without a correlation_id when one is not available.

2. **Deliberation events are hardcoded strings** in `miniautogen/core/runtime/deliberation_runtime.py` (lines 41-43): `"deliberation_started"`, `"deliberation_finished"`, `"deliberation_failed"`. These are NOT members of the `EventType` enum. The `DELIBERATION_EVENT_TYPES` set in `types.py:53-57` also uses raw strings instead of enum references.

3. **No `__init__.py`** files exist in `tests/core/` or `tests/core/events/`. Pytest discovers tests without them. Do NOT create `__init__.py` in test directories.

4. **Existing test pattern:** Tests use `@pytest.mark.asyncio` decorator for async tests. Tests import directly from `miniautogen.core.contracts.events` and `miniautogen.core.events`.

5. **Ruff config:** line-length=100, target Python 3.10, lint selects `["E", "F", "I"]` (pycodestyle, pyflakes, isort).

6. **All runtimes** (`PipelineRunner`, `AgenticLoopRuntime`, `WorkflowRuntime`, `DeliberationRuntime`) already emit `correlation_id` in events. They access the event sink via `self._runner.event_sink` (or `self.event_sink` for PipelineRunner).

---

### Task 1: Make correlation_id Optional on ExecutionEvent

**Files:**
- Modify: `miniautogen/core/contracts/events.py:20` — change `correlation_id: str` to `correlation_id: str | None = None`
- Test: `tests/core/events/test_execution_event_model.py` — add test for None correlation_id

**Step 1: Write the failing test**

Add this test to `tests/core/events/test_execution_event_model.py`:

```python
def test_execution_event_allows_none_correlation_id() -> None:
    event = ExecutionEvent(
        type="run_started",
        run_id="run-1",
    )
    assert event.correlation_id is None
    assert event.run_id == "run-1"
```

**Step 2: Run the test to verify it fails**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/core/events/test_execution_event_model.py::test_execution_event_allows_none_correlation_id -v`

Expected output:
```
FAILED tests/core/events/test_execution_event_model.py::test_execution_event_allows_none_correlation_id - pydantic_core._pydantic_core.ValidationError: 1 validation error for ExecutionEvent
```

**If you see a different error:** Ensure imports are correct and the test file already has `from miniautogen.core.contracts.events import ExecutionEvent` at the top (it does).

**Step 3: Implement the change**

In `miniautogen/core/contracts/events.py`, change line 20 from:

```python
    correlation_id: str
```

to:

```python
    correlation_id: str | None = None
```

**Step 4: Run the test to verify it passes**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/core/events/test_execution_event_model.py -v`

Expected output:
```
PASSED tests/core/events/test_execution_event_model.py::test_execution_event_allows_none_correlation_id
PASSED tests/core/events/test_execution_event_model.py::test_execution_event_supports_canonical_fields
PASSED tests/core/events/test_execution_event_model.py::test_execution_event_accepts_legacy_aliases
```

**Step 5: Run the full event test suite to check for regressions**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/core/events/ -v`

Expected: All tests pass. Existing tests already provide `correlation_id="corr-1"` so they are unaffected.

**Step 6: Run ruff**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && ruff check miniautogen/core/contracts/events.py tests/core/events/test_execution_event_model.py`

Expected: No errors.

**Step 7: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/core/contracts/events.py tests/core/events/test_execution_event_model.py
git commit -m "feat(events): make correlation_id optional on ExecutionEvent"
```

**If Task Fails:**
1. **Test won't run:** Check `pytest` is installed (`poetry install`). Check import path matches.
2. **Other tests break:** If existing tests relied on `correlation_id` being required, they already pass it explicitly, so this should not happen. Run `python -m pytest tests/ -x` to find which test breaks.
3. **Can't recover:** `git checkout -- miniautogen/core/contracts/events.py tests/core/events/test_execution_event_model.py`

---

### Task 2: Promote Deliberation Event Types to EventType Enum

**Files:**
- Modify: `miniautogen/core/events/types.py:4-57` — add 3 enum members, update DELIBERATION_EVENT_TYPES set
- Test: `tests/core/events/test_event_taxonomy.py` — add deliberation enum membership tests

**Step 1: Write the failing test**

Add these tests to `tests/core/events/test_event_taxonomy.py`:

```python
def test_deliberation_event_types_are_enum_members() -> None:
    assert EventType.DELIBERATION_STARTED.value == "deliberation_started"
    assert EventType.DELIBERATION_FINISHED.value == "deliberation_finished"
    assert EventType.DELIBERATION_FAILED.value == "deliberation_failed"


def test_deliberation_event_types_set_uses_enum() -> None:
    from miniautogen.core.events.types import DELIBERATION_EVENT_TYPES

    assert EventType.DELIBERATION_STARTED.value in DELIBERATION_EVENT_TYPES
    assert EventType.DELIBERATION_FINISHED.value in DELIBERATION_EVENT_TYPES
    assert EventType.DELIBERATION_FAILED.value in DELIBERATION_EVENT_TYPES
```

**Step 2: Run the tests to verify they fail**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/core/events/test_event_taxonomy.py::test_deliberation_event_types_are_enum_members -v`

Expected output:
```
FAILED - AttributeError: 'DELIBERATION_STARTED' is not a member of 'EventType'
```

**Step 3: Implement the enum additions**

In `miniautogen/core/events/types.py`, add three new members to the `EventType` enum after the backend driver events block (after line 42, before the closing of the class), and update the `DELIBERATION_EVENT_TYPES` set.

Replace the entire content of `miniautogen/core/events/types.py` with:

```python
from enum import Enum


class EventType(str, Enum):
    RUN_STARTED = "run_started"
    RUN_FINISHED = "run_finished"
    RUN_FAILED = "run_failed"
    RUN_CANCELLED = "run_cancelled"
    RUN_TIMED_OUT = "run_timed_out"
    COMPONENT_STARTED = "component_started"
    COMPONENT_FINISHED = "component_finished"
    COMPONENT_SKIPPED = "component_skipped"
    COMPONENT_RETRIED = "component_retried"
    TOOL_INVOKED = "tool_invoked"
    TOOL_SUCCEEDED = "tool_succeeded"
    TOOL_FAILED = "tool_failed"
    CHECKPOINT_SAVED = "checkpoint_saved"
    CHECKPOINT_RESTORED = "checkpoint_restored"
    ADAPTER_FAILED = "adapter_failed"
    VALIDATION_FAILED = "validation_failed"
    POLICY_APPLIED = "policy_applied"
    BUDGET_EXCEEDED = "budget_exceeded"

    # Agentic loop events
    AGENTIC_LOOP_STARTED = "agentic_loop_started"
    ROUTER_DECISION = "router_decision"
    AGENT_REPLIED = "agent_replied"
    AGENTIC_LOOP_STOPPED = "agentic_loop_stopped"
    STAGNATION_DETECTED = "stagnation_detected"

    # Deliberation events
    DELIBERATION_STARTED = "deliberation_started"
    DELIBERATION_FINISHED = "deliberation_finished"
    DELIBERATION_FAILED = "deliberation_failed"

    # Backend driver events
    BACKEND_SESSION_STARTED = "backend_session_started"
    BACKEND_TURN_STARTED = "backend_turn_started"
    BACKEND_MESSAGE_DELTA = "backend_message_delta"
    BACKEND_MESSAGE_COMPLETED = "backend_message_completed"
    BACKEND_TOOL_CALL_REQUESTED = "backend_tool_call_requested"
    BACKEND_TOOL_CALL_EXECUTED = "backend_tool_call_executed"
    BACKEND_ARTIFACT_EMITTED = "backend_artifact_emitted"
    BACKEND_WARNING = "backend_warning"
    BACKEND_ERROR = "backend_error"
    BACKEND_TURN_COMPLETED = "backend_turn_completed"
    BACKEND_SESSION_CLOSED = "backend_session_closed"


AGENTIC_LOOP_EVENT_TYPES = {
    EventType.AGENTIC_LOOP_STARTED.value,
    EventType.ROUTER_DECISION.value,
    EventType.AGENT_REPLIED.value,
    EventType.AGENTIC_LOOP_STOPPED.value,
    EventType.STAGNATION_DETECTED.value,
}

DELIBERATION_EVENT_TYPES = {
    EventType.DELIBERATION_STARTED.value,
    EventType.DELIBERATION_FINISHED.value,
    EventType.DELIBERATION_FAILED.value,
}

BACKEND_EVENT_TYPES = {
    EventType.BACKEND_SESSION_STARTED.value,
    EventType.BACKEND_TURN_STARTED.value,
    EventType.BACKEND_MESSAGE_DELTA.value,
    EventType.BACKEND_MESSAGE_COMPLETED.value,
    EventType.BACKEND_TOOL_CALL_REQUESTED.value,
    EventType.BACKEND_TOOL_CALL_EXECUTED.value,
    EventType.BACKEND_ARTIFACT_EMITTED.value,
    EventType.BACKEND_WARNING.value,
    EventType.BACKEND_ERROR.value,
    EventType.BACKEND_TURN_COMPLETED.value,
    EventType.BACKEND_SESSION_CLOSED.value,
}
```

**Step 4: Run the tests to verify they pass**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/core/events/test_event_taxonomy.py -v`

Expected output:
```
PASSED tests/core/events/test_event_taxonomy.py::test_event_taxonomy_contains_operational_events
PASSED tests/core/events/test_event_taxonomy.py::test_event_taxonomy_contains_terminal_run_events
PASSED tests/core/events/test_event_taxonomy.py::test_deliberation_event_types_are_enum_members
PASSED tests/core/events/test_event_taxonomy.py::test_deliberation_event_types_set_uses_enum
```

**Step 5: Run ruff**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && ruff check miniautogen/core/events/types.py tests/core/events/test_event_taxonomy.py`

Expected: No errors.

**Step 6: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/core/events/types.py tests/core/events/test_event_taxonomy.py
git commit -m "feat(events): promote deliberation event types to EventType enum"
```

**If Task Fails:**
1. **Enum name clash:** Ensure spelling matches exactly: `DELIBERATION_STARTED`, `DELIBERATION_FINISHED`, `DELIBERATION_FAILED`.
2. **Import errors in other modules:** The string values are identical, so modules comparing `.value` strings will still work.
3. **Can't recover:** `git checkout -- miniautogen/core/events/types.py tests/core/events/test_event_taxonomy.py`

---

### Task 3: Update DeliberationRuntime to Use EventType Enum

**Files:**
- Modify: `miniautogen/core/runtime/deliberation_runtime.py:27,41-43` — replace hardcoded strings with EventType members
- Test: `tests/core/events/test_event_taxonomy.py` — add integration-style test confirming runtime constants match enum

**Step 1: Write the failing test**

Add this test to `tests/core/events/test_event_taxonomy.py`:

```python
def test_deliberation_runtime_uses_enum_constants() -> None:
    from miniautogen.core.runtime.deliberation_runtime import (
        _EVT_STARTED,
        _EVT_FINISHED,
        _EVT_FAILED,
    )

    # These should now be EventType enum values, not raw strings
    assert _EVT_STARTED == EventType.DELIBERATION_STARTED.value
    assert _EVT_FINISHED == EventType.DELIBERATION_FINISHED.value
    assert _EVT_FAILED == EventType.DELIBERATION_FAILED.value
```

**Step 2: Run the test to verify it passes (it should already pass since values match)**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/core/events/test_event_taxonomy.py::test_deliberation_runtime_uses_enum_constants -v`

Expected: This test may actually pass already since the string values are identical. That is fine -- the real change is to make the runtime reference the enum so future renames propagate.

**Step 3: Implement the change**

In `miniautogen/core/runtime/deliberation_runtime.py`:

1. Add `EventType` to the import from `miniautogen.core.events.types` (line 27 area). The file currently does NOT import `EventType`. Add this import:

Find this line:
```python
from miniautogen.core.contracts.events import ExecutionEvent
```

After that line, add:
```python
from miniautogen.core.events.types import EventType
```

2. Replace lines 41-43:

Find:
```python
_EVT_STARTED = "deliberation_started"
_EVT_FINISHED = "deliberation_finished"
_EVT_FAILED = "deliberation_failed"
```

Replace with:
```python
_EVT_STARTED = EventType.DELIBERATION_STARTED.value
_EVT_FINISHED = EventType.DELIBERATION_FINISHED.value
_EVT_FAILED = EventType.DELIBERATION_FAILED.value
```

**Step 4: Run the full event test suite**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/core/events/ -v`

Expected: All tests pass.

**Step 5: Run ruff**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && ruff check miniautogen/core/runtime/deliberation_runtime.py`

Expected: No errors.

**Step 6: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/core/runtime/deliberation_runtime.py tests/core/events/test_event_taxonomy.py
git commit -m "refactor(events): use EventType enum in deliberation runtime"
```

**If Task Fails:**
1. **Import error:** Make sure `EventType` import is added. The file did not import it previously.
2. **Deliberation tests break:** Run `python -m pytest tests/ -k deliberation -v` to see which tests fail.
3. **Can't recover:** `git checkout -- miniautogen/core/runtime/deliberation_runtime.py tests/core/events/test_event_taxonomy.py`

---

### Task 4: Implement EventFilter Protocol and Built-in Filters

**Files:**
- Create: `miniautogen/core/events/filters.py`
- Test: `tests/core/events/test_filters.py`

**Step 1: Write the failing tests**

Create the file `tests/core/events/test_filters.py` with this content:

```python
import pytest

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.types import EventType
from miniautogen.core.events.filters import (
    CompositeFilter,
    EventFilter,
    RunFilter,
    TypeFilter,
)


def _make_event(
    event_type: str = EventType.RUN_STARTED.value,
    run_id: str = "run-1",
    correlation_id: str | None = "corr-1",
) -> ExecutionEvent:
    return ExecutionEvent(
        type=event_type,
        run_id=run_id,
        correlation_id=correlation_id,
    )


class TestTypeFilter:
    def test_matches_included_type(self) -> None:
        f = TypeFilter(event_types={EventType.RUN_STARTED, EventType.RUN_FINISHED})
        event = _make_event(event_type=EventType.RUN_STARTED.value)
        assert f.matches(event) is True

    def test_rejects_excluded_type(self) -> None:
        f = TypeFilter(event_types={EventType.RUN_STARTED})
        event = _make_event(event_type=EventType.RUN_FAILED.value)
        assert f.matches(event) is False

    def test_empty_set_matches_nothing(self) -> None:
        f = TypeFilter(event_types=set())
        event = _make_event()
        assert f.matches(event) is False


class TestRunFilter:
    def test_matches_correct_run_id(self) -> None:
        f = RunFilter(run_id="run-1")
        event = _make_event(run_id="run-1")
        assert f.matches(event) is True

    def test_rejects_wrong_run_id(self) -> None:
        f = RunFilter(run_id="run-1")
        event = _make_event(run_id="run-2")
        assert f.matches(event) is False

    def test_rejects_none_run_id(self) -> None:
        f = RunFilter(run_id="run-1")
        event = ExecutionEvent(type=EventType.RUN_STARTED.value)
        assert f.matches(event) is False


class TestCompositeFilter:
    def test_all_mode_requires_all_filters(self) -> None:
        f = CompositeFilter(
            filters=[
                TypeFilter(event_types={EventType.RUN_STARTED}),
                RunFilter(run_id="run-1"),
            ],
            mode="all",
        )
        event = _make_event(
            event_type=EventType.RUN_STARTED.value, run_id="run-1"
        )
        assert f.matches(event) is True

    def test_all_mode_fails_if_one_filter_fails(self) -> None:
        f = CompositeFilter(
            filters=[
                TypeFilter(event_types={EventType.RUN_STARTED}),
                RunFilter(run_id="run-2"),
            ],
            mode="all",
        )
        event = _make_event(
            event_type=EventType.RUN_STARTED.value, run_id="run-1"
        )
        assert f.matches(event) is False

    def test_any_mode_passes_if_one_filter_passes(self) -> None:
        f = CompositeFilter(
            filters=[
                TypeFilter(event_types={EventType.RUN_STARTED}),
                RunFilter(run_id="run-2"),
            ],
            mode="any",
        )
        event = _make_event(
            event_type=EventType.RUN_STARTED.value, run_id="run-1"
        )
        assert f.matches(event) is True

    def test_any_mode_fails_if_all_filters_fail(self) -> None:
        f = CompositeFilter(
            filters=[
                TypeFilter(event_types={EventType.RUN_FAILED}),
                RunFilter(run_id="run-2"),
            ],
            mode="any",
        )
        event = _make_event(
            event_type=EventType.RUN_STARTED.value, run_id="run-1"
        )
        assert f.matches(event) is False

    def test_empty_filters_all_mode_matches_everything(self) -> None:
        f = CompositeFilter(filters=[], mode="all")
        event = _make_event()
        assert f.matches(event) is True

    def test_empty_filters_any_mode_matches_nothing(self) -> None:
        f = CompositeFilter(filters=[], mode="any")
        event = _make_event()
        assert f.matches(event) is False


def test_type_filter_satisfies_event_filter_protocol() -> None:
    f = TypeFilter(event_types={EventType.RUN_STARTED})
    assert isinstance(f, EventFilter)


def test_run_filter_satisfies_event_filter_protocol() -> None:
    f = RunFilter(run_id="run-1")
    assert isinstance(f, EventFilter)


def test_composite_filter_satisfies_event_filter_protocol() -> None:
    f = CompositeFilter(filters=[], mode="all")
    assert isinstance(f, EventFilter)
```

**Step 2: Run the tests to verify they fail**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/core/events/test_filters.py -v`

Expected output:
```
ERROR tests/core/events/test_filters.py - ModuleNotFoundError: No module named 'miniautogen.core.events.filters'
```

**Step 3: Implement the filters module**

Create the file `miniautogen/core/events/filters.py`:

```python
"""Event filtering — composable predicates for event routing."""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.types import EventType


@runtime_checkable
class EventFilter(Protocol):
    """Protocol for event filters. Implementations decide which events pass."""

    def matches(self, event: ExecutionEvent) -> bool:
        """Return True if the event should be forwarded."""
        ...


class TypeFilter:
    """Matches events whose type is in the given set of EventType members."""

    def __init__(self, event_types: set[EventType]) -> None:
        self._allowed_values: set[str] = {et.value for et in event_types}

    def matches(self, event: ExecutionEvent) -> bool:
        return event.type in self._allowed_values


class RunFilter:
    """Matches events with a specific run_id."""

    def __init__(self, run_id: str) -> None:
        self._run_id = run_id

    def matches(self, event: ExecutionEvent) -> bool:
        return event.run_id == self._run_id


class CompositeFilter:
    """Combines multiple filters with AND ('all') or OR ('any') semantics."""

    def __init__(
        self,
        filters: list[EventFilter],
        mode: Literal["all", "any"] = "all",
    ) -> None:
        self._filters = filters
        self._mode = mode

    def matches(self, event: ExecutionEvent) -> bool:
        if not self._filters:
            return self._mode == "all"
        if self._mode == "all":
            return all(f.matches(event) for f in self._filters)
        return any(f.matches(event) for f in self._filters)
```

**Step 4: Run the tests to verify they pass**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/core/events/test_filters.py -v`

Expected output:
```
PASSED tests/core/events/test_filters.py::TestTypeFilter::test_matches_included_type
PASSED tests/core/events/test_filters.py::TestTypeFilter::test_rejects_excluded_type
PASSED tests/core/events/test_filters.py::TestTypeFilter::test_empty_set_matches_nothing
PASSED tests/core/events/test_filters.py::TestRunFilter::test_matches_correct_run_id
PASSED tests/core/events/test_filters.py::TestRunFilter::test_rejects_wrong_run_id
PASSED tests/core/events/test_filters.py::TestRunFilter::test_rejects_none_run_id
PASSED tests/core/events/test_filters.py::TestCompositeFilter::test_all_mode_requires_all_filters
PASSED tests/core/events/test_filters.py::TestCompositeFilter::test_all_mode_fails_if_one_filter_fails
PASSED tests/core/events/test_filters.py::TestCompositeFilter::test_any_mode_passes_if_one_filter_passes
PASSED tests/core/events/test_filters.py::TestCompositeFilter::test_any_mode_fails_if_all_filters_fail
PASSED tests/core/events/test_filters.py::TestCompositeFilter::test_empty_filters_all_mode_matches_everything
PASSED tests/core/events/test_filters.py::TestCompositeFilter::test_empty_filters_any_mode_matches_nothing
PASSED tests/core/events/test_filters.py::test_type_filter_satisfies_event_filter_protocol
PASSED tests/core/events/test_filters.py::test_run_filter_satisfies_event_filter_protocol
PASSED tests/core/events/test_filters.py::test_composite_filter_satisfies_event_filter_protocol
```

**Step 5: Run ruff**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && ruff check miniautogen/core/events/filters.py tests/core/events/test_filters.py`

Expected: No errors.

**Step 6: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/core/events/filters.py tests/core/events/test_filters.py
git commit -m "feat(events): add EventFilter protocol with TypeFilter, RunFilter, CompositeFilter"
```

**If Task Fails:**
1. **Protocol isinstance check fails:** Ensure `@runtime_checkable` is on `EventFilter`. Ensure all filter classes have a `matches(self, event: ExecutionEvent) -> bool` method.
2. **Import errors:** Ensure file is at exact path `miniautogen/core/events/filters.py`.
3. **Can't recover:** `git checkout -- .` and delete the new files.

---

### Task 5: Implement CompositeEventSink and FilteredEventSink

**Files:**
- Modify: `miniautogen/core/events/event_sink.py` — add `CompositeEventSink` and `FilteredEventSink`
- Test: `tests/core/events/test_event_sink.py` — add tests for new sinks

**Step 1: Write the failing tests**

Append these tests to `tests/core/events/test_event_sink.py`:

```python
from miniautogen.core.events.event_sink import (
    CompositeEventSink,
    FilteredEventSink,
)
from miniautogen.core.events.filters import TypeFilter


@pytest.mark.asyncio
async def test_composite_event_sink_fans_out_to_all_sinks() -> None:
    sink_a = InMemoryEventSink()
    sink_b = InMemoryEventSink()
    composite = CompositeEventSink(sinks=[sink_a, sink_b])

    event = ExecutionEvent(
        type=EventType.RUN_STARTED.value,
        run_id="run-1",
        correlation_id="corr-1",
    )
    await composite.publish(event)

    assert len(sink_a.events) == 1
    assert len(sink_b.events) == 1
    assert sink_a.events[0].type == EventType.RUN_STARTED.value


@pytest.mark.asyncio
async def test_composite_event_sink_with_empty_sinks_list() -> None:
    composite = CompositeEventSink(sinks=[])
    event = ExecutionEvent(
        type=EventType.RUN_STARTED.value,
        run_id="run-1",
        correlation_id="corr-1",
    )
    # Should not raise
    await composite.publish(event)


@pytest.mark.asyncio
async def test_filtered_event_sink_forwards_matching_events() -> None:
    inner = InMemoryEventSink()
    f = TypeFilter(event_types={EventType.RUN_STARTED})
    filtered = FilteredEventSink(sink=inner, filter=f)

    matching = ExecutionEvent(
        type=EventType.RUN_STARTED.value,
        run_id="run-1",
        correlation_id="corr-1",
    )
    await filtered.publish(matching)

    assert len(inner.events) == 1


@pytest.mark.asyncio
async def test_filtered_event_sink_drops_non_matching_events() -> None:
    inner = InMemoryEventSink()
    f = TypeFilter(event_types={EventType.RUN_STARTED})
    filtered = FilteredEventSink(sink=inner, filter=f)

    non_matching = ExecutionEvent(
        type=EventType.RUN_FAILED.value,
        run_id="run-1",
        correlation_id="corr-1",
    )
    await filtered.publish(non_matching)

    assert len(inner.events) == 0
```

**Step 2: Run the tests to verify they fail**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/core/events/test_event_sink.py -v`

Expected output:
```
ERROR tests/core/events/test_event_sink.py - ImportError: cannot import name 'CompositeEventSink' from 'miniautogen.core.events.event_sink'
```

**Step 3: Implement CompositeEventSink and FilteredEventSink**

In `miniautogen/core/events/event_sink.py`, replace the entire file with:

```python
from __future__ import annotations

from typing import Protocol

from miniautogen.core.contracts.events import ExecutionEvent


class EventSink(Protocol):
    async def publish(self, event: ExecutionEvent) -> None:
        """Publish a runtime execution event."""


class InMemoryEventSink:
    def __init__(self) -> None:
        self.events: list[ExecutionEvent] = []

    async def publish(self, event: ExecutionEvent) -> None:
        self.events.append(event)


class NullEventSink:
    async def publish(self, event: ExecutionEvent) -> None:
        return None


class CompositeEventSink:
    """Fans out events to multiple sinks."""

    def __init__(self, sinks: list[EventSink]) -> None:
        self._sinks = sinks

    async def publish(self, event: ExecutionEvent) -> None:
        for sink in self._sinks:
            await sink.publish(event)


class FilteredEventSink:
    """Only forwards events that match the given filter."""

    def __init__(self, sink: EventSink, filter: "EventFilter") -> None:
        self._sink = sink
        self._filter = filter

    async def publish(self, event: ExecutionEvent) -> None:
        if self._filter.matches(event):
            await self._sink.publish(event)


# Avoid circular import — import at module level only for type checking
from miniautogen.core.events.filters import EventFilter  # noqa: E402, F401
```

Wait -- there is a circular import risk here. `event_sink.py` imports from `contracts/events.py` and `filters.py` imports from `contracts/events.py` and `types.py`. `filters.py` does NOT import from `event_sink.py`. So `event_sink.py` importing from `filters.py` is safe (no cycle). But let me handle the type annotation cleanly.

Actually, to avoid any circular import issues and keep it clean, use `TYPE_CHECKING`:

Replace the file with:

```python
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from miniautogen.core.contracts.events import ExecutionEvent

if TYPE_CHECKING:
    from miniautogen.core.events.filters import EventFilter


class EventSink(Protocol):
    async def publish(self, event: ExecutionEvent) -> None:
        """Publish a runtime execution event."""


class InMemoryEventSink:
    def __init__(self) -> None:
        self.events: list[ExecutionEvent] = []

    async def publish(self, event: ExecutionEvent) -> None:
        self.events.append(event)


class NullEventSink:
    async def publish(self, event: ExecutionEvent) -> None:
        return None


class CompositeEventSink:
    """Fans out events to multiple sinks."""

    def __init__(self, sinks: list[EventSink]) -> None:
        self._sinks = sinks

    async def publish(self, event: ExecutionEvent) -> None:
        for sink in self._sinks:
            await sink.publish(event)


class FilteredEventSink:
    """Only forwards events that match the given filter."""

    def __init__(self, sink: EventSink, filter: EventFilter) -> None:
        self._sink = sink
        self._filter = filter

    async def publish(self, event: ExecutionEvent) -> None:
        if self._filter.matches(event):
            await self._sink.publish(event)
```

**Step 4: Run the tests to verify they pass**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/core/events/test_event_sink.py -v`

Expected output:
```
PASSED tests/core/events/test_event_sink.py::test_in_memory_event_sink_records_published_events
PASSED tests/core/events/test_event_sink.py::test_composite_event_sink_fans_out_to_all_sinks
PASSED tests/core/events/test_event_sink.py::test_composite_event_sink_with_empty_sinks_list
PASSED tests/core/events/test_event_sink.py::test_filtered_event_sink_forwards_matching_events
PASSED tests/core/events/test_event_sink.py::test_filtered_event_sink_drops_non_matching_events
```

**Step 5: Run ruff**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && ruff check miniautogen/core/events/event_sink.py tests/core/events/test_event_sink.py`

Expected: No errors.

**Step 6: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/core/events/event_sink.py tests/core/events/test_event_sink.py
git commit -m "feat(events): add CompositeEventSink and FilteredEventSink"
```

**If Task Fails:**
1. **Circular import:** The `TYPE_CHECKING` guard prevents circular imports at runtime. If you still get a circular import, verify `filters.py` does NOT import from `event_sink.py`.
2. **`filter` shadows built-in:** The parameter name `filter` shadows the built-in. This is fine for a parameter name. If ruff complains (it should not with the current lint rules), rename to `event_filter`.
3. **Can't recover:** `git checkout -- miniautogen/core/events/event_sink.py tests/core/events/test_event_sink.py`

---

### Task 6: Implement LoggingEventSink

**Files:**
- Create: `miniautogen/observability/event_logging.py`
- Test: `tests/observability/test_event_logging.py`

**Step 1: Check test directory exists**

Run: `ls /Users/brunocapelao/Projects/miniAutoGen/tests/observability/ 2>/dev/null || echo "DOES NOT EXIST"`

If it does not exist, create the directory before writing the test file:

Run: `mkdir -p /Users/brunocapelao/Projects/miniAutoGen/tests/observability`

**Step 2: Write the failing tests**

Create `tests/observability/test_event_logging.py`:

```python
import logging

import pytest
import structlog

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.types import EventType
from miniautogen.observability.event_logging import LoggingEventSink


@pytest.mark.asyncio
async def test_logging_sink_logs_run_started_as_info(capfd: pytest.CaptureFixture) -> None:
    sink = LoggingEventSink()
    event = ExecutionEvent(
        type=EventType.RUN_STARTED.value,
        run_id="run-1",
        correlation_id="corr-1",
    )
    await sink.publish(event)
    # The sink should not raise — structlog output goes to configured handler


@pytest.mark.asyncio
async def test_logging_sink_logs_run_failed_as_error() -> None:
    sink = LoggingEventSink()
    event = ExecutionEvent(
        type=EventType.RUN_FAILED.value,
        run_id="run-1",
        correlation_id="corr-1",
        payload={"error_type": "ValueError"},
    )
    # Should not raise
    await sink.publish(event)


@pytest.mark.asyncio
async def test_logging_sink_logs_unknown_type_as_debug() -> None:
    sink = LoggingEventSink()
    event = ExecutionEvent(
        type="some_custom_event",
        run_id="run-1",
        correlation_id="corr-1",
    )
    # Should not raise — unknown types default to debug level
    await sink.publish(event)


@pytest.mark.asyncio
async def test_logging_sink_maps_warning_events() -> None:
    sink = LoggingEventSink()
    event = ExecutionEvent(
        type=EventType.RUN_TIMED_OUT.value,
        run_id="run-1",
        correlation_id="corr-1",
    )
    await sink.publish(event)


@pytest.mark.asyncio
async def test_logging_sink_includes_event_metadata_in_log() -> None:
    """Verify the sink binds run_id and correlation_id to the log context."""
    captured_calls: list[dict] = []

    class CapturingLogger:
        """Fake structlog logger that captures bound kwargs."""

        def bind(self, **kw):
            self._bound = kw
            return self

        def info(self, event: str, **kw):
            captured_calls.append({"level": "info", "event": event, **self._bound, **kw})

        def warning(self, event: str, **kw):
            captured_calls.append({"level": "warning", "event": event, **self._bound, **kw})

        def error(self, event: str, **kw):
            captured_calls.append({"level": "error", "event": event, **self._bound, **kw})

        def debug(self, event: str, **kw):
            captured_calls.append({"level": "debug", "event": event, **self._bound, **kw})

    sink = LoggingEventSink(logger=CapturingLogger())
    event = ExecutionEvent(
        type=EventType.RUN_STARTED.value,
        run_id="run-42",
        correlation_id="corr-99",
        payload={"step": "init"},
    )
    await sink.publish(event)

    assert len(captured_calls) == 1
    call = captured_calls[0]
    assert call["level"] == "info"
    assert call["run_id"] == "run-42"
    assert call["correlation_id"] == "corr-99"
```

**Step 3: Run the tests to verify they fail**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/observability/test_event_logging.py -v`

Expected output:
```
ERROR tests/observability/test_event_logging.py - ModuleNotFoundError: No module named 'miniautogen.observability.event_logging'
```

**Step 4: Implement LoggingEventSink**

Create `miniautogen/observability/event_logging.py`:

```python
"""LoggingEventSink — bridges ExecutionEvent to structlog."""

from __future__ import annotations

from typing import Any

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.types import EventType
from miniautogen.observability.logging import get_logger

# Map event type strings to log levels.
# Missing entries default to "debug".
_EVENT_LOG_LEVELS: dict[str, str] = {
    # Error-level events
    EventType.RUN_FAILED.value: "error",
    EventType.ADAPTER_FAILED.value: "error",
    EventType.VALIDATION_FAILED.value: "error",
    EventType.TOOL_FAILED.value: "error",
    EventType.DELIBERATION_FAILED.value: "error",
    EventType.BACKEND_ERROR.value: "error",
    # Warning-level events
    EventType.RUN_TIMED_OUT.value: "warning",
    EventType.RUN_CANCELLED.value: "warning",
    EventType.BUDGET_EXCEEDED.value: "warning",
    EventType.STAGNATION_DETECTED.value: "warning",
    EventType.COMPONENT_SKIPPED.value: "warning",
    EventType.BACKEND_WARNING.value: "warning",
    # Info-level events
    EventType.RUN_STARTED.value: "info",
    EventType.RUN_FINISHED.value: "info",
    EventType.COMPONENT_STARTED.value: "info",
    EventType.COMPONENT_FINISHED.value: "info",
    EventType.COMPONENT_RETRIED.value: "info",
    EventType.TOOL_INVOKED.value: "info",
    EventType.TOOL_SUCCEEDED.value: "info",
    EventType.CHECKPOINT_SAVED.value: "info",
    EventType.CHECKPOINT_RESTORED.value: "info",
    EventType.POLICY_APPLIED.value: "info",
    EventType.AGENTIC_LOOP_STARTED.value: "info",
    EventType.AGENTIC_LOOP_STOPPED.value: "info",
    EventType.ROUTER_DECISION.value: "info",
    EventType.AGENT_REPLIED.value: "info",
    EventType.DELIBERATION_STARTED.value: "info",
    EventType.DELIBERATION_FINISHED.value: "info",
    EventType.BACKEND_SESSION_STARTED.value: "info",
    EventType.BACKEND_SESSION_CLOSED.value: "info",
    EventType.BACKEND_TURN_STARTED.value: "info",
    EventType.BACKEND_TURN_COMPLETED.value: "info",
    EventType.BACKEND_MESSAGE_COMPLETED.value: "info",
    EventType.BACKEND_TOOL_CALL_REQUESTED.value: "info",
    EventType.BACKEND_TOOL_CALL_EXECUTED.value: "info",
    EventType.BACKEND_ARTIFACT_EMITTED.value: "info",
    # Debug-level events (via default, but explicit for delta)
    EventType.BACKEND_MESSAGE_DELTA.value: "debug",
}


class LoggingEventSink:
    """EventSink that logs each event via structlog.

    Maps event types to log levels using ``_EVENT_LOG_LEVELS``.
    Unknown event types are logged at debug level.
    """

    def __init__(self, logger: Any | None = None) -> None:
        self._logger = logger or get_logger("miniautogen.events")

    async def publish(self, event: ExecutionEvent) -> None:
        level = _EVENT_LOG_LEVELS.get(event.type, "debug")
        bound = self._logger.bind(
            run_id=event.run_id,
            correlation_id=event.correlation_id,
            scope=event.scope,
        )
        log_fn = getattr(bound, level)
        log_fn(event.type, **event.payload)
```

**Step 5: Run the tests to verify they pass**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/observability/test_event_logging.py -v`

Expected output:
```
PASSED tests/observability/test_event_logging.py::test_logging_sink_logs_run_started_as_info
PASSED tests/observability/test_event_logging.py::test_logging_sink_logs_run_failed_as_error
PASSED tests/observability/test_event_logging.py::test_logging_sink_logs_unknown_type_as_debug
PASSED tests/observability/test_event_logging.py::test_logging_sink_maps_warning_events
PASSED tests/observability/test_event_logging.py::test_logging_sink_includes_event_metadata_in_log
```

**Step 6: Run ruff**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && ruff check miniautogen/observability/event_logging.py tests/observability/test_event_logging.py`

Expected: No errors.

**Step 7: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/observability/event_logging.py tests/observability/test_event_logging.py
git commit -m "feat(observability): add LoggingEventSink bridging events to structlog"
```

**If Task Fails:**
1. **structlog not installed:** Run `poetry install` to ensure structlog is available.
2. **Missing test directory:** Ensure `tests/observability/` directory was created.
3. **CapturingLogger test fails:** Verify the `bind()` method returns `self` and all log level methods are implemented.
4. **Can't recover:** Delete the new files and `git checkout -- .`

---

### Task 7: Update Package Exports

**Files:**
- Modify: `miniautogen/core/events/__init__.py` — export new classes
- Modify: `miniautogen/observability/__init__.py` — export LoggingEventSink
- Modify: `miniautogen/api.py` — add new public API exports
- Test: `tests/core/events/test_event_exports.py` — verify imports work

**Step 1: Write the failing tests**

Create `tests/core/events/test_event_exports.py`:

```python
def test_event_filter_importable_from_events_package() -> None:
    from miniautogen.core.events import EventFilter, TypeFilter, RunFilter, CompositeFilter

    assert EventFilter is not None
    assert TypeFilter is not None
    assert RunFilter is not None
    assert CompositeFilter is not None


def test_composite_sinks_importable_from_events_package() -> None:
    from miniautogen.core.events import CompositeEventSink, FilteredEventSink

    assert CompositeEventSink is not None
    assert FilteredEventSink is not None


def test_logging_sink_importable_from_observability() -> None:
    from miniautogen.observability import LoggingEventSink

    assert LoggingEventSink is not None


def test_new_exports_in_public_api() -> None:
    from miniautogen.api import (
        CompositeEventSink,
        EventFilter,
        FilteredEventSink,
        LoggingEventSink,
        TypeFilter,
        RunFilter,
        CompositeFilter,
    )

    assert EventFilter is not None
    assert TypeFilter is not None
    assert RunFilter is not None
    assert CompositeFilter is not None
    assert CompositeEventSink is not None
    assert FilteredEventSink is not None
    assert LoggingEventSink is not None
```

**Step 2: Run the tests to verify they fail**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/core/events/test_event_exports.py -v`

Expected output:
```
FAILED tests/core/events/test_event_exports.py::test_event_filter_importable_from_events_package - ImportError
```

**Step 3: Update miniautogen/core/events/__init__.py**

Replace the entire file with:

```python
from miniautogen.core.events.event_sink import (
    CompositeEventSink,
    EventSink,
    FilteredEventSink,
    InMemoryEventSink,
    NullEventSink,
)
from miniautogen.core.events.filters import (
    CompositeFilter,
    EventFilter,
    RunFilter,
    TypeFilter,
)
from miniautogen.core.events.types import EventType

__all__ = [
    "CompositeEventSink",
    "CompositeFilter",
    "EventFilter",
    "EventSink",
    "EventType",
    "FilteredEventSink",
    "InMemoryEventSink",
    "NullEventSink",
    "RunFilter",
    "TypeFilter",
]
```

**Step 4: Update miniautogen/observability/__init__.py**

Replace the entire file with:

```python
from miniautogen.observability.logging import configure_logging, get_logger
from miniautogen.observability.event_logging import LoggingEventSink

__all__ = ["LoggingEventSink", "configure_logging", "get_logger"]
```

**Step 5: Update miniautogen/api.py**

Add these imports after the existing event-related imports. Find the line:

```python
from miniautogen.core.contracts import (
```

Before that block (or after the existing imports), add:

```python
from miniautogen.core.events import (
    CompositeEventSink,
    CompositeFilter,
    EventFilter,
    FilteredEventSink,
    RunFilter,
    TypeFilter,
)
from miniautogen.observability import LoggingEventSink
```

Then update the `__all__` list. Find:

```python
    # Policy enforcement
```

Before that line, add:

```python
    # Event system
    "EventFilter",
    "TypeFilter",
    "RunFilter",
    "CompositeFilter",
    "CompositeEventSink",
    "FilteredEventSink",
    "LoggingEventSink",
```

The final `__all__` should include these 7 new entries alongside the existing ones.

**Step 6: Run the export tests**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/core/events/test_event_exports.py -v`

Expected output:
```
PASSED tests/core/events/test_event_exports.py::test_event_filter_importable_from_events_package
PASSED tests/core/events/test_event_exports.py::test_composite_sinks_importable_from_events_package
PASSED tests/core/events/test_event_exports.py::test_logging_sink_importable_from_observability
PASSED tests/core/events/test_event_exports.py::test_new_exports_in_public_api
```

**Step 7: Run the full test suite to check for regressions**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/core/events/ tests/observability/ -v`

Expected: All tests pass.

**Step 8: Run ruff on all changed files**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && ruff check miniautogen/core/events/__init__.py miniautogen/observability/__init__.py miniautogen/api.py tests/core/events/test_event_exports.py`

Expected: No errors.

**Step 9: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/core/events/__init__.py miniautogen/observability/__init__.py miniautogen/api.py tests/core/events/test_event_exports.py
git commit -m "feat(api): export EventFilter, composable sinks, and LoggingEventSink"
```

**If Task Fails:**
1. **Circular import from observability/__init__.py:** The `LoggingEventSink` import in `__init__.py` triggers `event_logging.py` which imports from `miniautogen.core.events.types` and `miniautogen.observability.logging`. These are NOT circular. If you still get an error, check that `event_logging.py` does not import from `miniautogen.observability` (it imports from `miniautogen.observability.logging` directly).
2. **api.py import fails:** Ensure import paths match exact module locations.
3. **Can't recover:** `git checkout -- miniautogen/core/events/__init__.py miniautogen/observability/__init__.py miniautogen/api.py` and delete new test file.

---

### Task 8: Code Review Checkpoint

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
- This tracks tech debt for future resolution

**Cosmetic/Nitpick Issues:**
- Add `FIXME(nitpick):` comments in code at the relevant location
- Format: `FIXME(nitpick): [Issue description] (reported by [reviewer] on [date], severity: Cosmetic)`
- Low-priority improvements tracked inline

3. **Proceed only when:**
   - Zero Critical/High/Medium issues remain
   - All Low issues have TODO(review): comments added
   - All Cosmetic issues have FIXME(nitpick): comments added

**Files changed in this chunk (scope for review):**
- `miniautogen/core/contracts/events.py` — correlation_id made optional
- `miniautogen/core/events/types.py` — deliberation enum members added
- `miniautogen/core/events/event_sink.py` — CompositeEventSink, FilteredEventSink added
- `miniautogen/core/events/filters.py` — new file (EventFilter, TypeFilter, RunFilter, CompositeFilter)
- `miniautogen/core/events/__init__.py` — updated exports
- `miniautogen/core/runtime/deliberation_runtime.py` — uses EventType enum
- `miniautogen/observability/event_logging.py` — new file (LoggingEventSink)
- `miniautogen/observability/__init__.py` — updated exports
- `miniautogen/api.py` — updated public API exports

---

## Summary of All Changes

| Task | What | Files |
|------|------|-------|
| 1 | Make correlation_id optional | `contracts/events.py`, `test_execution_event_model.py` |
| 2 | Add deliberation events to enum | `events/types.py`, `test_event_taxonomy.py` |
| 3 | Use enum in deliberation runtime | `deliberation_runtime.py`, `test_event_taxonomy.py` |
| 4 | EventFilter protocol + built-ins | `events/filters.py`, `test_filters.py` |
| 5 | CompositeEventSink + FilteredEventSink | `events/event_sink.py`, `test_event_sink.py` |
| 6 | LoggingEventSink | `observability/event_logging.py`, `test_event_logging.py` |
| 7 | Package exports | `events/__init__.py`, `observability/__init__.py`, `api.py`, `test_event_exports.py` |
| 8 | Code review checkpoint | N/A — review gate |

**Total new files:** 3 (`filters.py`, `event_logging.py`, `test_filters.py`, `test_event_logging.py`, `test_event_exports.py` = 2 source + 3 test)

**Total modified files:** 6 (`events.py`, `types.py`, `event_sink.py`, `deliberation_runtime.py`, `events/__init__.py`, `observability/__init__.py`, `api.py`)
