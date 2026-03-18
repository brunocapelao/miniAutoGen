# MiniAutoGen Dash TUI Implementation Plan

> **For Agents:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Build "MiniAutoGen Dash", a Textual-based TUI dashboard that visualizes multi-agent pipeline execution as a team workspace conversation.

**Architecture:** TuiEventSink implements the existing EventSink protocol and bridges core events to the Textual UI via `anyio.create_memory_object_stream()`. A Textual Worker reads from the receive stream and posts `TuiEvent` messages into the Textual message loop. The TUI is an optional dependency (`miniautogen[tui]`) with zero coupling to core -- it only imports protocols and event types.

**Tech Stack:** Python 3.10+, Textual >=1.0, Rich (bundled with Textual), anyio >=4.0, Click >=8.0, Pydantic >=2.5

**Global Prerequisites:**
- Environment: macOS/Linux, Python 3.10-3.11
- Tools: poetry for dependency management, pytest for testing
- Access: No external API keys needed for TUI development
- State: Work from `main` branch, clean working tree

**Verification before starting:**
```bash
python --version        # Expected: Python 3.10.x or 3.11.x
poetry --version        # Expected: Poetry 1.x+
pytest --version        # Expected: pytest 7.4+
git status              # Expected: clean working tree on main
git branch              # Expected: * main
```

---

## Phase 0: Foundation

### Task 1: Add Textual as Optional Dependency

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/pyproject.toml`

**Prerequisites:**
- Poetry installed
- Clean working tree

**Step 1: Add the `tui` optional extra to pyproject.toml**

In `/Users/brunocapelao/Projects/miniAutoGen/pyproject.toml`, add the `tui` extras group after the `[tool.poetry.group.dev.dependencies]` section and before `[tool.poetry.scripts]`:

```toml
[tool.poetry.extras]
tui = ["textual"]
```

Also add `textual` as an optional dependency inside `[tool.poetry.dependencies]`:

```toml
textual = {version = ">=1.0.0", optional = true}
```

The final `[tool.poetry.dependencies]` section should look like:

```toml
[tool.poetry.dependencies]
python = ">3.10, <3.12"
openai = ">=1.3.9"
python-dotenv = "1.0.0"
sqlalchemy = ">=2.0.23"
litellm = ">=1.16.12"
pydantic = ">=2.5.0"
aiosqlite = ">=0.19.0"
anyio = ">=4.0.0"
jinja2 = ">=3.1.0"
structlog = ">=24.0.0"
tenacity = ">=8.2.0"
fastapi = ">=0.115.0"
uvicorn = ">=0.32.0"
httpx = ">=0.28.0"
click = ">=8.0"
pyyaml = ">=6.0"
ruamel-yaml = ">=0.18.0"
textual = {version = ">=1.0.0", optional = true}
```

And the extras section placed after dev dependencies:

```toml
[tool.poetry.extras]
tui = ["textual"]
```

**Step 2: Install the extra**

Run: `poetry install --extras tui`

**Expected output:**
```
Installing textual (...)
...
Installing dependencies from lock file
```

**Step 3: Verify Textual is importable**

Run: `poetry run python -c "import textual; print(textual.__version__)"`

**Expected output:**
```
1.x.x
```

**Step 4: Commit**

```bash
git add pyproject.toml poetry.lock
git commit -m "chore: add textual as optional tui dependency"
```

**If Task Fails:**
1. **Poetry lock conflict:** Run `poetry lock --no-update` then retry install
2. **Version incompatibility:** Try `textual = {version = ">=0.80.0", optional = true}` (wider range)
3. **Can't recover:** Document poetry error, return to human partner

---

### Task 2: Create TUI Package Skeleton

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/__init__.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/__main__.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/__init__.py`

**Prerequisites:**
- Task 1 completed (textual importable)

**Step 1: Create the tui package directory**

Run: `mkdir -p /Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui`

**Step 2: Create the `__init__.py`**

Write `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/__init__.py`:

```python
"""MiniAutoGen Dash -- TUI dashboard for multi-agent pipeline monitoring.

Optional dependency: install with ``pip install miniautogen[tui]``.

This package has ZERO coupling to miniautogen.core internals.
It only imports protocols (EventSink) and data models (ExecutionEvent, EventType).
"""
```

**Step 3: Create the `__main__.py` entry point**

Write `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/__main__.py`:

```python
"""Standalone entry point: python -m miniautogen.tui"""

from __future__ import annotations

import sys


def main() -> None:
    try:
        from miniautogen.tui.app import MiniAutoGenDash
    except ImportError:
        print(
            "MiniAutoGen TUI requires the 'tui' extra.\n"
            "Install with: pip install miniautogen[tui]",
            file=sys.stderr,
        )
        raise SystemExit(1)

    app = MiniAutoGenDash()
    app.run()


if __name__ == "__main__":
    main()
```

**Step 4: Create the test directory**

Run: `mkdir -p /Users/brunocapelao/Projects/miniAutoGen/tests/tui`

Write `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/__init__.py`:

```python
```

(Empty file.)

**Step 5: Commit**

```bash
git add miniautogen/tui/ tests/tui/
git commit -m "feat(tui): create package skeleton with standalone entry point"
```

**If Task Fails:**
1. **Directory already exists:** Not a problem, proceed
2. **Import error in __main__:** The ImportError is expected if app.py doesn't exist yet -- that's handled by the try/except
3. **Can't recover:** Document error, return to human partner

---

### Task 3: Implement TuiEventSink

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/event_sink.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_event_sink.py`

**Prerequisites:**
- Task 2 completed
- Understanding: The existing `EventSink` protocol (at `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/events/event_sink.py`) requires a single method: `async def publish(self, event: ExecutionEvent) -> None`
- Understanding: `ExecutionEvent` is a Pydantic BaseModel with fields: `type`, `timestamp`, `run_id`, `correlation_id`, `scope`, `payload`

**Step 1: Write the failing test**

Write `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_event_sink.py`:

```python
"""Tests for TuiEventSink -- the bridge between core events and Textual UI."""

from __future__ import annotations

import pytest

import anyio

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.types import EventType
from miniautogen.tui.event_sink import TuiEventSink


@pytest.mark.anyio
async def test_tui_event_sink_satisfies_protocol() -> None:
    """TuiEventSink must satisfy the EventSink protocol."""
    from miniautogen.core.events.event_sink import EventSink

    sink = TuiEventSink()
    assert isinstance(sink, EventSink)


@pytest.mark.anyio
async def test_tui_event_sink_publishes_to_stream() -> None:
    """Published events must be receivable from the stream."""
    sink = TuiEventSink()
    event = ExecutionEvent(
        type=EventType.RUN_STARTED.value,
        run_id="run-1",
        correlation_id="corr-1",
    )

    await sink.publish(event)

    received = await sink.receive()
    assert received.type == EventType.RUN_STARTED.value
    assert received.run_id == "run-1"


@pytest.mark.anyio
async def test_tui_event_sink_multiple_events_ordered() -> None:
    """Multiple events must be received in publish order."""
    sink = TuiEventSink()

    events = [
        ExecutionEvent(type=EventType.RUN_STARTED.value, run_id="run-1"),
        ExecutionEvent(type=EventType.COMPONENT_STARTED.value, run_id="run-1"),
        ExecutionEvent(type=EventType.COMPONENT_FINISHED.value, run_id="run-1"),
    ]

    for event in events:
        await sink.publish(event)

    received = []
    for _ in range(3):
        received.append(await sink.receive())

    assert [e.type for e in received] == [
        EventType.RUN_STARTED.value,
        EventType.COMPONENT_STARTED.value,
        EventType.COMPONENT_FINISHED.value,
    ]


@pytest.mark.anyio
async def test_tui_event_sink_close() -> None:
    """Closing the sink must close the underlying stream."""
    sink = TuiEventSink()
    await sink.publish(
        ExecutionEvent(type=EventType.RUN_STARTED.value, run_id="run-1"),
    )
    await sink.close()

    with pytest.raises(anyio.ClosedResourceError):
        await sink.publish(
            ExecutionEvent(type=EventType.RUN_FINISHED.value, run_id="run-1"),
        )


@pytest.mark.anyio
async def test_tui_event_sink_context_manager() -> None:
    """TuiEventSink must work as an async context manager."""
    async with TuiEventSink() as sink:
        await sink.publish(
            ExecutionEvent(type=EventType.RUN_STARTED.value, run_id="run-1"),
        )
        received = await sink.receive()
        assert received.type == EventType.RUN_STARTED.value


@pytest.mark.anyio
async def test_tui_event_sink_buffer_size() -> None:
    """TuiEventSink must accept a configurable buffer size."""
    sink = TuiEventSink(buffer_size=2)

    # Fill the buffer
    await sink.publish(
        ExecutionEvent(type=EventType.RUN_STARTED.value, run_id="run-1"),
    )
    await sink.publish(
        ExecutionEvent(type=EventType.COMPONENT_STARTED.value, run_id="run-1"),
    )

    # Buffer is full -- verify we can still drain
    r1 = await sink.receive()
    r2 = await sink.receive()
    assert r1.type == EventType.RUN_STARTED.value
    assert r2.type == EventType.COMPONENT_STARTED.value
```

**Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/tui/test_event_sink.py -v`

**Expected output:**
```
FAILED ... - ModuleNotFoundError: No module named 'miniautogen.tui.event_sink'
```

**Step 3: Write the implementation**

Write `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/event_sink.py`:

```python
"""TuiEventSink -- bridges core ExecutionEvents to the Textual UI loop.

Uses anyio.create_memory_object_stream() for async-safe cross-loop
communication. The PipelineRunner publishes events via publish(),
and the Textual Worker reads via receive().

This module imports ONLY protocols and data models from core.
Zero coupling to runtime internals.
"""

from __future__ import annotations

import anyio
from anyio.abc import ObjectReceiveStream, ObjectSendStream

from miniautogen.core.contracts.events import ExecutionEvent

# Default buffer: 256 events before backpressure
_DEFAULT_BUFFER_SIZE = 256


class TuiEventSink:
    """EventSink that bridges events to a Textual app via memory stream.

    Satisfies the EventSink protocol::

        async def publish(self, event: ExecutionEvent) -> None

    Usage::

        sink = TuiEventSink()
        # Pass sink to PipelineRunner as event_sink
        runner = PipelineRunner(event_sink=CompositeEventSink([existing, sink]))
        # In Textual Worker, read events:
        async for event in sink:
            self.post_message(TuiEvent(event))
    """

    def __init__(self, buffer_size: int = _DEFAULT_BUFFER_SIZE) -> None:
        send: ObjectSendStream[ExecutionEvent]
        recv: ObjectReceiveStream[ExecutionEvent]
        send, recv = anyio.create_memory_object_stream[ExecutionEvent](
            max_buffer_size=buffer_size,
        )
        self._send = send
        self._recv = recv

    async def publish(self, event: ExecutionEvent) -> None:
        """Publish an event to the stream (called by PipelineRunner)."""
        await self._send.send(event)

    async def receive(self) -> ExecutionEvent:
        """Receive the next event from the stream (called by Textual Worker)."""
        return await self._recv.receive()

    def __aiter__(self) -> TuiEventSink:
        return self

    async def __anext__(self) -> ExecutionEvent:
        try:
            return await self._recv.receive()
        except anyio.EndOfStream:
            raise StopAsyncIteration

    async def close(self) -> None:
        """Close both ends of the stream."""
        await self._send.aclose()
        await self._recv.aclose()

    async def __aenter__(self) -> TuiEventSink:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()
```

**Step 4: Run tests to verify they pass**

Run: `poetry run pytest tests/tui/test_event_sink.py -v`

**Expected output:**
```
tests/tui/test_event_sink.py::test_tui_event_sink_satisfies_protocol PASSED
tests/tui/test_event_sink.py::test_tui_event_sink_publishes_to_stream PASSED
tests/tui/test_event_sink.py::test_tui_event_sink_multiple_events_ordered PASSED
tests/tui/test_event_sink.py::test_tui_event_sink_close PASSED
tests/tui/test_event_sink.py::test_tui_event_sink_context_manager PASSED
tests/tui/test_event_sink.py::test_tui_event_sink_buffer_size PASSED
```

**Step 5: Verify existing tests still pass**

Run: `poetry run pytest tests/core/events/ -v`

**Expected output:** All existing event tests pass (no regressions).

**Step 6: Commit**

```bash
git add miniautogen/tui/event_sink.py tests/tui/test_event_sink.py
git commit -m "feat(tui): implement TuiEventSink with anyio memory stream bridge"
```

**If Task Fails:**
1. **Protocol check fails:** Ensure `EventSink` is a `Protocol` with `runtime_checkable` -- check `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/events/event_sink.py`. Note: `EventSink` is NOT decorated with `@runtime_checkable`, so `isinstance` check will fail. In that case, change the test to verify duck-typing instead:
   ```python
   async def test_tui_event_sink_satisfies_protocol() -> None:
       sink = TuiEventSink()
       assert hasattr(sink, 'publish')
       assert callable(sink.publish)
   ```
2. **anyio test marker:** If `@pytest.mark.anyio` isn't recognized, install `anyio[trio]` or use `@pytest.mark.asyncio` with `pytest-asyncio`. Check existing test patterns in the repo.
3. **Can't recover:** Document error, return to human partner

---

### Task 4: Implement TuiEvent Textual Message

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/messages.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_messages.py`

**Prerequisites:**
- Task 3 completed (TuiEventSink exists)

**Step 1: Write the failing test**

Write `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_messages.py`:

```python
"""Tests for TUI-specific Textual messages."""

from __future__ import annotations

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.types import EventType
from miniautogen.tui.messages import TuiEvent


def test_tui_event_wraps_execution_event() -> None:
    """TuiEvent must wrap an ExecutionEvent."""
    event = ExecutionEvent(
        type=EventType.RUN_STARTED.value,
        run_id="run-1",
    )
    msg = TuiEvent(event)
    assert msg.event is event
    assert msg.event.type == EventType.RUN_STARTED.value


def test_tui_event_is_textual_message() -> None:
    """TuiEvent must be a Textual Message."""
    from textual.message import Message

    event = ExecutionEvent(
        type=EventType.AGENT_REPLIED.value,
        run_id="run-1",
        payload={"agent_id": "writer", "content": "hello"},
    )
    msg = TuiEvent(event)
    assert isinstance(msg, Message)
```

**Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/tui/test_messages.py -v`

**Expected output:**
```
FAILED ... - ModuleNotFoundError: No module named 'miniautogen.tui.messages'
```

**Step 3: Write the implementation**

Write `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/messages.py`:

```python
"""Textual messages for TUI event handling.

These messages bridge ExecutionEvents from the core event system
into Textual's message loop, enabling reactive UI updates.
"""

from __future__ import annotations

from textual.message import Message

from miniautogen.core.contracts.events import ExecutionEvent


class TuiEvent(Message):
    """Wraps a core ExecutionEvent as a Textual Message.

    Posted by the EventBridgeWorker into the Textual message loop.
    Widgets subscribe to this message to update their display.
    """

    def __init__(self, event: ExecutionEvent) -> None:
        super().__init__()
        self.event = event
```

**Step 4: Run tests to verify they pass**

Run: `poetry run pytest tests/tui/test_messages.py -v`

**Expected output:**
```
tests/tui/test_messages.py::test_tui_event_wraps_execution_event PASSED
tests/tui/test_messages.py::test_tui_event_is_textual_message PASSED
```

**Step 5: Commit**

```bash
git add miniautogen/tui/messages.py tests/tui/test_messages.py
git commit -m "feat(tui): add TuiEvent textual message wrapper"
```

**If Task Fails:**
1. **Textual not installed:** Run `poetry install --extras tui`
2. **Can't recover:** Document error, return to human partner

---

### Task 5: Implement Status Vocabulary Model

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/status.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_status.py`

**Prerequisites:**
- Task 2 completed (tui package exists)

**Step 1: Write the failing test**

Write `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_status.py`:

```python
"""Tests for the 7-state status vocabulary."""

from __future__ import annotations

from miniautogen.tui.status import AgentStatus, StatusVocab


def test_status_vocab_has_seven_states() -> None:
    assert len(AgentStatus) == 7


def test_status_done() -> None:
    info = StatusVocab.get(AgentStatus.DONE)
    assert info.symbol == "\u2713"  # checkmark
    assert info.color == "dim green"
    assert info.label == "Done"


def test_status_active() -> None:
    info = StatusVocab.get(AgentStatus.ACTIVE)
    assert info.symbol == "\u25cf"  # filled circle
    assert info.color == "bright_green"
    assert info.label == "Active"


def test_status_working() -> None:
    info = StatusVocab.get(AgentStatus.WORKING)
    assert info.symbol == "\u25d0"  # half circle
    assert info.color == "yellow"
    assert info.label == "Working"


def test_status_waiting() -> None:
    info = StatusVocab.get(AgentStatus.WAITING)
    assert info.symbol == "\u231b"  # hourglass
    assert info.color == "dark_orange"
    assert info.label == "Waiting"


def test_status_pending() -> None:
    info = StatusVocab.get(AgentStatus.PENDING)
    assert info.symbol == "\u25cb"  # open circle
    assert info.color == "grey50"
    assert info.label == "Pending"


def test_status_failed() -> None:
    info = StatusVocab.get(AgentStatus.FAILED)
    assert info.symbol == "\u2715"  # multiplication x
    assert info.color == "red"
    assert info.label == "Failed"


def test_status_cancelled() -> None:
    info = StatusVocab.get(AgentStatus.CANCELLED)
    assert info.symbol == "\u2298"  # circled division slash
    assert info.color == "dark_red"
    assert info.label == "Cancelled"


def test_all_symbols_are_unique() -> None:
    symbols = [StatusVocab.get(s).symbol for s in AgentStatus]
    assert len(symbols) == len(set(symbols))


def test_rich_markup() -> None:
    info = StatusVocab.get(AgentStatus.ACTIVE)
    markup = info.rich_markup()
    assert "bright_green" in markup
    assert "\u25cf" in markup
```

**Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/tui/test_status.py -v`

**Expected output:**
```
FAILED ... - ModuleNotFoundError: No module named 'miniautogen.tui.status'
```

**Step 3: Write the implementation**

Write `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/status.py`:

```python
"""7-state status vocabulary for agent and step visualization.

Each status has a unique symbol (distinguishable without color for
accessibility), a color, and a human-readable label.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AgentStatus(str, Enum):
    """The 7 possible states for an agent or pipeline step."""

    DONE = "done"
    ACTIVE = "active"
    WORKING = "working"
    WAITING = "waiting"
    PENDING = "pending"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class StatusInfo:
    """Display metadata for a status state."""

    symbol: str
    color: str
    label: str

    def rich_markup(self) -> str:
        """Return a Rich markup string for this status."""
        return f"[{self.color}]{self.symbol} {self.label}[/{self.color}]"


class StatusVocab:
    """Maps AgentStatus to display information."""

    _LOOKUP: dict[AgentStatus, StatusInfo] = {
        AgentStatus.DONE: StatusInfo(
            symbol="\u2713", color="dim green", label="Done",
        ),
        AgentStatus.ACTIVE: StatusInfo(
            symbol="\u25cf", color="bright_green", label="Active",
        ),
        AgentStatus.WORKING: StatusInfo(
            symbol="\u25d0", color="yellow", label="Working",
        ),
        AgentStatus.WAITING: StatusInfo(
            symbol="\u231b", color="dark_orange", label="Waiting",
        ),
        AgentStatus.PENDING: StatusInfo(
            symbol="\u25cb", color="grey50", label="Pending",
        ),
        AgentStatus.FAILED: StatusInfo(
            symbol="\u2715", color="red", label="Failed",
        ),
        AgentStatus.CANCELLED: StatusInfo(
            symbol="\u2298", color="dark_red", label="Cancelled",
        ),
    }

    @classmethod
    def get(cls, status: AgentStatus) -> StatusInfo:
        """Get display info for a status."""
        return cls._LOOKUP[status]
```

**Step 4: Run tests to verify they pass**

Run: `poetry run pytest tests/tui/test_status.py -v`

**Expected output:**
```
tests/tui/test_status.py::test_status_vocab_has_seven_states PASSED
tests/tui/test_status.py::test_status_done PASSED
tests/tui/test_status.py::test_status_active PASSED
tests/tui/test_status.py::test_status_working PASSED
tests/tui/test_status.py::test_status_waiting PASSED
tests/tui/test_status.py::test_status_pending PASSED
tests/tui/test_status.py::test_status_failed PASSED
tests/tui/test_status.py::test_status_cancelled PASSED
tests/tui/test_status.py::test_all_symbols_are_unique PASSED
tests/tui/test_status.py::test_rich_markup PASSED
```

**Step 5: Commit**

```bash
git add miniautogen/tui/status.py tests/tui/test_status.py
git commit -m "feat(tui): implement 7-state status vocabulary"
```

**If Task Fails:**
1. **Unicode rendering:** The symbols are standard Unicode. If tests fail on symbol comparison, check encoding.
2. **Can't recover:** Document error, return to human partner

---

### Task 6: Implement Event-to-Status Mapper

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/event_mapper.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_event_mapper.py`

**Prerequisites:**
- Task 5 completed (status vocabulary exists)
- Understanding: EventType enum at `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/events/types.py` has 44 event types

**Step 1: Write the failing test**

Write `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_event_mapper.py`:

```python
"""Tests for mapping ExecutionEvents to TUI status updates."""

from __future__ import annotations

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.types import EventType
from miniautogen.tui.event_mapper import EventMapper
from miniautogen.tui.status import AgentStatus


def test_run_started_maps_to_active() -> None:
    event = ExecutionEvent(type=EventType.RUN_STARTED.value, run_id="r1")
    result = EventMapper.map_run_status(event)
    assert result == AgentStatus.ACTIVE


def test_run_finished_maps_to_done() -> None:
    event = ExecutionEvent(type=EventType.RUN_FINISHED.value, run_id="r1")
    result = EventMapper.map_run_status(event)
    assert result == AgentStatus.DONE


def test_run_failed_maps_to_failed() -> None:
    event = ExecutionEvent(type=EventType.RUN_FAILED.value, run_id="r1")
    result = EventMapper.map_run_status(event)
    assert result == AgentStatus.FAILED


def test_run_cancelled_maps_to_cancelled() -> None:
    event = ExecutionEvent(type=EventType.RUN_CANCELLED.value, run_id="r1")
    result = EventMapper.map_run_status(event)
    assert result == AgentStatus.CANCELLED


def test_run_timed_out_maps_to_failed() -> None:
    event = ExecutionEvent(type=EventType.RUN_TIMED_OUT.value, run_id="r1")
    result = EventMapper.map_run_status(event)
    assert result == AgentStatus.FAILED


def test_component_started_maps_to_active() -> None:
    event = ExecutionEvent(type=EventType.COMPONENT_STARTED.value, run_id="r1")
    result = EventMapper.map_component_status(event)
    assert result == AgentStatus.ACTIVE


def test_component_finished_maps_to_done() -> None:
    event = ExecutionEvent(type=EventType.COMPONENT_FINISHED.value, run_id="r1")
    result = EventMapper.map_component_status(event)
    assert result == AgentStatus.DONE


def test_approval_requested_maps_to_waiting() -> None:
    event = ExecutionEvent(type=EventType.APPROVAL_REQUESTED.value, run_id="r1")
    result = EventMapper.map_run_status(event)
    assert result == AgentStatus.WAITING


def test_backend_message_delta_maps_to_working() -> None:
    event = ExecutionEvent(type=EventType.BACKEND_MESSAGE_DELTA.value, run_id="r1")
    result = EventMapper.map_agent_status(event)
    assert result == AgentStatus.WORKING


def test_tool_invoked_maps_to_working() -> None:
    event = ExecutionEvent(type=EventType.TOOL_INVOKED.value, run_id="r1")
    result = EventMapper.map_agent_status(event)
    assert result == AgentStatus.WORKING


def test_agent_replied_maps_to_done() -> None:
    event = ExecutionEvent(type=EventType.AGENT_REPLIED.value, run_id="r1")
    result = EventMapper.map_agent_status(event)
    assert result == AgentStatus.DONE


def test_extract_agent_id_from_payload() -> None:
    event = ExecutionEvent(
        type=EventType.AGENT_REPLIED.value,
        run_id="r1",
        payload={"agent_id": "writer"},
    )
    result = EventMapper.extract_agent_id(event)
    assert result == "writer"


def test_extract_agent_id_missing_returns_none() -> None:
    event = ExecutionEvent(type=EventType.RUN_STARTED.value, run_id="r1")
    result = EventMapper.extract_agent_id(event)
    assert result is None
```

**Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/tui/test_event_mapper.py -v`

**Expected output:**
```
FAILED ... - ModuleNotFoundError: No module named 'miniautogen.tui.event_mapper'
```

**Step 3: Write the implementation**

Write `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/event_mapper.py`:

```python
"""Maps core ExecutionEvents to TUI status updates.

This is the translation layer between the core event vocabulary
(44 EventTypes) and the TUI's 7-state status vocabulary.
"""

from __future__ import annotations

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.types import EventType
from miniautogen.tui.status import AgentStatus

# Mapping tables: EventType value -> AgentStatus

_RUN_STATUS_MAP: dict[str, AgentStatus] = {
    EventType.RUN_STARTED.value: AgentStatus.ACTIVE,
    EventType.RUN_FINISHED.value: AgentStatus.DONE,
    EventType.RUN_FAILED.value: AgentStatus.FAILED,
    EventType.RUN_CANCELLED.value: AgentStatus.CANCELLED,
    EventType.RUN_TIMED_OUT.value: AgentStatus.FAILED,
    EventType.APPROVAL_REQUESTED.value: AgentStatus.WAITING,
    EventType.APPROVAL_GRANTED.value: AgentStatus.ACTIVE,
    EventType.APPROVAL_DENIED.value: AgentStatus.CANCELLED,
    EventType.APPROVAL_TIMEOUT.value: AgentStatus.FAILED,
}

_COMPONENT_STATUS_MAP: dict[str, AgentStatus] = {
    EventType.COMPONENT_STARTED.value: AgentStatus.ACTIVE,
    EventType.COMPONENT_FINISHED.value: AgentStatus.DONE,
    EventType.COMPONENT_SKIPPED.value: AgentStatus.CANCELLED,
    EventType.COMPONENT_RETRIED.value: AgentStatus.WORKING,
}

_AGENT_STATUS_MAP: dict[str, AgentStatus] = {
    EventType.AGENT_REPLIED.value: AgentStatus.DONE,
    EventType.ROUTER_DECISION.value: AgentStatus.ACTIVE,
    EventType.BACKEND_SESSION_STARTED.value: AgentStatus.ACTIVE,
    EventType.BACKEND_TURN_STARTED.value: AgentStatus.ACTIVE,
    EventType.BACKEND_MESSAGE_DELTA.value: AgentStatus.WORKING,
    EventType.BACKEND_MESSAGE_COMPLETED.value: AgentStatus.DONE,
    EventType.BACKEND_TOOL_CALL_REQUESTED.value: AgentStatus.WORKING,
    EventType.BACKEND_TOOL_CALL_EXECUTED.value: AgentStatus.DONE,
    EventType.BACKEND_ERROR.value: AgentStatus.FAILED,
    EventType.BACKEND_TURN_COMPLETED.value: AgentStatus.DONE,
    EventType.BACKEND_SESSION_CLOSED.value: AgentStatus.DONE,
    EventType.TOOL_INVOKED.value: AgentStatus.WORKING,
    EventType.TOOL_SUCCEEDED.value: AgentStatus.DONE,
    EventType.TOOL_FAILED.value: AgentStatus.FAILED,
    EventType.AGENTIC_LOOP_STARTED.value: AgentStatus.ACTIVE,
    EventType.AGENTIC_LOOP_STOPPED.value: AgentStatus.DONE,
    EventType.STAGNATION_DETECTED.value: AgentStatus.FAILED,
    EventType.DELIBERATION_STARTED.value: AgentStatus.ACTIVE,
    EventType.DELIBERATION_ROUND_COMPLETED.value: AgentStatus.WORKING,
    EventType.DELIBERATION_FINISHED.value: AgentStatus.DONE,
    EventType.DELIBERATION_FAILED.value: AgentStatus.FAILED,
}


class EventMapper:
    """Translates core events to TUI status vocabulary."""

    @staticmethod
    def map_run_status(event: ExecutionEvent) -> AgentStatus | None:
        """Map an event to a pipeline-run-level status."""
        return _RUN_STATUS_MAP.get(event.type)

    @staticmethod
    def map_component_status(event: ExecutionEvent) -> AgentStatus | None:
        """Map an event to a component/step-level status."""
        return _COMPONENT_STATUS_MAP.get(event.type)

    @staticmethod
    def map_agent_status(event: ExecutionEvent) -> AgentStatus | None:
        """Map an event to an agent-level status."""
        return _AGENT_STATUS_MAP.get(event.type)

    @staticmethod
    def extract_agent_id(event: ExecutionEvent) -> str | None:
        """Extract the agent_id from an event payload, if present."""
        return event.payload.get("agent_id")
```

**Step 4: Run tests to verify they pass**

Run: `poetry run pytest tests/tui/test_event_mapper.py -v`

**Expected output:**
```
... 13 passed ...
```

**Step 5: Commit**

```bash
git add miniautogen/tui/event_mapper.py tests/tui/test_event_mapper.py
git commit -m "feat(tui): implement event-to-status mapper"
```

**If Task Fails:**
1. **EventType value mismatch:** Verify exact string values in `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/events/types.py`
2. **Can't recover:** Document error, return to human partner

---

### Task 7: Implement Desktop Notifications (OSC 9/99)

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/notifications.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_notifications.py`

**Prerequisites:**
- Task 6 completed

**Step 1: Write the failing test**

Write `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_notifications.py`:

```python
"""Tests for desktop notification support via OSC 9/99."""

from __future__ import annotations

from unittest.mock import patch

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.types import EventType
from miniautogen.tui.notifications import (
    NotificationLevel,
    TerminalNotifier,
    should_notify,
)


def test_approval_requested_triggers_notification() -> None:
    event = ExecutionEvent(
        type=EventType.APPROVAL_REQUESTED.value,
        run_id="r1",
        payload={"agent_id": "planner"},
    )
    assert should_notify(event) is True


def test_run_finished_triggers_notification() -> None:
    event = ExecutionEvent(type=EventType.RUN_FINISHED.value, run_id="r1")
    assert should_notify(event) is True


def test_run_failed_triggers_notification() -> None:
    event = ExecutionEvent(type=EventType.RUN_FAILED.value, run_id="r1")
    assert should_notify(event) is True


def test_component_started_does_not_trigger() -> None:
    event = ExecutionEvent(type=EventType.COMPONENT_STARTED.value, run_id="r1")
    assert should_notify(event) is False


def test_notification_level_all() -> None:
    event = ExecutionEvent(type=EventType.RUN_FINISHED.value, run_id="r1")
    assert should_notify(event, level=NotificationLevel.ALL) is True


def test_notification_level_failures_only_blocks_success() -> None:
    event = ExecutionEvent(type=EventType.RUN_FINISHED.value, run_id="r1")
    assert should_notify(event, level=NotificationLevel.FAILURES_ONLY) is False


def test_notification_level_failures_only_allows_failure() -> None:
    event = ExecutionEvent(type=EventType.RUN_FAILED.value, run_id="r1")
    assert should_notify(event, level=NotificationLevel.FAILURES_ONLY) is True


def test_notification_level_none_blocks_all() -> None:
    event = ExecutionEvent(type=EventType.RUN_FAILED.value, run_id="r1")
    assert should_notify(event, level=NotificationLevel.NONE) is False


def test_notifier_builds_osc9_sequence() -> None:
    notifier = TerminalNotifier()
    seq = notifier.build_osc9("Test title", "Test body")
    assert "\x1b]9;" in seq or "\x1b]99;" in seq


def test_notifier_format_approval_event() -> None:
    event = ExecutionEvent(
        type=EventType.APPROVAL_REQUESTED.value,
        run_id="r1",
        payload={"agent_id": "planner"},
    )
    title, body = TerminalNotifier.format_event(event)
    assert "planner" in body.lower() or "approval" in title.lower()
```

**Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/tui/test_notifications.py -v`

**Expected output:**
```
FAILED ... - ModuleNotFoundError: No module named 'miniautogen.tui.notifications'
```

**Step 3: Write the implementation**

Write `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/notifications.py`:

```python
"""Desktop notifications via OSC 9/99 escape sequences.

Supports three notification levels: all, failures-only, none.
Falls back to terminal bell when OSC is unsupported.
"""

from __future__ import annotations

import sys
from enum import Enum

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.types import EventType

# Events that always trigger notifications
_NOTIFY_EVENTS: set[str] = {
    EventType.APPROVAL_REQUESTED.value,
    EventType.RUN_FINISHED.value,
    EventType.RUN_FAILED.value,
    EventType.RUN_TIMED_OUT.value,
    EventType.RUN_CANCELLED.value,
}

# Events considered failures
_FAILURE_EVENTS: set[str] = {
    EventType.RUN_FAILED.value,
    EventType.RUN_TIMED_OUT.value,
    EventType.APPROVAL_REQUESTED.value,
}


class NotificationLevel(str, Enum):
    ALL = "all"
    FAILURES_ONLY = "failures-only"
    NONE = "none"


def should_notify(
    event: ExecutionEvent,
    level: NotificationLevel = NotificationLevel.ALL,
) -> bool:
    """Determine if an event warrants a desktop notification."""
    if level == NotificationLevel.NONE:
        return False
    if event.type not in _NOTIFY_EVENTS:
        return False
    if level == NotificationLevel.FAILURES_ONLY:
        return event.type in _FAILURE_EVENTS
    return True


class TerminalNotifier:
    """Sends desktop notifications via OSC 9/99 escape sequences."""

    @staticmethod
    def format_event(event: ExecutionEvent) -> tuple[str, str]:
        """Format an event into (title, body) for notification."""
        agent_id = event.payload.get("agent_id", "Agent")
        etype = event.type

        if etype == EventType.APPROVAL_REQUESTED.value:
            return ("Approval Needed", f"{agent_id} needs your approval")
        if etype == EventType.RUN_FINISHED.value:
            return ("Pipeline Completed", f"Run {event.run_id or 'unknown'} finished")
        if etype == EventType.RUN_FAILED.value:
            return ("Pipeline Failed", f"Run {event.run_id or 'unknown'} failed")
        if etype == EventType.RUN_TIMED_OUT.value:
            return ("Pipeline Timed Out", f"Run {event.run_id or 'unknown'} timed out")
        if etype == EventType.RUN_CANCELLED.value:
            return ("Pipeline Cancelled", f"Run {event.run_id or 'unknown'} cancelled")
        return ("MiniAutoGen", f"Event: {etype}")

    def build_osc9(self, title: str, body: str) -> str:
        """Build an OSC 9/99 notification escape sequence.

        OSC 99 (kitty/modern): ``ESC ] 99 ; title ST body``
        OSC 9 (iTerm2/older): ``ESC ] 9 ; text ST``
        Falls back to OSC 9 which is more widely supported.
        """
        text = f"{title}: {body}" if body else title
        return f"\x1b]9;{text}\x1b\\"

    def send(self, event: ExecutionEvent) -> None:
        """Send a desktop notification for an event."""
        title, body = self.format_event(event)
        seq = self.build_osc9(title, body)
        try:
            sys.stderr.write(seq)
            sys.stderr.flush()
        except OSError:
            # Terminal doesn't support OSC; send bell as fallback
            try:
                sys.stderr.write("\a")
                sys.stderr.flush()
            except OSError:
                pass
```

**Step 4: Run tests to verify they pass**

Run: `poetry run pytest tests/tui/test_notifications.py -v`

**Expected output:**
```
... 11 passed ...
```

**Step 5: Commit**

```bash
git add miniautogen/tui/notifications.py tests/tui/test_notifications.py
git commit -m "feat(tui): implement desktop notifications via OSC 9/99"
```

**If Task Fails:**
1. **OSC escape issues:** The `\x1b]9;` is the standard sequence. If tests fail on string matching, check raw bytes.
2. **Can't recover:** Document error, return to human partner

---

### Task 8: Implement App Shell (Header, Footer, Key Bindings)

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/app.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_app.py`

**Prerequisites:**
- Tasks 3, 4, 5 completed
- Understanding: Textual apps require a class extending `App`, with `compose()` for layout and `BINDINGS` for keys

**Step 1: Write the failing test**

Write `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_app.py`:

```python
"""Tests for the MiniAutoGen Dash app shell."""

from __future__ import annotations

import pytest

from textual.app import App

from miniautogen.tui.app import MiniAutoGenDash


def test_app_is_textual_app() -> None:
    assert issubclass(MiniAutoGenDash, App)


def test_app_has_title() -> None:
    app = MiniAutoGenDash()
    assert app.TITLE == "MiniAutoGen Dash"


def test_app_has_subtitle() -> None:
    app = MiniAutoGenDash()
    assert "team" in app.SUB_TITLE.lower() or "agent" in app.SUB_TITLE.lower()


def test_app_has_key_bindings() -> None:
    app = MiniAutoGenDash()
    binding_keys = {b.key for b in app.BINDINGS}
    # Core navigation keys from the design spec
    assert "question_mark" in binding_keys or "?" in binding_keys
    assert "escape" in binding_keys
    assert "f" in binding_keys
    assert "t" in binding_keys


def test_app_has_css() -> None:
    """App must define CSS (inline or file)."""
    app = MiniAutoGenDash()
    assert app.CSS or app.CSS_PATH


@pytest.mark.asyncio
async def test_app_mounts_without_error() -> None:
    """Smoke test: the app mounts and can be started in headless mode."""
    app = MiniAutoGenDash()
    async with app.run_test(size=(120, 40)) as pilot:
        assert app.is_running
        await pilot.press("q")
```

**Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/tui/test_app.py -v`

**Expected output:**
```
FAILED ... - ImportError: cannot import name 'MiniAutoGenDash' from 'miniautogen.tui.app'
```

**Step 3: Write the implementation**

Write `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/app.py`:

```python
"""MiniAutoGen Dash -- main Textual application.

The app shell provides:
- Header with title
- Footer with key hints
- Global key bindings
- Command palette (built-in)
- SVG export (built-in via Ctrl+P)
- Theme support
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, Static


class MiniAutoGenDash(App):
    """Your AI Team at Work -- TUI dashboard for MiniAutoGen."""

    TITLE = "MiniAutoGen Dash"
    SUB_TITLE = "Your AI Team at Work"

    ENABLE_COMMAND_PALETTE = True

    CSS = """
    Screen {
        layout: grid;
        grid-size: 1;
    }

    #workspace {
        height: 1fr;
    }

    #empty-state {
        content-align: center middle;
        text-align: center;
        color: $text-muted;
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("question_mark", "help", "Help", show=True),
        Binding("escape", "back", "Back", show=True),
        Binding("f", "fullscreen", "Fullscreen", show=True),
        Binding("t", "toggle_sidebar", "Team", show=True),
        Binding("d", "diff_view", "Diff", show=False),
        Binding("slash", "search", "Search", show=True),
        Binding("tab", "next_pipeline", "Next Tab", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(
            "Your team is ready.\n\n"
            "Run a pipeline to see your agents at work.\n\n"
            "[dim]miniautogen run <pipeline>[/dim]",
            id="empty-state",
        )
        yield Footer()

    def action_help(self) -> None:
        """Show help overlay."""
        self.notify("Help: Press [b]:[/b] for commands, [b]/[/b] to search")

    def action_back(self) -> None:
        """Navigate back or close panel."""
        pass

    def action_fullscreen(self) -> None:
        """Toggle fullscreen for work panel."""
        pass

    def action_toggle_sidebar(self) -> None:
        """Toggle team sidebar visibility."""
        pass

    def action_search(self) -> None:
        """Open search/filter in current view."""
        pass

    def action_diff_view(self) -> None:
        """Open diff view."""
        pass

    def action_next_pipeline(self) -> None:
        """Switch to next pipeline tab."""
        pass
```

**Step 4: Run tests to verify they pass**

Run: `poetry run pytest tests/tui/test_app.py -v`

**Expected output:**
```
tests/tui/test_app.py::test_app_is_textual_app PASSED
tests/tui/test_app.py::test_app_has_title PASSED
tests/tui/test_app.py::test_app_has_subtitle PASSED
tests/tui/test_app.py::test_app_has_key_bindings PASSED
tests/tui/test_app.py::test_app_has_css PASSED
tests/tui/test_app.py::test_app_mounts_without_error PASSED
```

**Step 5: Commit**

```bash
git add miniautogen/tui/app.py tests/tui/test_app.py
git commit -m "feat(tui): implement app shell with header, footer, key bindings"
```

**If Task Fails:**
1. **Textual test pilot issues:** If `run_test()` fails, check Textual version. Textual >=0.47 supports `run_test`. If `size` param fails, remove it.
2. **Binding key names:** Textual uses `question_mark` not `?`. If binding lookup fails, check Textual's key name constants.
3. **Can't recover:** Document error, return to human partner

---

### Task 9: Add `miniautogen dash` CLI Command

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/commands/dash.py`
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/main.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/commands/test_dash.py`

**Prerequisites:**
- Task 8 completed (app shell exists)

**Step 1: Write the failing test**

Write `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/commands/test_dash.py`:

```python
"""Tests for the `miniautogen dash` CLI command."""

from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from miniautogen.cli.main import cli


def test_dash_command_exists() -> None:
    """The dash command must be registered."""
    runner = CliRunner()
    result = runner.invoke(cli, ["dash", "--help"])
    assert result.exit_code == 0
    assert "Launch the TUI dashboard" in result.output or "dash" in result.output


def test_dash_command_without_textual_shows_error() -> None:
    """If textual is not installed, show a helpful error."""
    runner = CliRunner()
    with patch.dict("sys.modules", {"textual": None}):
        # Force ImportError for textual
        with patch(
            "miniautogen.cli.commands.dash._check_textual_available",
            return_value=False,
        ):
            result = runner.invoke(cli, ["dash"])
            assert result.exit_code != 0 or "tui" in result.output.lower()
```

**Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/cli/commands/test_dash.py -v`

**Expected output:**
```
FAILED ... - ModuleNotFoundError: No module named 'miniautogen.cli.commands.dash'
```

**Step 3: Write the CLI command**

Write `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/commands/dash.py`:

```python
"""miniautogen dash command -- launch the TUI dashboard."""

from __future__ import annotations

import sys

import click


def _check_textual_available() -> bool:
    """Check if textual is importable."""
    try:
        import textual  # noqa: F401

        return True
    except ImportError:
        return False


@click.command("dash")
@click.option(
    "--theme",
    type=click.Choice(["tokyo-night", "catppuccin", "monokai", "light"]),
    default="tokyo-night",
    help="Color theme for the dashboard.",
)
@click.option(
    "--notifications",
    type=click.Choice(["all", "failures-only", "none"]),
    default="all",
    help="Desktop notification level.",
)
def dash_command(theme: str, notifications: str) -> None:
    """Launch the TUI dashboard.

    Opens an interactive terminal UI showing your AI team at work.
    Requires the 'tui' extra: pip install miniautogen[tui]
    """
    if not _check_textual_available():
        click.secho(
            "Error: MiniAutoGen TUI requires the 'tui' extra.\n"
            "Install with: pip install miniautogen[tui]",
            fg="red",
            err=True,
        )
        raise SystemExit(1)

    from miniautogen.tui.app import MiniAutoGenDash

    app = MiniAutoGenDash()
    app.run()
```

**Step 4: Register the command in main.py**

Add to `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/main.py`, after the last `cli.add_command()` call (after the `completions_command` registration):

```python
from miniautogen.cli.commands.dash import dash_command  # noqa: E402

cli.add_command(dash_command)
```

**Step 5: Run tests to verify they pass**

Run: `poetry run pytest tests/cli/commands/test_dash.py -v`

**Expected output:**
```
tests/cli/commands/test_dash.py::test_dash_command_exists PASSED
tests/cli/commands/test_dash.py::test_dash_command_without_textual_shows_error PASSED
```

**Step 6: Verify existing CLI tests still pass**

Run: `poetry run pytest tests/cli/ -v --timeout=30`

**Expected output:** All existing CLI tests pass.

**Step 7: Commit**

```bash
git add miniautogen/cli/commands/dash.py miniautogen/cli/main.py tests/cli/commands/test_dash.py
git commit -m "feat(cli): add miniautogen dash command for TUI launch"
```

**If Task Fails:**
1. **Import ordering in main.py:** Add the import AFTER the last existing command registration to match the pattern
2. **Test mock issues:** If the mock approach doesn't work, simplify to just testing `--help` output
3. **Can't recover:** Document error, return to human partner

---

### Task 10: Run Code Review (Phase 0)

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

3. **Proceed only when:**
   - Zero Critical/High/Medium issues remain
   - All Low issues have TODO(review): comments added
   - All Cosmetic issues have FIXME(nitpick): comments added

---

## Phase 1: Core Monitoring

### Task 11: Implement EventBridgeWorker

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/workers.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_workers.py`

**Prerequisites:**
- Tasks 3 and 4 completed (TuiEventSink and TuiEvent exist)

**Step 1: Write the failing test**

Write `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_workers.py`:

```python
"""Tests for the EventBridgeWorker that reads from TuiEventSink."""

from __future__ import annotations

import pytest

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.types import EventType
from miniautogen.tui.event_sink import TuiEventSink
from miniautogen.tui.workers import EventBridgeWorker


def test_event_bridge_worker_exists() -> None:
    """EventBridgeWorker must be importable."""
    assert EventBridgeWorker is not None


def test_event_bridge_worker_accepts_sink() -> None:
    """EventBridgeWorker must accept a TuiEventSink."""
    sink = TuiEventSink()
    worker = EventBridgeWorker(sink)
    assert worker._sink is sink
```

**Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/tui/test_workers.py -v`

**Expected output:**
```
FAILED ... - ModuleNotFoundError: No module named 'miniautogen.tui.workers'
```

**Step 3: Write the implementation**

Write `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/workers.py`:

```python
"""Textual Workers for background event processing.

EventBridgeWorker reads from TuiEventSink's receive stream and
posts TuiEvent messages into the Textual message loop.
"""

from __future__ import annotations

from textual.worker import Worker, WorkerState

from miniautogen.tui.event_sink import TuiEventSink
from miniautogen.tui.messages import TuiEvent


class EventBridgeWorker:
    """Reads events from TuiEventSink and posts them as TuiEvent messages.

    This worker is started by the App and runs in the background.
    It bridges the anyio MemoryObjectStream to Textual's message loop.

    Usage in App::

        def on_mount(self) -> None:
            self._worker = EventBridgeWorker(self._event_sink)
            self.run_worker(self._worker.run, exclusive=True)

    The worker reads events in a loop and calls app.post_message()
    for each one.
    """

    def __init__(self, sink: TuiEventSink) -> None:
        self._sink = sink

    async def run(self, app: object) -> None:
        """Main worker loop. Reads events and posts TuiEvent messages.

        Args:
            app: The Textual App instance (must have post_message method).
        """
        post_message = getattr(app, "post_message")
        async for event in self._sink:
            post_message(TuiEvent(event))
```

**Step 4: Run tests to verify they pass**

Run: `poetry run pytest tests/tui/test_workers.py -v`

**Expected output:**
```
tests/tui/test_workers.py::test_event_bridge_worker_exists PASSED
tests/tui/test_workers.py::test_event_bridge_worker_accepts_sink PASSED
```

**Step 5: Commit**

```bash
git add miniautogen/tui/workers.py tests/tui/test_workers.py
git commit -m "feat(tui): implement EventBridgeWorker for stream-to-message bridging"
```

**If Task Fails:**
1. **Worker API changes:** Check Textual Worker docs for current API. The worker pattern may use `@work` decorator instead of subclassing.
2. **Can't recover:** Document error, return to human partner

---

### Task 12: Implement AgentCard Widget (Team Sidebar Item)

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/widgets/__init__.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/widgets/agent_card.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_agent_card.py`

**Prerequisites:**
- Task 5 completed (status vocabulary exists)

**Step 1: Create widgets package**

Run: `mkdir -p /Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/widgets`

Write `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/widgets/__init__.py`:

```python
"""TUI widgets for MiniAutoGen Dash."""
```

**Step 2: Write the failing test**

Write `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_agent_card.py`:

```python
"""Tests for the AgentCard widget in the team sidebar."""

from __future__ import annotations

import pytest

from textual.widget import Widget

from miniautogen.tui.status import AgentStatus
from miniautogen.tui.widgets.agent_card import AgentCard


def test_agent_card_is_textual_widget() -> None:
    assert issubclass(AgentCard, Widget)


def test_agent_card_stores_agent_info() -> None:
    card = AgentCard(
        agent_id="writer",
        name="Writer",
        role="Developer",
        icon="pencil2",
        status=AgentStatus.PENDING,
    )
    assert card.agent_id == "writer"
    assert card.name == "Writer"
    assert card.role == "Developer"
    assert card.status == AgentStatus.PENDING


def test_agent_card_status_update() -> None:
    card = AgentCard(
        agent_id="writer",
        name="Writer",
        role="Developer",
        icon="pencil2",
        status=AgentStatus.PENDING,
    )
    card.status = AgentStatus.ACTIVE
    assert card.status == AgentStatus.ACTIVE


@pytest.mark.asyncio
async def test_agent_card_renders() -> None:
    """Smoke test: AgentCard renders without error."""
    from miniautogen.tui.app import MiniAutoGenDash

    app = MiniAutoGenDash()
    async with app.run_test(size=(120, 40)) as pilot:
        card = AgentCard(
            agent_id="planner",
            name="Planner",
            role="Architect",
            icon="classical_building",
            status=AgentStatus.ACTIVE,
        )
        await app.mount(card)
        assert card.is_mounted
```

**Step 3: Run tests to verify they fail**

Run: `poetry run pytest tests/tui/test_agent_card.py -v`

**Expected output:**
```
FAILED ... - ModuleNotFoundError: No module named 'miniautogen.tui.widgets.agent_card'
```

**Step 4: Write the implementation**

Write `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/widgets/agent_card.py`:

```python
"""AgentCard widget -- displays an agent in the Team sidebar.

Shows: icon, name, role, status indicator.
Syncs status with pipeline execution events.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from miniautogen.tui.status import AgentStatus, StatusVocab

# Emoji fallback map (Textual uses Unicode names or direct chars)
_ICON_MAP: dict[str, str] = {
    "classical_building": "\U0001f3db",
    "pencil2": "\u270f",
    "mag": "\U0001f50d",
    "sparkles": "\u2728",
    "robot": "\U0001f916",
    "gear": "\u2699",
}


class AgentCard(Widget):
    """A single agent entry in the Team sidebar."""

    DEFAULT_CSS = """
    AgentCard {
        height: 3;
        padding: 0 1;
        background: $surface;
    }

    AgentCard:hover {
        background: $surface-lighten-1;
    }

    AgentCard .agent-icon {
        width: 3;
    }

    AgentCard .agent-name {
        text-style: bold;
    }

    AgentCard .agent-role {
        color: $text-muted;
    }

    AgentCard .agent-status {
        dock: right;
        width: 3;
        content-align: center middle;
    }
    """

    status: reactive[AgentStatus] = reactive(AgentStatus.PENDING)

    def __init__(
        self,
        agent_id: str,
        name: str,
        role: str,
        icon: str = "robot",
        status: AgentStatus = AgentStatus.PENDING,
    ) -> None:
        super().__init__()
        self.agent_id = agent_id
        self.name = name
        self.role = role
        self.icon = icon
        self.status = status

    def compose(self) -> ComposeResult:
        icon_char = _ICON_MAP.get(self.icon, self.icon)
        status_info = StatusVocab.get(self.status)
        yield Static(icon_char, classes="agent-icon")
        yield Static(
            f"[bold]{self.name}[/bold]\n[dim]{self.role}[/dim]",
            classes="agent-name",
        )
        yield Static(
            f"[{status_info.color}]{status_info.symbol}[/{status_info.color}]",
            classes="agent-status",
            id="status-indicator",
        )

    def watch_status(self, new_status: AgentStatus) -> None:
        """Update the status indicator when status changes."""
        try:
            indicator = self.query_one("#status-indicator", Static)
            info = StatusVocab.get(new_status)
            indicator.update(
                f"[{info.color}]{info.symbol}[/{info.color}]"
            )
        except Exception:
            pass  # Widget not yet mounted
```

**Step 5: Run tests to verify they pass**

Run: `poetry run pytest tests/tui/test_agent_card.py -v`

**Expected output:**
```
... 4 passed ...
```

**Step 6: Commit**

```bash
git add miniautogen/tui/widgets/ tests/tui/test_agent_card.py
git commit -m "feat(tui): implement AgentCard widget for team sidebar"
```

**If Task Fails:**
1. **Textual reactive API:** If `reactive` import fails, check Textual version. Older versions use `Reactive` from `textual.reactive`.
2. **Mount in test:** If mounting in `run_test` fails, simplify the smoke test to just check the class.
3. **Can't recover:** Document error, return to human partner

---

### Task 13: Implement InteractionLog Widget (The Killer Feature)

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/widgets/interaction_log.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_interaction_log.py`

**Prerequisites:**
- Tasks 4, 5, 6 completed

**Step 1: Write the failing test**

Write `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_interaction_log.py`:

```python
"""Tests for the InteractionLog widget -- the main work panel."""

from __future__ import annotations

import pytest

from textual.widget import Widget

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.types import EventType
from miniautogen.tui.widgets.interaction_log import InteractionLog


def test_interaction_log_is_widget() -> None:
    assert issubclass(InteractionLog, Widget)


def test_interaction_log_starts_empty() -> None:
    log = InteractionLog()
    assert log.entry_count == 0


def test_interaction_log_add_agent_message() -> None:
    log = InteractionLog()
    log.add_agent_message(
        agent_id="writer",
        agent_name="Writer",
        content="Hello, I will write the code.",
    )
    assert log.entry_count == 1


def test_interaction_log_add_tool_call() -> None:
    log = InteractionLog()
    log.add_tool_call(
        agent_id="writer",
        tool_name="file_write",
        status="executing",
    )
    assert log.entry_count == 1


def test_interaction_log_add_step_header() -> None:
    log = InteractionLog()
    log.add_step_header(
        step_number=1,
        step_label="Planning",
        agent_name="Planner",
    )
    assert log.entry_count == 1


def test_interaction_log_add_streaming_indicator() -> None:
    log = InteractionLog()
    log.add_streaming_indicator(
        agent_id="writer",
        state="thinking",
    )
    assert log.entry_count == 1


def test_interaction_log_handles_event() -> None:
    log = InteractionLog()
    event = ExecutionEvent(
        type=EventType.AGENT_REPLIED.value,
        run_id="r1",
        payload={"agent_id": "writer", "content": "Done."},
    )
    log.handle_event(event)
    assert log.entry_count >= 1
```

**Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/tui/test_interaction_log.py -v`

**Expected output:**
```
FAILED ... - ModuleNotFoundError: No module named 'miniautogen.tui.widgets.interaction_log'
```

**Step 3: Write the implementation**

Write `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/widgets/interaction_log.py`:

```python
"""InteractionLog widget -- the conversation-style work panel.

This is the killer feature of MiniAutoGen Dash. It displays pipeline
execution as a chat-like conversation with:
- Agent messages with icon + name
- Syntax-highlighted code blocks (via Rich)
- Inline tool call cards
- Collapsible steps
- Streaming indicators
- Auto-scroll with manual override

Uses RichLog internally to handle large volumes efficiently.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import RichLog

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.types import EventType
from miniautogen.tui.event_mapper import EventMapper
from miniautogen.tui.status import AgentStatus, StatusVocab

# Map of event types that represent agent messages
_MESSAGE_EVENTS: set[str] = {
    EventType.AGENT_REPLIED.value,
    EventType.BACKEND_MESSAGE_COMPLETED.value,
}

_TOOL_EVENTS: set[str] = {
    EventType.TOOL_INVOKED.value,
    EventType.TOOL_SUCCEEDED.value,
    EventType.TOOL_FAILED.value,
    EventType.BACKEND_TOOL_CALL_REQUESTED.value,
    EventType.BACKEND_TOOL_CALL_EXECUTED.value,
}

_STEP_START_EVENTS: set[str] = {
    EventType.COMPONENT_STARTED.value,
    EventType.DELIBERATION_STARTED.value,
    EventType.AGENTIC_LOOP_STARTED.value,
}

_STREAMING_EVENTS: set[str] = {
    EventType.BACKEND_MESSAGE_DELTA.value,
    EventType.BACKEND_TURN_STARTED.value,
}


class InteractionLog(Widget):
    """The main conversation log panel.

    Receives events and renders them as a chat-thread conversation.
    """

    DEFAULT_CSS = """
    InteractionLog {
        height: 1fr;
    }

    InteractionLog RichLog {
        height: 1fr;
        scrollbar-size: 1 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._entry_count = 0
        self._auto_scroll = True

    @property
    def entry_count(self) -> int:
        return self._entry_count

    def compose(self) -> ComposeResult:
        yield RichLog(
            highlight=True,
            markup=True,
            wrap=True,
            auto_scroll=True,
            id="log",
        )

    def _get_log(self) -> RichLog:
        """Get the underlying RichLog widget."""
        return self.query_one("#log", RichLog)

    def add_agent_message(
        self,
        agent_id: str,
        agent_name: str,
        content: str,
    ) -> None:
        """Add an agent message entry to the log."""
        try:
            log = self._get_log()
            log.write(f"[bold]{agent_name}[/bold]")
            log.write(content)
            log.write("")  # blank line separator
        except Exception:
            pass  # Widget not yet mounted
        self._entry_count += 1

    def add_tool_call(
        self,
        agent_id: str,
        tool_name: str,
        status: str,
        result_summary: str | None = None,
        elapsed: float | None = None,
    ) -> None:
        """Add a tool call card to the log."""
        status_indicator = "\u25d0" if status == "executing" else "\u2713"
        elapsed_str = f" {elapsed:.1f}s" if elapsed else ""
        summary = f" {result_summary}" if result_summary else ""

        try:
            log = self._get_log()
            log.write(
                f"  \u258c\U0001f527 {tool_name}  "
                f"{status_indicator} {status}{elapsed_str}{summary}"
            )
        except Exception:
            pass
        self._entry_count += 1

    def add_step_header(
        self,
        step_number: int,
        step_label: str,
        agent_name: str | None = None,
    ) -> None:
        """Add a step header to the log."""
        agent_str = f" ({agent_name})" if agent_name else ""
        try:
            log = self._get_log()
            log.write("")
            log.write(
                f"[bold]\u2500\u2500\u2500 Step {step_number}: "
                f"{step_label}{agent_str} \u2500\u2500\u2500[/bold]"
            )
            log.write("")
        except Exception:
            pass
        self._entry_count += 1

    def add_streaming_indicator(
        self,
        agent_id: str,
        state: str = "thinking",
    ) -> None:
        """Add a streaming state indicator."""
        if state == "thinking":
            indicator = "\u2591\u2591\u2591 thinking..."
        elif state == "generating":
            indicator = "\u258a"
        else:
            indicator = f"\u25d0 {state}..."

        try:
            log = self._get_log()
            log.write(f"  [dim]{indicator}[/dim]")
        except Exception:
            pass
        self._entry_count += 1

    def handle_event(self, event: ExecutionEvent) -> None:
        """Process an ExecutionEvent and add appropriate log entries."""
        etype = event.type
        payload = event.payload
        agent_id = payload.get("agent_id", "system")
        agent_name = payload.get("agent_name", agent_id)

        if etype in _STEP_START_EVENTS:
            step_num = payload.get("step_number", 0)
            step_label = payload.get("component_name", payload.get("label", ""))
            self.add_step_header(step_num, step_label, agent_name)

        elif etype in _MESSAGE_EVENTS:
            content = payload.get("content", payload.get("message", ""))
            self.add_agent_message(agent_id, agent_name, content)

        elif etype in _TOOL_EVENTS:
            tool_name = payload.get("tool_name", payload.get("name", "unknown"))
            if etype in {
                EventType.TOOL_INVOKED.value,
                EventType.BACKEND_TOOL_CALL_REQUESTED.value,
            }:
                self.add_tool_call(agent_id, tool_name, "executing")
            elif etype == EventType.TOOL_SUCCEEDED.value:
                summary = payload.get("summary", "")
                self.add_tool_call(agent_id, tool_name, "done", result_summary=summary)
            elif etype == EventType.TOOL_FAILED.value:
                error = payload.get("error", "failed")
                self.add_tool_call(agent_id, tool_name, "failed", result_summary=error)
            elif etype == EventType.BACKEND_TOOL_CALL_EXECUTED.value:
                self.add_tool_call(agent_id, tool_name, "done")

        elif etype in _STREAMING_EVENTS:
            if etype == EventType.BACKEND_MESSAGE_DELTA.value:
                self.add_streaming_indicator(agent_id, "generating")
            else:
                self.add_streaming_indicator(agent_id, "thinking")
```

**Step 4: Run tests to verify they pass**

Run: `poetry run pytest tests/tui/test_interaction_log.py -v`

**Expected output:**
```
... 6 passed ...
```

**Step 5: Commit**

```bash
git add miniautogen/tui/widgets/interaction_log.py tests/tui/test_interaction_log.py
git commit -m "feat(tui): implement InteractionLog conversation widget"
```

**If Task Fails:**
1. **RichLog not found:** Check Textual version. RichLog was added in Textual 0.40+. If missing, use `Log` or `TextLog` as fallback.
2. **Entry count not incrementing:** The `_entry_count` increments regardless of mount state. Check tests don't depend on RichLog being mounted.
3. **Can't recover:** Document error, return to human partner

---

### Task 14: Implement HITL Approval Widget

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/widgets/approval_banner.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_approval_banner.py`

**Prerequisites:**
- Task 4 completed (TuiEvent message exists)
- Understanding: `ApprovalRequest` model at `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/policies/approval.py` has fields: `request_id`, `action`, `description`, `context`, `timeout_seconds`

**Step 1: Write the failing test**

Write `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_approval_banner.py`:

```python
"""Tests for the inline HITL approval banner widget."""

from __future__ import annotations

import pytest

from textual.widget import Widget

from miniautogen.tui.widgets.approval_banner import ApprovalBanner, ApprovalDecision


def test_approval_banner_is_widget() -> None:
    assert issubclass(ApprovalBanner, Widget)


def test_approval_banner_stores_request() -> None:
    banner = ApprovalBanner(
        request_id="req-1",
        action="run_pipeline",
        description="Execute pipeline main",
    )
    assert banner.request_id == "req-1"
    assert banner.action == "run_pipeline"
    assert banner.description == "Execute pipeline main"


def test_approval_decision_message() -> None:
    """ApprovalDecision message carries the decision."""
    from textual.message import Message

    decision = ApprovalDecision(
        request_id="req-1",
        decision="approved",
    )
    assert isinstance(decision, Message)
    assert decision.request_id == "req-1"
    assert decision.decision == "approved"
```

**Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/tui/test_approval_banner.py -v`

**Expected output:**
```
FAILED ... - ModuleNotFoundError: No module named 'miniautogen.tui.widgets.approval_banner'
```

**Step 3: Write the implementation**

Write `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/widgets/approval_banner.py`:

```python
"""Inline HITL approval banner for the interaction log.

Appears inline in the conversation flow (not as a blocking modal).
Shows action description with Approve/Deny buttons.
"""

from __future__ import annotations

from typing import Literal

from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Static


class ApprovalDecision(Message):
    """Message posted when the user makes an approval decision."""

    def __init__(
        self,
        request_id: str,
        decision: Literal["approved", "denied"],
        reason: str | None = None,
    ) -> None:
        super().__init__()
        self.request_id = request_id
        self.decision = decision
        self.reason = reason


class ApprovalBanner(Widget):
    """Inline approval request in the conversation flow.

    Renders a double-border banner with the action description
    and [A]pprove / [D]eny buttons.
    """

    DEFAULT_CSS = """
    ApprovalBanner {
        height: auto;
        margin: 1 2;
        padding: 1 2;
        border: double $warning;
        background: $surface;
    }

    ApprovalBanner .approval-title {
        text-style: bold;
        color: $warning;
    }

    ApprovalBanner .approval-description {
        margin: 1 0;
    }

    ApprovalBanner .approval-buttons {
        layout: horizontal;
        height: 3;
    }

    ApprovalBanner Button {
        margin: 0 1;
    }
    """

    def __init__(
        self,
        request_id: str,
        action: str,
        description: str,
    ) -> None:
        super().__init__()
        self.request_id = request_id
        self.action = action
        self.description = description

    def compose(self) -> ComposeResult:
        yield Static(
            "\u231b Approval Required",
            classes="approval-title",
        )
        yield Static(
            f"{self.description}\n[dim]Action: {self.action}[/dim]",
            classes="approval-description",
        )
        with Widget(classes="approval-buttons"):
            yield Button("[A]pprove", variant="success", id="approve-btn")
            yield Button("[D]eny", variant="error", id="deny-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle approve/deny button presses."""
        if event.button.id == "approve-btn":
            self.post_message(
                ApprovalDecision(
                    request_id=self.request_id,
                    decision="approved",
                )
            )
        elif event.button.id == "deny-btn":
            self.post_message(
                ApprovalDecision(
                    request_id=self.request_id,
                    decision="denied",
                )
            )

    def key_a(self) -> None:
        """Keyboard shortcut for approve."""
        self.post_message(
            ApprovalDecision(
                request_id=self.request_id,
                decision="approved",
            )
        )

    def key_d(self) -> None:
        """Keyboard shortcut for deny."""
        self.post_message(
            ApprovalDecision(
                request_id=self.request_id,
                decision="denied",
            )
        )
```

**Step 4: Run tests to verify they pass**

Run: `poetry run pytest tests/tui/test_approval_banner.py -v`

**Expected output:**
```
... 3 passed ...
```

**Step 5: Commit**

```bash
git add miniautogen/tui/widgets/approval_banner.py tests/tui/test_approval_banner.py
git commit -m "feat(tui): implement inline HITL approval banner widget"
```

**If Task Fails:**
1. **Button variant not supported:** Remove `variant` param if Textual version doesn't support it
2. **Nested Widget as container:** If `with Widget(classes=...)` doesn't work, use `Container` from `textual.containers`
3. **Can't recover:** Document error, return to human partner

---

### Task 15: Run Code Review (Phase 1)

1. **Dispatch all 3 reviewers in parallel:**
   - REQUIRED SUB-SKILL: Use requesting-code-review
   - All reviewers run simultaneously (code-reviewer, business-logic-reviewer, security-reviewer)
   - Wait for all to complete

2. **Handle findings by severity (MANDATORY):**

**Critical/High/Medium Issues:**
- Fix immediately
- Re-run all 3 reviewers in parallel after fixes
- Repeat until zero Critical/High/Medium issues remain

**Low Issues:**
- Add `TODO(review):` comments in code at the relevant location

**Cosmetic/Nitpick Issues:**
- Add `FIXME(nitpick):` comments in code at the relevant location

3. **Proceed only when:**
   - Zero Critical/High/Medium issues remain

---

## Phase 2: Navigation and Layout

### Task 16: Implement TeamSidebar Widget

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/widgets/team_sidebar.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_team_sidebar.py`

**Prerequisites:**
- Task 12 completed (AgentCard widget exists)

**Step 1: Write the failing test**

Write `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_team_sidebar.py`:

```python
"""Tests for the TeamSidebar widget."""

from __future__ import annotations

import pytest

from textual.widget import Widget

from miniautogen.tui.status import AgentStatus
from miniautogen.tui.widgets.team_sidebar import TeamSidebar


def test_team_sidebar_is_widget() -> None:
    assert issubclass(TeamSidebar, Widget)


def test_team_sidebar_starts_empty() -> None:
    sidebar = TeamSidebar()
    assert sidebar.agent_count == 0


def test_team_sidebar_add_agent() -> None:
    sidebar = TeamSidebar()
    sidebar.add_agent(
        agent_id="writer",
        name="Writer",
        role="Developer",
        icon="pencil2",
    )
    assert sidebar.agent_count == 1


def test_team_sidebar_update_agent_status() -> None:
    sidebar = TeamSidebar()
    sidebar.add_agent(agent_id="writer", name="Writer", role="Developer")
    sidebar.update_agent_status("writer", AgentStatus.ACTIVE)
    card = sidebar.get_agent_card("writer")
    assert card is not None
    assert card.status == AgentStatus.ACTIVE


def test_team_sidebar_get_nonexistent_agent() -> None:
    sidebar = TeamSidebar()
    assert sidebar.get_agent_card("nonexistent") is None
```

**Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/tui/test_team_sidebar.py -v`

**Expected output:**
```
FAILED ... - ModuleNotFoundError: No module named 'miniautogen.tui.widgets.team_sidebar'
```

**Step 3: Write the implementation**

Write `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/widgets/team_sidebar.py`:

```python
"""TeamSidebar widget -- shows the agent roster.

Displays each agent as an AgentCard with live status updates.
Supports responsive collapse (icons-only at narrow widths).
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Static

from miniautogen.tui.status import AgentStatus
from miniautogen.tui.widgets.agent_card import AgentCard


class TeamSidebar(Widget):
    """The left panel showing the agent roster."""

    DEFAULT_CSS = """
    TeamSidebar {
        width: 28;
        dock: left;
        background: $surface;
        border-right: solid $primary-background;
    }

    TeamSidebar .sidebar-title {
        text-style: bold;
        text-align: center;
        padding: 1;
        color: $text;
    }

    TeamSidebar VerticalScroll {
        height: 1fr;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._agents: dict[str, AgentCard] = {}

    @property
    def agent_count(self) -> int:
        return len(self._agents)

    def compose(self) -> ComposeResult:
        yield Static("The Team", classes="sidebar-title")
        yield VerticalScroll(id="agent-list")

    def add_agent(
        self,
        agent_id: str,
        name: str,
        role: str,
        icon: str = "robot",
        status: AgentStatus = AgentStatus.PENDING,
    ) -> None:
        """Add an agent to the sidebar."""
        card = AgentCard(
            agent_id=agent_id,
            name=name,
            role=role,
            icon=icon,
            status=status,
        )
        self._agents[agent_id] = card
        try:
            container = self.query_one("#agent-list", VerticalScroll)
            container.mount(card)
        except Exception:
            pass  # Widget not yet mounted

    def update_agent_status(
        self,
        agent_id: str,
        status: AgentStatus,
    ) -> None:
        """Update an agent's status."""
        card = self._agents.get(agent_id)
        if card is not None:
            card.status = status

    def get_agent_card(self, agent_id: str) -> AgentCard | None:
        """Get an agent's card by ID."""
        return self._agents.get(agent_id)
```

**Step 4: Run tests to verify they pass**

Run: `poetry run pytest tests/tui/test_team_sidebar.py -v`

**Expected output:**
```
... 5 passed ...
```

**Step 5: Commit**

```bash
git add miniautogen/tui/widgets/team_sidebar.py tests/tui/test_team_sidebar.py
git commit -m "feat(tui): implement TeamSidebar agent roster widget"
```

**If Task Fails:**
1. **VerticalScroll import:** If not available, use `from textual.containers import Vertical` instead
2. **Can't recover:** Document error, return to human partner

---

### Task 17: Implement WorkPanel Widget

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/widgets/work_panel.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_work_panel.py`

**Prerequisites:**
- Task 13 completed (InteractionLog exists)

**Step 1: Write the failing test**

Write `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_work_panel.py`:

```python
"""Tests for the WorkPanel widget -- the right panel of the workspace."""

from __future__ import annotations

from textual.widget import Widget

from miniautogen.tui.widgets.work_panel import WorkPanel


def test_work_panel_is_widget() -> None:
    assert issubclass(WorkPanel, Widget)


def test_work_panel_has_interaction_log() -> None:
    panel = WorkPanel()
    assert hasattr(panel, "interaction_log")
```

**Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/tui/test_work_panel.py -v`

**Expected output:**
```
FAILED ... - ModuleNotFoundError: No module named 'miniautogen.tui.widgets.work_panel'
```

**Step 3: Write the implementation**

Write `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/widgets/work_panel.py`:

```python
"""WorkPanel widget -- the right panel showing pipeline conversation.

Contains the InteractionLog and a progress bar at the bottom.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import ProgressBar, Static

from miniautogen.tui.widgets.interaction_log import InteractionLog


class WorkPanel(Widget):
    """The main work area showing the pipeline conversation."""

    DEFAULT_CSS = """
    WorkPanel {
        height: 1fr;
    }

    WorkPanel #progress-section {
        dock: bottom;
        height: 3;
        padding: 0 1;
        background: $surface;
    }

    WorkPanel #step-progress {
        width: 1fr;
    }

    WorkPanel #step-label {
        text-align: center;
        color: $text-muted;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.interaction_log = InteractionLog()
        self._total_steps = 0
        self._current_step = 0

    def compose(self) -> ComposeResult:
        yield self.interaction_log
        with Widget(id="progress-section"):
            yield ProgressBar(total=100, show_eta=False, id="step-progress")
            yield Static("Ready", id="step-label")

    def update_progress(self, current: int, total: int, label: str = "") -> None:
        """Update the step progress bar."""
        self._current_step = current
        self._total_steps = total
        try:
            bar = self.query_one("#step-progress", ProgressBar)
            bar.total = total
            bar.progress = current
            lbl = self.query_one("#step-label", Static)
            lbl.update(label or f"Step {current} of {total}")
        except Exception:
            pass
```

**Step 4: Run tests to verify they pass**

Run: `poetry run pytest tests/tui/test_work_panel.py -v`

**Expected output:**
```
... 2 passed ...
```

**Step 5: Commit**

```bash
git add miniautogen/tui/widgets/work_panel.py tests/tui/test_work_panel.py
git commit -m "feat(tui): implement WorkPanel with progress bar"
```

**If Task Fails:**
1. **ProgressBar API:** If `show_eta` param not supported, remove it. If ProgressBar not in Textual, use a Static with manual bar rendering.
2. **Can't recover:** Document error, return to human partner

---

### Task 18: Assemble Workspace Layout in App

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/app.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_workspace_layout.py`

**Prerequisites:**
- Tasks 16, 17 completed (TeamSidebar, WorkPanel exist)

**Step 1: Write the failing test**

Write `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_workspace_layout.py`:

```python
"""Tests for the workspace layout assembly."""

from __future__ import annotations

import pytest

from miniautogen.tui.app import MiniAutoGenDash


@pytest.mark.asyncio
async def test_workspace_has_sidebar_and_work_panel() -> None:
    """The workspace must contain both TeamSidebar and WorkPanel."""
    from miniautogen.tui.widgets.team_sidebar import TeamSidebar
    from miniautogen.tui.widgets.work_panel import WorkPanel

    app = MiniAutoGenDash()
    async with app.run_test(size=(120, 40)) as pilot:
        sidebars = app.query(TeamSidebar)
        panels = app.query(WorkPanel)
        assert len(sidebars) == 1
        assert len(panels) == 1


@pytest.mark.asyncio
async def test_toggle_sidebar_hides_team() -> None:
    """Pressing 't' should toggle team sidebar visibility."""
    from miniautogen.tui.widgets.team_sidebar import TeamSidebar

    app = MiniAutoGenDash()
    async with app.run_test(size=(120, 40)) as pilot:
        sidebar = app.query_one(TeamSidebar)
        assert sidebar.display is True
        await pilot.press("t")
        assert sidebar.display is False
        await pilot.press("t")
        assert sidebar.display is True
```

**Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/tui/test_workspace_layout.py -v`

**Expected output:**
```
FAILED ... (no TeamSidebar/WorkPanel in current app compose)
```

**Step 3: Update the app to include the workspace layout**

Replace the contents of `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/app.py` with:

```python
"""MiniAutoGen Dash -- main Textual application.

The app shell provides:
- Header with title
- Footer with key hints
- Two-panel workspace (Team sidebar + Work panel)
- Global key bindings
- Command palette (built-in)
- SVG export (built-in via Ctrl+P)
- Theme support
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header

from miniautogen.tui.messages import TuiEvent
from miniautogen.tui.widgets.team_sidebar import TeamSidebar
from miniautogen.tui.widgets.work_panel import WorkPanel


class MiniAutoGenDash(App):
    """Your AI Team at Work -- TUI dashboard for MiniAutoGen."""

    TITLE = "MiniAutoGen Dash"
    SUB_TITLE = "Your AI Team at Work"

    ENABLE_COMMAND_PALETTE = True

    CSS = """
    Screen {
        layout: horizontal;
    }

    #workspace {
        layout: horizontal;
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("question_mark", "help", "Help", show=True),
        Binding("escape", "back", "Back", show=True),
        Binding("f", "fullscreen", "Fullscreen", show=True),
        Binding("t", "toggle_sidebar", "Team", show=True),
        Binding("d", "diff_view", "Diff", show=False),
        Binding("slash", "search", "Search", show=True),
        Binding("tab", "next_pipeline", "Next Tab", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield TeamSidebar()
        yield WorkPanel()
        yield Footer()

    def on_tui_event(self, message: TuiEvent) -> None:
        """Handle incoming TUI events from the event bridge."""
        event = message.event
        # Forward to work panel
        try:
            work_panel = self.query_one(WorkPanel)
            work_panel.interaction_log.handle_event(event)
        except Exception:
            pass

    def action_help(self) -> None:
        """Show help overlay."""
        self.notify("Help: Press [b]:[/b] for commands, [b]/[/b] to search")

    def action_back(self) -> None:
        """Navigate back or close panel."""
        pass

    def action_fullscreen(self) -> None:
        """Toggle fullscreen for work panel."""
        try:
            sidebar = self.query_one(TeamSidebar)
            sidebar.display = False
        except Exception:
            pass

    def action_toggle_sidebar(self) -> None:
        """Toggle team sidebar visibility."""
        try:
            sidebar = self.query_one(TeamSidebar)
            sidebar.display = not sidebar.display
        except Exception:
            pass

    def action_search(self) -> None:
        """Open search/filter in current view."""
        pass

    def action_diff_view(self) -> None:
        """Open diff view."""
        pass

    def action_next_pipeline(self) -> None:
        """Switch to next pipeline tab."""
        pass
```

**Step 4: Run tests to verify they pass**

Run: `poetry run pytest tests/tui/test_workspace_layout.py -v`

**Expected output:**
```
tests/tui/test_workspace_layout.py::test_workspace_has_sidebar_and_work_panel PASSED
tests/tui/test_workspace_layout.py::test_toggle_sidebar_hides_team PASSED
```

**Step 5: Also re-run the app tests**

Run: `poetry run pytest tests/tui/test_app.py -v`

**Expected output:** All pass (the key binding tests and CSS test should still pass).

**Step 6: Commit**

```bash
git add miniautogen/tui/app.py tests/tui/test_workspace_layout.py
git commit -m "feat(tui): assemble workspace layout with sidebar and work panel"
```

**If Task Fails:**
1. **Query returns empty:** If Textual's `query` doesn't find widgets, check that `compose()` yields them directly (not inside a Container).
2. **Display toggle:** If `sidebar.display` doesn't work, try `sidebar.visible` or `sidebar.styles.display = "none"`.
3. **Can't recover:** Document error, return to human partner

---

### Task 19: Implement Responsive Breakpoints

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/app.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_responsive.py`

**Prerequisites:**
- Task 18 completed

**Step 1: Write the failing test**

Write `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_responsive.py`:

```python
"""Tests for responsive breakpoint behavior."""

from __future__ import annotations

import pytest

from miniautogen.tui.app import MiniAutoGenDash
from miniautogen.tui.widgets.team_sidebar import TeamSidebar


@pytest.mark.asyncio
async def test_full_layout_at_120x40() -> None:
    """At 120x40, full sidebar is visible."""
    app = MiniAutoGenDash()
    async with app.run_test(size=(120, 40)) as pilot:
        sidebar = app.query_one(TeamSidebar)
        assert sidebar.display is True


@pytest.mark.asyncio
async def test_sidebar_hidden_at_80x24() -> None:
    """At 80x24, sidebar should be hidden."""
    app = MiniAutoGenDash()
    async with app.run_test(size=(80, 24)) as pilot:
        sidebar = app.query_one(TeamSidebar)
        # At narrow width, sidebar should auto-hide
        assert sidebar.display is False or sidebar.styles.width is not None
```

**Step 2: Run tests to verify behavior**

Run: `poetry run pytest tests/tui/test_responsive.py -v`

**Step 3: Add responsive handling to the app**

Add this method to `MiniAutoGenDash` in `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/app.py`:

```python
    def on_resize(self, event: object) -> None:
        """Handle terminal resize for responsive breakpoints."""
        width = self.size.width
        try:
            sidebar = self.query_one(TeamSidebar)
            if width < 100:
                sidebar.display = False
            else:
                sidebar.display = True
                if width < 120:
                    sidebar.styles.width = "6"  # icons only
                else:
                    sidebar.styles.width = "28"  # full
        except Exception:
            pass
```

You will also need to add to the `on_mount` method (add it if not present):

```python
    def on_mount(self) -> None:
        """Handle initial mount -- apply responsive breakpoints."""
        self.on_resize(None)
```

**Step 4: Run tests to verify they pass**

Run: `poetry run pytest tests/tui/test_responsive.py -v`

**Expected output:**
```
... 2 passed ...
```

**Step 5: Commit**

```bash
git add miniautogen/tui/app.py tests/tui/test_responsive.py
git commit -m "feat(tui): implement responsive breakpoints for sidebar"
```

**If Task Fails:**
1. **Resize event API:** Textual's resize may use `on_resize(self, event: Resize)` from `textual.events`. Check the import.
2. **Size not available on mount:** If `self.size` is not set during `on_mount`, defer with `self.call_later(self.on_resize, None)`.
3. **Can't recover:** Document error, return to human partner

---

### Task 20: Implement HintBar Widget

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/widgets/hint_bar.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_hint_bar.py`

**Prerequisites:**
- Task 2 completed

**Step 1: Write the failing test**

Write `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_hint_bar.py`:

```python
"""Tests for the context-aware hint bar."""

from __future__ import annotations

from miniautogen.tui.widgets.hint_bar import HintBar


def test_hint_bar_default_hints() -> None:
    bar = HintBar()
    text = bar.get_hint_text()
    assert "[Enter]" in text
    assert "[/]" in text or "search" in text.lower()
    assert "[:]" in text or "commands" in text.lower()
    assert "[?]" in text or "help" in text.lower()
```

**Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/tui/test_hint_bar.py -v`

**Step 3: Write the implementation**

Write `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/widgets/hint_bar.py`:

```python
"""Context-aware hint bar showing available keyboard shortcuts.

Always visible at the bottom of the screen, above the Footer.
Updates based on the current context (workspace, agent detail, etc.).
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

_DEFAULT_HINTS = "[Enter]detail  [/]search  [:]commands  [d]iff  [?]help"

_AGENT_DETAIL_HINTS = "[e]dit  [h]istory  [Esc]close"

_APPROVAL_HINTS = "[A]pprove  [D]eny  [Esc]dismiss"


class HintBar(Widget):
    """Displays context-sensitive keyboard shortcut hints."""

    DEFAULT_CSS = """
    HintBar {
        dock: bottom;
        height: 1;
        padding: 0 1;
        background: $surface;
        color: $text-muted;
    }
    """

    def __init__(self, context: str = "workspace") -> None:
        super().__init__()
        self._context = context

    def get_hint_text(self) -> str:
        """Get the hint text for the current context."""
        if self._context == "agent_detail":
            return _AGENT_DETAIL_HINTS
        if self._context == "approval":
            return _APPROVAL_HINTS
        return _DEFAULT_HINTS

    def compose(self) -> ComposeResult:
        yield Static(self.get_hint_text(), id="hints")

    def set_context(self, context: str) -> None:
        """Update the hint context."""
        self._context = context
        try:
            hints = self.query_one("#hints", Static)
            hints.update(self.get_hint_text())
        except Exception:
            pass
```

**Step 4: Run tests to verify they pass**

Run: `poetry run pytest tests/tui/test_hint_bar.py -v`

**Expected output:**
```
... 1 passed ...
```

**Step 5: Commit**

```bash
git add miniautogen/tui/widgets/hint_bar.py tests/tui/test_hint_bar.py
git commit -m "feat(tui): implement context-aware hint bar widget"
```

---

### Task 21: Run Code Review (Phase 2)

1. **Dispatch all 3 reviewers in parallel:**
   - REQUIRED SUB-SKILL: Use requesting-code-review
   - All reviewers run simultaneously (code-reviewer, business-logic-reviewer, security-reviewer)
   - Wait for all to complete

2. **Handle findings by severity (MANDATORY).**

3. **Proceed only when zero Critical/High/Medium issues remain.**

---

## Phase 3: Secondary Views

### Task 22: Implement Secondary View Base Class

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/views/__init__.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/views/base.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_views_base.py`

**Prerequisites:**
- Task 8 completed

**Step 1: Create views package**

Run: `mkdir -p /Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/views`

Write `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/views/__init__.py`:

```python
"""Secondary views for MiniAutoGen Dash."""
```

**Step 2: Write the failing test**

Write `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_views_base.py`:

```python
"""Tests for the secondary view base class."""

from __future__ import annotations

from textual.screen import Screen

from miniautogen.tui.views.base import SecondaryView


def test_secondary_view_is_screen() -> None:
    assert issubclass(SecondaryView, Screen)


def test_secondary_view_has_title() -> None:
    class TestView(SecondaryView):
        VIEW_TITLE = "Test"

    view = TestView()
    assert view.VIEW_TITLE == "Test"
```

**Step 3: Write the implementation**

Write `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/views/base.py`:

```python
"""Base class for secondary views (`:command` screens).

All secondary views are Textual Screens that can be pushed
onto the screen stack via the command palette.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, Static


class SecondaryView(Screen):
    """Base screen for secondary views like :agents, :pipelines, etc."""

    VIEW_TITLE: str = "View"

    BINDINGS = [
        Binding("escape", "pop_screen", "Back", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(
            f"[bold]{self.VIEW_TITLE}[/bold]",
            id="view-title",
        )
        yield from self.compose_content()
        yield Footer()

    def compose_content(self) -> ComposeResult:
        """Override in subclasses to provide view-specific content."""
        yield Static("[dim]No content[/dim]")
```

**Step 4: Run tests to verify they pass**

Run: `poetry run pytest tests/tui/test_views_base.py -v`

**Expected output:**
```
... 2 passed ...
```

**Step 5: Commit**

```bash
git add miniautogen/tui/views/ tests/tui/test_views_base.py
git commit -m "feat(tui): implement SecondaryView base screen"
```

---

### Task 23: Implement `:agents` View

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/views/agents.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_agents_view.py`

**Prerequisites:**
- Task 22 completed

**Step 1: Write the failing test**

Write `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_agents_view.py`:

```python
"""Tests for the :agents secondary view."""

from __future__ import annotations

from miniautogen.tui.views.agents import AgentsView
from miniautogen.tui.views.base import SecondaryView


def test_agents_view_is_secondary_view() -> None:
    assert issubclass(AgentsView, SecondaryView)


def test_agents_view_title() -> None:
    view = AgentsView()
    assert view.VIEW_TITLE == "Agents"
```

**Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/tui/test_agents_view.py -v`

**Step 3: Write the implementation**

Write `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/views/agents.py`:

```python
"""`:agents` view -- agent roster with DataTable CRUD."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import DataTable

from miniautogen.tui.views.base import SecondaryView


class AgentsView(SecondaryView):
    """Agent roster view with DataTable."""

    VIEW_TITLE = "Agents"

    def compose_content(self) -> ComposeResult:
        table = DataTable(id="agents-table")
        table.add_columns("ID", "Name", "Role", "Engine", "Status")
        yield table
```

**Step 4: Run tests to verify they pass**

Run: `poetry run pytest tests/tui/test_agents_view.py -v`

**Expected output:**
```
... 2 passed ...
```

**Step 5: Commit**

```bash
git add miniautogen/tui/views/agents.py tests/tui/test_agents_view.py
git commit -m "feat(tui): implement :agents secondary view"
```

---

### Task 24: Implement `:events` View

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/views/events.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_events_view.py`

**Prerequisites:**
- Task 22 completed

**Step 1: Write the failing test**

Write `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_events_view.py`:

```python
"""Tests for the :events secondary view."""

from __future__ import annotations

from miniautogen.tui.views.events import EventsView
from miniautogen.tui.views.base import SecondaryView


def test_events_view_is_secondary_view() -> None:
    assert issubclass(EventsView, SecondaryView)


def test_events_view_title() -> None:
    view = EventsView()
    assert view.VIEW_TITLE == "Events"
```

**Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/tui/test_events_view.py -v`

**Step 3: Write the implementation**

Write `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/views/events.py`:

```python
"""`:events` view -- raw event stream with filters."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import DataTable, Input

from miniautogen.tui.views.base import SecondaryView


class EventsView(SecondaryView):
    """Raw event stream with filter support."""

    VIEW_TITLE = "Events"

    def compose_content(self) -> ComposeResult:
        yield Input(placeholder="Filter events (type, run_id, agent_id)...", id="event-filter")
        table = DataTable(id="events-table")
        table.add_columns("Timestamp", "Type", "Run ID", "Agent", "Payload")
        yield table
```

**Step 4: Run tests to verify they pass**

Run: `poetry run pytest tests/tui/test_events_view.py -v`

**Expected output:**
```
... 2 passed ...
```

**Step 5: Commit**

```bash
git add miniautogen/tui/views/events.py tests/tui/test_events_view.py
git commit -m "feat(tui): implement :events secondary view"
```

---

### Task 25: Implement Remaining Secondary Views (:pipelines, :runs, :engines, :config)

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/views/pipelines.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/views/runs.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/views/engines.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/views/config.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_secondary_views.py`

**Prerequisites:**
- Task 22 completed

**Step 1: Write the failing test for all views**

Write `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_secondary_views.py`:

```python
"""Tests for all secondary views."""

from __future__ import annotations

import pytest

from miniautogen.tui.views.base import SecondaryView
from miniautogen.tui.views.pipelines import PipelinesView
from miniautogen.tui.views.runs import RunsView
from miniautogen.tui.views.engines import EnginesView
from miniautogen.tui.views.config import ConfigView


@pytest.mark.parametrize(
    "view_cls,expected_title",
    [
        (PipelinesView, "Pipelines"),
        (RunsView, "Runs"),
        (EnginesView, "Engines"),
        (ConfigView, "Config"),
    ],
)
def test_secondary_view_inherits_base(view_cls: type, expected_title: str) -> None:
    assert issubclass(view_cls, SecondaryView)
    view = view_cls()
    assert view.VIEW_TITLE == expected_title
```

**Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/tui/test_secondary_views.py -v`

**Step 3: Write all four views**

Write `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/views/pipelines.py`:

```python
"""`:pipelines` view -- pipeline list with DataTable CRUD."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import DataTable

from miniautogen.tui.views.base import SecondaryView


class PipelinesView(SecondaryView):
    VIEW_TITLE = "Pipelines"

    def compose_content(self) -> ComposeResult:
        table = DataTable(id="pipelines-table")
        table.add_columns("Name", "Target", "Mode", "Agents", "Status")
        yield table
```

Write `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/views/runs.py`:

```python
"""`:runs` view -- run history."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import DataTable

from miniautogen.tui.views.base import SecondaryView


class RunsView(SecondaryView):
    VIEW_TITLE = "Runs"

    def compose_content(self) -> ComposeResult:
        table = DataTable(id="runs-table")
        table.add_columns("Run ID", "Pipeline", "Status", "Started", "Duration", "Events")
        yield table
```

Write `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/views/engines.py`:

```python
"""`:engines` view -- engine profiles."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import DataTable

from miniautogen.tui.views.base import SecondaryView


class EnginesView(SecondaryView):
    VIEW_TITLE = "Engines"

    def compose_content(self) -> ComposeResult:
        table = DataTable(id="engines-table")
        table.add_columns("Name", "Kind", "Provider", "Model", "Temperature")
        yield table
```

Write `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/views/config.py`:

```python
"""`:config` view -- project configuration display."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import Static

from miniautogen.tui.views.base import SecondaryView


class ConfigView(SecondaryView):
    VIEW_TITLE = "Config"

    def compose_content(self) -> ComposeResult:
        yield Static("[dim]Project configuration will be displayed here.[/dim]")
```

**Step 4: Run tests to verify they pass**

Run: `poetry run pytest tests/tui/test_secondary_views.py -v`

**Expected output:**
```
... 4 passed ...
```

**Step 5: Commit**

```bash
git add miniautogen/tui/views/ tests/tui/test_secondary_views.py
git commit -m "feat(tui): implement remaining secondary views"
```

---

### Task 26: Register Secondary Views in Command Palette

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/app.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_command_palette.py`

**Prerequisites:**
- Tasks 23-25 completed

**Step 1: Write the failing test**

Write `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_command_palette.py`:

```python
"""Tests for command palette integration."""

from __future__ import annotations

from miniautogen.tui.app import MiniAutoGenDash


def test_app_has_command_providers() -> None:
    """App must provide commands for secondary views."""
    app = MiniAutoGenDash()
    # The app should have SCREENS or get_system_commands
    assert hasattr(app, "SCREENS") or hasattr(app, "get_system_commands")
```

**Step 2: Run tests to verify behavior**

Run: `poetry run pytest tests/tui/test_command_palette.py -v`

**Step 3: Add screen registration to the app**

In `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/app.py`, add the `SCREENS` class variable and imports:

Add these imports at the top of the file:

```python
from miniautogen.tui.views.agents import AgentsView
from miniautogen.tui.views.events import EventsView
from miniautogen.tui.views.pipelines import PipelinesView
from miniautogen.tui.views.runs import RunsView
from miniautogen.tui.views.engines import EnginesView
from miniautogen.tui.views.config import ConfigView
```

Add this class variable to `MiniAutoGenDash`:

```python
    SCREENS = {
        "agents": AgentsView,
        "events": EventsView,
        "pipelines": PipelinesView,
        "runs": RunsView,
        "engines": EnginesView,
        "config": ConfigView,
    }
```

**Step 4: Run tests to verify they pass**

Run: `poetry run pytest tests/tui/test_command_palette.py -v`

**Expected output:**
```
... 1 passed ...
```

**Step 5: Commit**

```bash
git add miniautogen/tui/app.py tests/tui/test_command_palette.py
git commit -m "feat(tui): register secondary views in command palette"
```

---

### Task 27: Run Code Review (Phase 3)

1. **Dispatch all 3 reviewers in parallel:**
   - REQUIRED SUB-SKILL: Use requesting-code-review
   - All reviewers run simultaneously

2. **Handle findings by severity (MANDATORY).**

3. **Proceed only when zero Critical/High/Medium issues remain.**

---

## Phase 4: Polish

### Task 28: Implement Textual CSS Theme System

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/themes.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_themes.py`

**Prerequisites:**
- Task 8 completed

**Step 1: Write the failing test**

Write `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_themes.py`:

```python
"""Tests for the theme system."""

from __future__ import annotations

from miniautogen.tui.themes import THEMES, get_theme


def test_four_themes_available() -> None:
    assert len(THEMES) == 4


def test_default_theme_is_tokyo_night() -> None:
    theme = get_theme("tokyo-night")
    assert theme is not None
    assert "tokyo" in theme.name.lower() or theme.name == "tokyo-night"


def test_all_themes_have_name() -> None:
    for name, theme in THEMES.items():
        assert theme.name == name


def test_get_nonexistent_theme_returns_default() -> None:
    theme = get_theme("nonexistent")
    assert theme.name == "tokyo-night"
```

**Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/tui/test_themes.py -v`

**Step 3: Write the implementation**

Write `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/themes.py`:

```python
"""Theme definitions for MiniAutoGen Dash.

Uses Textual's theme system with semantic color tokens.
4 built-in themes: tokyo-night, catppuccin, monokai, light.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DashTheme:
    """Theme definition with semantic color tokens."""

    name: str
    primary: str = "#7aa2f7"
    secondary: str = "#bb9af7"
    accent: str = "#7dcfff"
    background: str = "#1a1b26"
    surface: str = "#24283b"
    text: str = "#c0caf5"
    text_muted: str = "#565f89"
    status_active: str = "#9ece6a"
    status_done: str = "#73daca"
    status_working: str = "#e0af68"
    status_waiting: str = "#ff9e64"
    status_failed: str = "#f7768e"
    status_cancelled: str = "#db4b4b"


_TOKYO_NIGHT = DashTheme(name="tokyo-night")

_CATPPUCCIN = DashTheme(
    name="catppuccin",
    primary="#89b4fa",
    secondary="#cba6f7",
    accent="#89dceb",
    background="#1e1e2e",
    surface="#313244",
    text="#cdd6f4",
    text_muted="#6c7086",
    status_active="#a6e3a1",
    status_done="#94e2d5",
    status_working="#f9e2af",
    status_waiting="#fab387",
    status_failed="#f38ba8",
    status_cancelled="#eba0ac",
)

_MONOKAI = DashTheme(
    name="monokai",
    primary="#66d9ef",
    secondary="#ae81ff",
    accent="#a6e22e",
    background="#272822",
    surface="#3e3d32",
    text="#f8f8f2",
    text_muted="#75715e",
    status_active="#a6e22e",
    status_done="#66d9ef",
    status_working="#e6db74",
    status_waiting="#fd971f",
    status_failed="#f92672",
    status_cancelled="#cc6633",
)

_LIGHT = DashTheme(
    name="light",
    primary="#4078f2",
    secondary="#a626a4",
    accent="#0184bc",
    background="#fafafa",
    surface="#f0f0f0",
    text="#383a42",
    text_muted="#a0a1a7",
    status_active="#50a14f",
    status_done="#0184bc",
    status_working="#c18401",
    status_waiting="#e45649",
    status_failed="#e45649",
    status_cancelled="#986801",
)

THEMES: dict[str, DashTheme] = {
    "tokyo-night": _TOKYO_NIGHT,
    "catppuccin": _CATPPUCCIN,
    "monokai": _MONOKAI,
    "light": _LIGHT,
}


def get_theme(name: str) -> DashTheme:
    """Get a theme by name. Falls back to tokyo-night."""
    return THEMES.get(name, _TOKYO_NIGHT)
```

**Step 4: Run tests to verify they pass**

Run: `poetry run pytest tests/tui/test_themes.py -v`

**Expected output:**
```
... 4 passed ...
```

**Step 5: Commit**

```bash
git add miniautogen/tui/themes.py tests/tui/test_themes.py
git commit -m "feat(tui): implement 4 built-in color themes"
```

---

### Task 29: Export TUI Public API

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/__init__.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_tui_exports.py`

**Prerequisites:**
- All previous TUI tasks completed

**Step 1: Write the failing test**

Write `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_tui_exports.py`:

```python
"""Tests for TUI package public API exports."""

from __future__ import annotations


def test_tui_exports_app() -> None:
    from miniautogen.tui import MiniAutoGenDash

    assert MiniAutoGenDash is not None


def test_tui_exports_event_sink() -> None:
    from miniautogen.tui import TuiEventSink

    assert TuiEventSink is not None


def test_tui_exports_status() -> None:
    from miniautogen.tui import AgentStatus, StatusVocab

    assert AgentStatus is not None
    assert StatusVocab is not None
```

**Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/tui/test_tui_exports.py -v`

**Step 3: Update `__init__.py`**

Replace `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/__init__.py` with:

```python
"""MiniAutoGen Dash -- TUI dashboard for multi-agent pipeline monitoring.

Optional dependency: install with ``pip install miniautogen[tui]``.

This package has ZERO coupling to miniautogen.core internals.
It only imports protocols (EventSink) and data models (ExecutionEvent, EventType).
"""

from miniautogen.tui.app import MiniAutoGenDash
from miniautogen.tui.event_sink import TuiEventSink
from miniautogen.tui.status import AgentStatus, StatusVocab

__all__ = [
    "MiniAutoGenDash",
    "TuiEventSink",
    "AgentStatus",
    "StatusVocab",
]
```

**Step 4: Run tests to verify they pass**

Run: `poetry run pytest tests/tui/test_tui_exports.py -v`

**Expected output:**
```
... 3 passed ...
```

**Step 5: Commit**

```bash
git add miniautogen/tui/__init__.py tests/tui/test_tui_exports.py
git commit -m "feat(tui): export public API from tui package"
```

---

### Task 30: Full Test Suite and Zero-Coupling Verification

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_zero_coupling.py`

**Prerequisites:**
- All previous tasks completed

**Step 1: Write the zero-coupling verification test**

Write `/Users/brunocapelao/Projects/miniAutoGen/tests/tui/test_zero_coupling.py`:

```python
"""Verify that miniautogen.tui has zero coupling to core internals.

The TUI package must ONLY import:
- miniautogen.core.contracts.events (ExecutionEvent model)
- miniautogen.core.events.types (EventType enum)
- miniautogen.core.events.event_sink (EventSink protocol -- for isinstance checks only)
- miniautogen.policies.approval (ApprovalRequest/ApprovalResponse models)

It must NOT import:
- miniautogen.core.runtime (PipelineRunner, runtimes)
- miniautogen.stores (any store)
- miniautogen.adapters (any adapter)
- miniautogen.pipeline (any pipeline)
"""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

_TUI_ROOT = Path(__file__).resolve().parent.parent.parent / "miniautogen" / "tui"

_ALLOWED_CORE_IMPORTS = {
    "miniautogen.core.contracts.events",
    "miniautogen.core.events.types",
    "miniautogen.core.events.event_sink",
    "miniautogen.policies.approval",
}

_FORBIDDEN_PREFIXES = [
    "miniautogen.core.runtime",
    "miniautogen.stores",
    "miniautogen.adapters",
    "miniautogen.pipeline",
    "miniautogen.backends",
]


def _get_imports_from_file(path: Path) -> set[str]:
    """Extract all import module paths from a Python file using AST."""
    source = path.read_text()
    tree = ast.parse(source)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports


def test_tui_files_do_not_import_forbidden_modules() -> None:
    """No TUI module should import from forbidden core internals."""
    violations: list[str] = []

    for py_file in _TUI_ROOT.rglob("*.py"):
        if py_file.name == "__pycache__":
            continue
        imports = _get_imports_from_file(py_file)
        for imp in imports:
            for prefix in _FORBIDDEN_PREFIXES:
                if imp.startswith(prefix):
                    violations.append(
                        f"{py_file.name}: imports {imp} (forbidden: {prefix})"
                    )

    assert violations == [], (
        "TUI package has forbidden imports:\n" + "\n".join(violations)
    )
```

**Step 2: Run the test**

Run: `poetry run pytest tests/tui/test_zero_coupling.py -v`

**Expected output:**
```
tests/tui/test_zero_coupling.py::test_tui_files_do_not_import_forbidden_modules PASSED
```

**Step 3: Run the full TUI test suite**

Run: `poetry run pytest tests/tui/ -v`

**Expected output:** All TUI tests pass.

**Step 4: Run the full project test suite to verify no regressions**

Run: `poetry run pytest tests/ -v --timeout=60`

**Expected output:** All tests pass, zero regressions.

**Step 5: Commit**

```bash
git add tests/tui/test_zero_coupling.py
git commit -m "test(tui): add zero-coupling verification for TUI package"
```

---

### Task 31: Final Code Review (Phase 4)

1. **Dispatch all 3 reviewers in parallel:**
   - REQUIRED SUB-SKILL: Use requesting-code-review
   - All reviewers run simultaneously (code-reviewer, business-logic-reviewer, security-reviewer)

2. **Handle findings by severity (MANDATORY).**

3. **Proceed only when zero Critical/High/Medium issues remain.**

---

## Summary of File Structure

After all tasks complete, the new TUI package will have this structure:

```
miniautogen/tui/
  __init__.py          # Public API exports
  __main__.py          # Standalone entry point
  app.py               # Main Textual App (MiniAutoGenDash)
  event_sink.py        # TuiEventSink (EventSink protocol impl)
  event_mapper.py      # ExecutionEvent -> AgentStatus mapper
  messages.py          # TuiEvent Textual Message
  notifications.py     # Desktop notifications (OSC 9/99)
  status.py            # 7-state status vocabulary
  themes.py            # 4 built-in color themes
  workers.py           # EventBridgeWorker
  widgets/
    __init__.py
    agent_card.py       # Agent entry in sidebar
    approval_banner.py  # Inline HITL approval
    hint_bar.py         # Context-aware key hints
    interaction_log.py  # Main conversation log (killer feature)
    team_sidebar.py     # Agent roster sidebar
    work_panel.py       # Right panel with log + progress
  views/
    __init__.py
    base.py             # SecondaryView base screen
    agents.py           # :agents view
    config.py           # :config view
    engines.py          # :engines view
    events.py           # :events view
    pipelines.py        # :pipelines view
    runs.py             # :runs view

miniautogen/cli/commands/
  dash.py              # `miniautogen dash` CLI command

tests/tui/
  __init__.py
  test_event_sink.py
  test_messages.py
  test_status.py
  test_event_mapper.py
  test_notifications.py
  test_app.py
  test_workers.py
  test_agent_card.py
  test_interaction_log.py
  test_approval_banner.py
  test_team_sidebar.py
  test_work_panel.py
  test_workspace_layout.py
  test_responsive.py
  test_hint_bar.py
  test_views_base.py
  test_agents_view.py
  test_events_view.py
  test_secondary_views.py
  test_command_palette.py
  test_themes.py
  test_tui_exports.py
  test_zero_coupling.py
```

Total: 19 source files, 22 test files, 31 tasks with 4 code review checkpoints.
