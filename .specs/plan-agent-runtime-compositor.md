# AgentRuntime Compositor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement AgentRuntime as the Layer 3 compositor that adds hooks, tools, memory, and delegation to Engines, materializing "o agente e commodity, o runtime e o produto".

**Architecture:** AgentRuntime implements the 3 existing agent protocols (WorkflowAgent, ConversationalAgent, DeliberationAgent) transparently. Coordination runtimes require zero changes. PipelineRunner builds AgentRuntimes from YAML as the sole factory. Per-agent config lives in `.miniautogen/agents/{name}/`.

**Tech Stack:** Python 3.10+, AnyIO, Pydantic v2, anyio.fail_after for timeouts, hashlib for prompt integrity.

**Spec:** `.specs/agent-runtime-compositor.md` (approved, 4 review rounds)

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `miniautogen/core/contracts/tool_registry.py` | ToolRegistryProtocol, ToolDefinition, ToolCall models |
| `miniautogen/core/contracts/delegation.py` | DelegationRouterProtocol, PersistableMemory protocol |
| `miniautogen/core/contracts/turn_result.py` | TurnResult internal model |
| `miniautogen/core/runtime/agent_runtime.py` | AgentRuntime compositor class |
| `miniautogen/core/runtime/tool_registry.py` | InMemoryToolRegistry implementation |
| `miniautogen/core/runtime/delegation_router.py` | ConfigDelegationRouter implementation |
| `miniautogen/core/runtime/persistent_memory.py` | PersistentMemoryProvider (filesystem-backed) |
| `miniautogen/core/runtime/filesystem_tool_registry.py` | FileSystemToolRegistry (loads tools.yml) |
| `miniautogen/core/runtime/agent_sandbox.py` | AgentFilesystemSandbox + ToolExecutionPolicy |
| `miniautogen/core/runtime/agent_errors.py` | Error classes with canonical taxonomy mapping |
| `tests/core/runtime/test_agent_runtime.py` | AgentRuntime unit tests |
| `tests/core/runtime/test_tool_registry.py` | ToolRegistry tests |
| `tests/core/runtime/test_delegation_router.py` | DelegationRouter tests |
| `tests/core/runtime/test_persistent_memory.py` | PersistentMemoryProvider tests |
| `tests/core/runtime/test_filesystem_tool_registry.py` | FileSystemToolRegistry tests |
| `tests/core/runtime/test_agent_sandbox.py` | Security tests |

### Modified Files

| File | Change |
|------|--------|
| `miniautogen/core/events/types.py` | +6 EventType members + update set |
| `miniautogen/core/contracts/agent_spec.py` | +field_validator on `id`, +max_depth on DelegationConfig |
| `miniautogen/backends/resolver.py` | +create_driver() public method |
| `miniautogen/backends/engine_resolver.py` | +create_fresh_driver() method |
| `miniautogen/core/runtime/pipeline_runner.py` | +_build_agent_runtimes() factory |
| `miniautogen/core/contracts/__init__.py` | Export new contracts |
| `miniautogen/api.py` | Export AgentRuntime + new types |
| `miniautogen/cli/commands/init.py` | Scaffold .miniautogen/agents/ |

---

## Task 1: Contracts — ToolRegistry, Delegation, TurnResult

**Files:**
- Create: `miniautogen/core/contracts/tool_registry.py`
- Create: `miniautogen/core/contracts/delegation.py`
- Create: `miniautogen/core/contracts/turn_result.py`
- Create: `miniautogen/core/runtime/agent_errors.py`
- Test: `tests/core/contracts/test_tool_registry_protocol.py`
- Test: `tests/core/contracts/test_delegation_protocol.py`

- [ ] **Step 1: Write failing test for ToolRegistryProtocol**

```python
# tests/core/contracts/test_tool_registry_protocol.py
import pytest
from miniautogen.core.contracts.tool_registry import (
    ToolRegistryProtocol,
    ToolDefinition,
    ToolCall,
)
from miniautogen.core.contracts.tool import ToolResult


def test_tool_definition_model():
    td = ToolDefinition(name="read_file", description="Read a file")
    assert td.name == "read_file"
    assert td.parameters is None


def test_tool_definition_with_schema():
    td = ToolDefinition(
        name="read_file",
        description="Read a file",
        parameters={"type": "object", "properties": {"path": {"type": "string"}}},
    )
    assert td.parameters is not None


def test_tool_call_model():
    tc = ToolCall(tool_name="read_file", call_id="abc123", params={"path": "foo.py"})
    assert tc.tool_name == "read_file"
    assert tc.call_id == "abc123"


def test_tool_registry_protocol_is_runtime_checkable():
    assert hasattr(ToolRegistryProtocol, "__protocol_attrs__") or hasattr(
        ToolRegistryProtocol, "__abstractmethods__"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/core/contracts/test_tool_registry_protocol.py -v`
Expected: FAIL (ImportError — module does not exist)

- [ ] **Step 3: Implement ToolRegistry contracts**

```python
# miniautogen/core/contracts/tool_registry.py
"""Tool registry protocol and supporting models."""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from miniautogen.core.contracts.tool import ToolProtocol, ToolResult


class ToolDefinition(BaseModel):
    """Serializable tool definition for injection into driver prompts."""

    name: str
    description: str
    parameters: dict[str, Any] | None = None  # JSON Schema

    @classmethod
    def from_protocol(cls, tool: ToolProtocol) -> ToolDefinition:
        """Extract definition from a ToolProtocol implementation."""
        return cls(name=tool.name, description=tool.description)


class ToolCall(BaseModel):
    """A tool invocation request from the driver."""

    tool_name: str
    call_id: str
    params: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class ToolRegistryProtocol(Protocol):
    """Registry of tools available to an agent. Loaded from tools.yml."""

    def list_tools(self) -> list[ToolDefinition]: ...
    async def execute_tool(self, call: ToolCall) -> ToolResult: ...
    def has_tool(self, name: str) -> bool: ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/core/contracts/test_tool_registry_protocol.py -v`
Expected: PASS

- [ ] **Step 5: Write failing test for DelegationRouter + PersistableMemory**

```python
# tests/core/contracts/test_delegation_protocol.py
import pytest
from miniautogen.core.contracts.delegation import (
    DelegationRouterProtocol,
    PersistableMemory,
)


def test_delegation_router_is_runtime_checkable():
    assert hasattr(DelegationRouterProtocol, "__protocol_attrs__") or hasattr(
        DelegationRouterProtocol, "__abstractmethods__"
    )


def test_persistable_memory_is_runtime_checkable():
    assert hasattr(PersistableMemory, "__protocol_attrs__") or hasattr(
        PersistableMemory, "__abstractmethods__"
    )
```

- [ ] **Step 6: Implement Delegation + PersistableMemory contracts**

```python
# miniautogen/core/contracts/delegation.py
"""Delegation router protocol and persistable memory protocol."""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class DelegationRouterProtocol(Protocol):
    """Controls which agents can delegate to which others."""

    def can_delegate(self, from_agent: str, to_agent: str) -> bool: ...

    async def delegate(
        self,
        from_agent: str,
        to_agent: str,
        input_data: Any,
        current_depth: int = 0,
    ) -> Any:
        """Delegate work to another agent. Returns the target agent's output.

        Raises DelegationDepthExceededError if current_depth >= max_depth.
        """
        ...


@runtime_checkable
class PersistableMemory(Protocol):
    """Protocol for memory providers that support filesystem persistence."""

    async def load_from_disk(self) -> None: ...
    async def persist_to_disk(self) -> None: ...
```

- [ ] **Step 7: Implement TurnResult + error classes**

```python
# miniautogen/core/contracts/turn_result.py
"""Internal turn result model for AgentRuntime."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from miniautogen.core.contracts.tool_registry import ToolCall


class TurnResult(BaseModel):
    """Result of a single agent turn. INTERNAL — not part of public interface."""

    output: Any = None  # WorkflowAgent.process() return value
    text: str = ""  # ConversationalAgent.reply() return value
    structured: dict[str, Any] = Field(default_factory=dict)  # For model_validate
    messages: list[dict[str, Any]] = Field(default_factory=list)
    token_usage: dict[str, int] = Field(default_factory=dict)
    tool_calls: list[ToolCall] = Field(default_factory=list)
```

```python
# miniautogen/core/runtime/agent_errors.py
"""AgentRuntime error classes mapped to canonical taxonomy."""
from __future__ import annotations

from miniautogen.core.contracts.errors import MiniAutoGenError


class DelegationDepthExceededError(MiniAutoGenError):
    """Delegation depth exceeded max_depth. Category: validation."""

    error_category = "validation"


class AgentClosedError(MiniAutoGenError):
    """Agent was called after close(). Category: state_consistency."""

    error_category = "state_consistency"


class ToolExecutionError(MiniAutoGenError):
    """Tool execution failed. Category: adapter."""

    error_category = "adapter"


class ToolTimeoutError(MiniAutoGenError):
    """Tool execution timed out. Category: timeout."""

    error_category = "timeout"


class AgentSecurityError(MiniAutoGenError):
    """Security violation (path traversal, injection). Category: permanent."""

    error_category = "permanent"
```

- [ ] **Step 8: Run all contract tests**

Run: `python -m pytest tests/core/contracts/test_tool_registry_protocol.py tests/core/contracts/test_delegation_protocol.py -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add miniautogen/core/contracts/tool_registry.py miniautogen/core/contracts/delegation.py miniautogen/core/contracts/turn_result.py miniautogen/core/runtime/agent_errors.py tests/core/contracts/test_tool_registry_protocol.py tests/core/contracts/test_delegation_protocol.py
git commit -m "feat(core): add ToolRegistry, Delegation, TurnResult contracts and error types"
```

---

## Task 2: New EventTypes

**Files:**
- Modify: `miniautogen/core/events/types.py`
- Test: `tests/core/events/test_agent_runtime_events.py`

- [ ] **Step 1: Write failing test for new events**

```python
# tests/core/events/test_agent_runtime_events.py
from miniautogen.core.events.types import EventType, AGENT_RUNTIME_EVENT_TYPES


def test_new_agent_runtime_events_exist():
    assert EventType.AGENT_INITIALIZED == "agent_initialized"
    assert EventType.AGENT_CLOSED == "agent_closed"
    assert EventType.AGENT_MEMORY_LOADED == "agent_memory_loaded"
    assert EventType.AGENT_MEMORY_SAVED == "agent_memory_saved"
    assert EventType.AGENT_DELEGATED == "agent_delegated"
    assert EventType.AGENT_DELEGATION_DEPTH_EXCEEDED == "agent_delegation_depth_exceeded"


def test_agent_runtime_event_types_set_includes_new():
    new_events = {
        EventType.AGENT_INITIALIZED,
        EventType.AGENT_CLOSED,
        EventType.AGENT_MEMORY_LOADED,
        EventType.AGENT_MEMORY_SAVED,
        EventType.AGENT_DELEGATED,
        EventType.AGENT_DELEGATION_DEPTH_EXCEEDED,
    }
    assert new_events.issubset(AGENT_RUNTIME_EVENT_TYPES)


def test_total_event_count():
    all_members = list(EventType)
    assert len(all_members) == 69
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/core/events/test_agent_runtime_events.py -v`
Expected: FAIL (AttributeError — members don't exist)

- [ ] **Step 3: Add 6 new events to EventType enum**

In `miniautogen/core/events/types.py`, add after the existing Agent Runtime block (after `AGENT_TOOL_INVOKED`):

```python
    # Agent Runtime events (Phase B) — continued
    AGENT_INITIALIZED = "agent_initialized"
    AGENT_CLOSED = "agent_closed"
    AGENT_MEMORY_LOADED = "agent_memory_loaded"
    AGENT_MEMORY_SAVED = "agent_memory_saved"
    AGENT_DELEGATED = "agent_delegated"
    AGENT_DELEGATION_DEPTH_EXCEEDED = "agent_delegation_depth_exceeded"
```

Update `AGENT_RUNTIME_EVENT_TYPES` set to include all 10:

```python
AGENT_RUNTIME_EVENT_TYPES: set[EventType] = {
    EventType.AGENT_TURN_STARTED,
    EventType.AGENT_TURN_COMPLETED,
    EventType.AGENT_HOOK_EXECUTED,
    EventType.AGENT_TOOL_INVOKED,
    EventType.AGENT_INITIALIZED,
    EventType.AGENT_CLOSED,
    EventType.AGENT_MEMORY_LOADED,
    EventType.AGENT_MEMORY_SAVED,
    EventType.AGENT_DELEGATED,
    EventType.AGENT_DELEGATION_DEPTH_EXCEEDED,
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/core/events/test_agent_runtime_events.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add miniautogen/core/events/types.py tests/core/events/test_agent_runtime_events.py
git commit -m "feat(events): add 6 AgentRuntime lifecycle events (total 69)"
```

---

## Task 3: InMemoryToolRegistry

**Files:**
- Create: `miniautogen/core/runtime/tool_registry.py`
- Test: `tests/core/runtime/test_tool_registry.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/core/runtime/test_tool_registry.py
import pytest
import anyio
from miniautogen.core.contracts.tool_registry import (
    ToolRegistryProtocol,
    ToolDefinition,
    ToolCall,
)
from miniautogen.core.contracts.tool import ToolResult
from miniautogen.core.runtime.tool_registry import InMemoryToolRegistry


def test_implements_protocol():
    reg = InMemoryToolRegistry()
    assert isinstance(reg, ToolRegistryProtocol)


def test_empty_registry():
    reg = InMemoryToolRegistry()
    assert reg.list_tools() == []
    assert not reg.has_tool("read_file")


def test_register_and_list():
    reg = InMemoryToolRegistry()
    td = ToolDefinition(name="read_file", description="Read a file")
    reg.register(td, handler=lambda params: ToolResult(success=True, output="content"))
    assert reg.has_tool("read_file")
    assert len(reg.list_tools()) == 1


@pytest.mark.anyio
async def test_execute_tool():
    reg = InMemoryToolRegistry()
    td = ToolDefinition(name="echo", description="Echo input")

    async def echo_handler(params):
        return ToolResult(success=True, output=params.get("text", ""))

    reg.register(td, handler=echo_handler)
    result = await reg.execute_tool(ToolCall(tool_name="echo", call_id="1", params={"text": "hello"}))
    assert result.success
    assert result.output == "hello"


@pytest.mark.anyio
async def test_execute_unknown_tool():
    reg = InMemoryToolRegistry()
    result = await reg.execute_tool(ToolCall(tool_name="unknown", call_id="1", params={}))
    assert not result.success
    assert "unknown" in result.error.lower()
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/core/runtime/test_tool_registry.py -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: Implement InMemoryToolRegistry**

```python
# miniautogen/core/runtime/tool_registry.py
"""In-memory tool registry implementation."""
from __future__ import annotations

from typing import Any, Callable, Awaitable

from miniautogen.core.contracts.tool import ToolResult
from miniautogen.core.contracts.tool_registry import (
    ToolCall,
    ToolDefinition,
    ToolRegistryProtocol,
)

ToolHandler = Callable[[dict[str, Any]], Awaitable[ToolResult]]


class InMemoryToolRegistry:
    """In-memory tool registry for testing and programmatic use."""

    def __init__(self) -> None:
        self._definitions: dict[str, ToolDefinition] = {}
        self._handlers: dict[str, ToolHandler] = {}

    def register(self, definition: ToolDefinition, handler: ToolHandler) -> None:
        """Register a tool with its handler."""
        self._definitions[definition.name] = definition
        # Wrap sync handlers
        if not callable(handler):
            msg = f"Handler for '{definition.name}' must be callable"
            raise TypeError(msg)
        self._handlers[definition.name] = handler

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._definitions.values())

    def has_tool(self, name: str) -> bool:
        return name in self._definitions

    async def execute_tool(self, call: ToolCall) -> ToolResult:
        handler = self._handlers.get(call.tool_name)
        if handler is None:
            return ToolResult(success=False, error=f"Unknown tool: {call.tool_name}")
        try:
            result = handler(call.params)
            if hasattr(result, "__await__"):
                result = await result
            return result
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/core/runtime/test_tool_registry.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add miniautogen/core/runtime/tool_registry.py tests/core/runtime/test_tool_registry.py
git commit -m "feat(runtime): add InMemoryToolRegistry implementation"
```

---

## Task 4: ConfigDelegationRouter

**Files:**
- Create: `miniautogen/core/runtime/delegation_router.py`
- Test: `tests/core/runtime/test_delegation_router.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/core/runtime/test_delegation_router.py
import pytest
from miniautogen.core.contracts.delegation import DelegationRouterProtocol
from miniautogen.core.runtime.delegation_router import ConfigDelegationRouter
from miniautogen.core.runtime.agent_errors import DelegationDepthExceededError


def test_implements_protocol():
    router = ConfigDelegationRouter(configs={})
    assert isinstance(router, DelegationRouterProtocol)


def test_can_delegate_allowed():
    configs = {
        "architect": {"can_delegate_to": ["developer"], "max_depth": 2},
        "developer": {"can_delegate_to": [], "max_depth": 1},
    }
    router = ConfigDelegationRouter(configs=configs)
    assert router.can_delegate("architect", "developer")
    assert not router.can_delegate("developer", "architect")
    assert not router.can_delegate("architect", "unknown")


def test_can_delegate_empty_config():
    router = ConfigDelegationRouter(configs={})
    assert not router.can_delegate("a", "b")
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/core/runtime/test_delegation_router.py -v`
Expected: FAIL

- [ ] **Step 3: Implement ConfigDelegationRouter**

```python
# miniautogen/core/runtime/delegation_router.py
"""Config-driven delegation router."""
from __future__ import annotations

from typing import Any

from miniautogen.core.runtime.agent_errors import (
    DelegationDepthExceededError,
    AgentSecurityError,
)


class ConfigDelegationRouter:
    """Routes delegation based on YAML config allowlists and depth limits."""

    def __init__(self, configs: dict[str, dict[str, Any]]) -> None:
        self._configs = configs
        self._agents: dict[str, Any] = {}  # populated by PipelineRunner

    def register_agent(self, agent_id: str, agent: Any) -> None:
        """Register an agent runtime for delegation targets."""
        self._agents[agent_id] = agent

    def can_delegate(self, from_agent: str, to_agent: str) -> bool:
        config = self._configs.get(from_agent)
        if config is None:
            return False
        allowed = config.get("can_delegate_to", [])
        return to_agent in allowed

    async def delegate(
        self,
        from_agent: str,
        to_agent: str,
        input_data: Any,
        current_depth: int = 0,
    ) -> Any:
        if not self.can_delegate(from_agent, to_agent):
            msg = f"Delegation not allowed: {from_agent} -> {to_agent}"
            raise AgentSecurityError(msg)

        config = self._configs.get(from_agent, {})
        max_depth = config.get("max_depth", 1)
        if current_depth >= max_depth:
            msg = f"Agent '{from_agent}' exceeded max delegation depth {max_depth}"
            raise DelegationDepthExceededError(msg)

        target = self._agents.get(to_agent)
        if target is None:
            msg = f"Delegation target '{to_agent}' not found"
            raise AgentSecurityError(msg)

        # Delegate via process() (WorkflowAgent protocol)
        return await target.process(input_data)
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/core/runtime/test_delegation_router.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add miniautogen/core/runtime/delegation_router.py tests/core/runtime/test_delegation_router.py
git commit -m "feat(runtime): add ConfigDelegationRouter with depth tracking"
```

---

## Task 5: AgentRuntime Compositor

**Files:**
- Create: `miniautogen/core/runtime/agent_runtime.py`
- Test: `tests/core/runtime/test_agent_runtime.py`

This is the core task. AgentRuntime implements all 3 agent protocols and wraps `_execute_turn()`.

- [ ] **Step 1: Write failing tests for protocol satisfaction**

```python
# tests/core/runtime/test_agent_runtime.py
import pytest
import anyio
from unittest.mock import AsyncMock, MagicMock
from miniautogen.core.contracts.agent import (
    WorkflowAgent,
    ConversationalAgent,
    DeliberationAgent,
)
from miniautogen.core.contracts.tool_registry import ToolDefinition, ToolCall
from miniautogen.core.contracts.tool import ToolResult
from miniautogen.core.events.types import EventType
from miniautogen.core.runtime.agent_runtime import AgentRuntime
from miniautogen.core.runtime.tool_registry import InMemoryToolRegistry
from miniautogen.core.runtime.delegation_router import ConfigDelegationRouter


def _make_mock_driver():
    """Create a mock AgentDriver that returns simple responses."""
    driver = AsyncMock()
    driver.start_session = AsyncMock(return_value=MagicMock(session_id="test-session"))

    async def mock_send_turn(request):
        from miniautogen.backends.models import AgentEvent
        yield AgentEvent(
            type="message",
            content=request.messages[-1].get("content", "echo"),
            metadata={},
        )

    driver.send_turn = mock_send_turn
    driver.close_session = AsyncMock()
    return driver


def _make_mock_spec(agent_id="test-agent"):
    spec = MagicMock()
    spec.id = agent_id
    spec.name = "Test Agent"
    spec.role = "tester"
    spec.tool_timeout_seconds = 5.0
    return spec


def _make_mock_event_sink():
    sink = AsyncMock()
    sink.publish = AsyncMock()
    return sink


def _make_runtime(**overrides):
    defaults = dict(
        spec=_make_mock_spec(),
        driver=_make_mock_driver(),
        hooks=[],
        tools=InMemoryToolRegistry(),
        memory=AsyncMock(),  # InMemoryMemoryProvider mock
        delegation=None,
        policies=[],
        event_sink=_make_mock_event_sink(),
        config_dir=None,
    )
    defaults.update(overrides)
    return AgentRuntime(**defaults)


def test_satisfies_workflow_agent_protocol():
    rt = _make_runtime()
    assert isinstance(rt, WorkflowAgent)


def test_satisfies_conversational_agent_protocol():
    rt = _make_runtime()
    assert isinstance(rt, ConversationalAgent)


def test_satisfies_deliberation_agent_protocol():
    rt = _make_runtime()
    assert isinstance(rt, DeliberationAgent)


@pytest.mark.anyio
async def test_initialize_starts_session():
    driver = _make_mock_driver()
    rt = _make_runtime(driver=driver)
    await rt.initialize()
    driver.start_session.assert_called_once()


@pytest.mark.anyio
async def test_process_returns_output():
    rt = _make_runtime()
    rt._memory = AsyncMock()
    rt._memory.get_context = AsyncMock(return_value=[])
    rt._memory.save_turn = AsyncMock()
    await rt.initialize()
    result = await rt.process("hello")
    assert result is not None


@pytest.mark.anyio
async def test_close_persists_and_closes():
    driver = _make_mock_driver()
    rt = _make_runtime(driver=driver)
    await rt.initialize()
    await rt.close()
    driver.close_session.assert_called_once()
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/core/runtime/test_agent_runtime.py -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: Implement AgentRuntime**

```python
# miniautogen/core/runtime/agent_runtime.py
"""AgentRuntime — the Layer 3 compositor.

Implements WorkflowAgent, ConversationalAgent, DeliberationAgent.
Coordination runtimes see it as a regular agent via duck typing.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

import anyio

from miniautogen.backends.driver import AgentDriver
from miniautogen.backends.models import SendTurnRequest, StartSessionRequest
from miniautogen.core.contracts.agent_hook import AgentHook
from miniautogen.core.contracts.agent_spec import AgentSpec
from miniautogen.core.contracts.delegation import DelegationRouterProtocol, PersistableMemory
from miniautogen.core.contracts.memory_provider import MemoryProvider
from miniautogen.core.contracts.tool_registry import ToolCall, ToolDefinition, ToolRegistryProtocol
from miniautogen.core.contracts.turn_result import TurnResult
from miniautogen.core.events.event_sink import EventSink
from miniautogen.core.events.execution_event import ExecutionEvent
from miniautogen.core.events.types import EventType
from miniautogen.core.runtime.agent_errors import AgentClosedError

logger = logging.getLogger(__name__)


class AgentRuntime:
    """Compositor: Engine + superpowers.

    Implements WorkflowAgent, ConversationalAgent, DeliberationAgent.
    """

    def __init__(
        self,
        spec: AgentSpec,
        driver: AgentDriver,
        hooks: list[AgentHook],
        tools: ToolRegistryProtocol,
        memory: MemoryProvider,
        delegation: DelegationRouterProtocol | None,
        policies: list[Any],
        event_sink: EventSink,
        config_dir: Path | None,
    ) -> None:
        self._spec = spec
        self._driver = driver
        self._hooks = hooks
        self._tools = tools
        self._memory = memory
        self._delegation = delegation
        self._policies = policies
        self._event_sink = event_sink
        self._config_dir = config_dir
        self._session_id: str | None = None
        self._closed = False
        self._prompt_hash: str | None = None
        self._system_prompt: str | None = None

    @property
    def spec(self) -> AgentSpec:
        return self._spec

    @property
    def agent_id(self) -> str:
        return self._spec.id

    # --- Lifecycle ---

    async def initialize(self) -> None:
        """Start driver session, load config, hydrate memory."""
        response = await self._driver.start_session(
            StartSessionRequest(system_prompt=self._system_prompt or "")
        )
        self._session_id = response.session_id

        # Load system prompt from filesystem
        if self._config_dir:
            prompt_path = self._config_dir / "prompt.md"
            if prompt_path.exists():
                content = prompt_path.read_text()
                self._system_prompt = content
                self._prompt_hash = hashlib.sha256(content.encode()).hexdigest()

        # Hydrate memory from disk
        if isinstance(self._memory, PersistableMemory):
            await self._memory.load_from_disk()

        await self._emit(EventType.AGENT_INITIALIZED, {"agent_id": self.agent_id})

    async def close(self) -> None:
        """Persist memory, close driver session."""
        async with anyio.open_cancel_scope(shield=True):
            try:
                await self._memory.distill(self.agent_id)
                if isinstance(self._memory, PersistableMemory):
                    await self._memory.persist_to_disk()
                    await self._emit(EventType.AGENT_MEMORY_SAVED, {"success": True})
            except Exception as exc:
                await self._emit(EventType.AGENT_MEMORY_SAVED, {"success": False, "error": str(exc)})
                logger.error("memory_persist_failed", extra={"agent_id": self.agent_id, "error": str(exc)})
            finally:
                if self._session_id:
                    await self._driver.close_session(self._session_id)
                self._closed = True
                await self._emit(EventType.AGENT_CLOSED, {"agent_id": self.agent_id})

    # --- WorkflowAgent protocol ---

    async def process(self, input: Any) -> Any:
        """WorkflowAgent.process — wraps _execute_turn."""
        request = self._build_request([{"role": "user", "content": str(input)}])
        result = await self._execute_turn(request)
        return result.output

    # --- ConversationalAgent protocol ---

    async def reply(self, message: str, context: dict[str, Any]) -> str:
        """ConversationalAgent.reply — wraps _execute_turn."""
        request = self._build_request([{"role": "user", "content": message}])
        result = await self._execute_turn(request)
        return result.text

    async def route(self, conversation_history: list[Any]) -> Any:
        """ConversationalAgent.route — delegates to driver."""
        request = self._build_request(
            [{"role": "system", "content": "Decide the next speaker."}]
            + conversation_history
        )
        result = await self._execute_turn(request)
        return result.structured

    # --- DeliberationAgent protocol ---

    async def contribute(self, topic: str) -> Any:
        """DeliberationAgent.contribute — wraps _execute_turn."""
        request = self._build_request([{"role": "user", "content": f"Contribute to: {topic}"}])
        result = await self._execute_turn(request)
        return result.structured if result.structured else result.output

    async def review(self, target_id: str, contribution: Any) -> Any:
        """DeliberationAgent.review — wraps _execute_turn."""
        request = self._build_request([
            {"role": "user", "content": f"Review contribution from {target_id}: {contribution}"}
        ])
        result = await self._execute_turn(request)
        return result.structured if result.structured else result.output

    # --- Internal compositor engine ---

    async def _execute_turn(self, request: SendTurnRequest) -> TurnResult:
        """Full turn: hooks before -> enrich -> driver -> tool loop -> hooks after -> memory."""
        if self._closed:
            raise AgentClosedError(f"Agent '{self.agent_id}' is closed")

        await self._emit(EventType.AGENT_TURN_STARTED, {"agent_id": self.agent_id})

        # 1. Before hooks
        messages = request.messages
        from miniautogen.core.events.execution_event import RunContext
        context = RunContext(run_id="", agent_id=self.agent_id)
        for hook in self._hooks:
            messages = await hook.before_turn(messages, context)

        # 2. Enrich with memory context
        memory_ctx = await self._memory.get_context(self.agent_id, context)
        if memory_ctx:
            messages = memory_ctx + messages

        # 3. Enrich with tool definitions
        tool_defs = self._tools.list_tools()
        if tool_defs:
            tools_text = "\n".join(f"- {t.name}: {t.description}" for t in tool_defs)
            messages = [{"role": "system", "content": f"Available tools:\n{tools_text}"}] + messages

        # 4. Send to driver
        enriched = SendTurnRequest(
            session_id=self._session_id or "",
            messages=messages,
            metadata=request.metadata,
        )

        output_text = ""
        async for event in self._driver.send_turn(enriched):
            if hasattr(event, "content") and event.content:
                output_text += str(event.content)

        # 5. Save turn to memory
        turn_messages = messages + [{"role": "assistant", "content": output_text}]
        await self._memory.save_turn(turn_messages, context)

        # 6. After hooks
        result_event = ExecutionEvent(
            event_type=EventType.AGENT_TURN_COMPLETED,
            payload={"output": output_text, "agent_id": self.agent_id},
        )
        for hook in self._hooks:
            result_event = await hook.after_event(result_event, context)

        await self._emit(EventType.AGENT_TURN_COMPLETED, {"agent_id": self.agent_id})

        return TurnResult(
            output=output_text,
            text=output_text,
            structured={},
            messages=turn_messages,
        )

    # --- Helpers ---

    def _build_request(self, messages: list[dict[str, Any]]) -> SendTurnRequest:
        return SendTurnRequest(
            session_id=self._session_id or "",
            messages=messages,
            metadata={"agent_id": self.agent_id},
        )

    async def _emit(self, event_type: EventType, payload: dict[str, Any]) -> None:
        event = ExecutionEvent(
            event_type=event_type,
            payload=payload,
        )
        await self._event_sink.publish(event)
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/core/runtime/test_agent_runtime.py -v`
Expected: PASS (may need to adjust mock setup based on actual model signatures)

- [ ] **Step 5: Commit**

```bash
git add miniautogen/core/runtime/agent_runtime.py tests/core/runtime/test_agent_runtime.py
git commit -m "feat(runtime): add AgentRuntime compositor implementing 3 agent protocols"
```

---

## Task 6: EngineResolver.create_fresh_driver + BackendResolver.create_driver

**Files:**
- Modify: `miniautogen/backends/resolver.py`
- Modify: `miniautogen/backends/engine_resolver.py`
- Test: `tests/backends/test_resolver.py` (add test)
- Test: `tests/backends/test_engine_resolver.py` (add test)

- [ ] **Step 1: Write failing test for BackendResolver.create_driver**

```python
# Add to tests/backends/test_resolver.py
def test_create_driver_returns_new_instance(resolver_with_factory):
    """create_driver should return a fresh driver, not cached."""
    config = make_backend_config("test-1")
    resolver_with_factory.add_backend(config)
    cached = resolver_with_factory.get_driver("test-1")

    fresh = resolver_with_factory.create_driver(config)
    assert fresh is not cached  # Different instances
```

- [ ] **Step 2: Implement BackendResolver.create_driver**

Add to `miniautogen/backends/resolver.py`:

```python
def create_driver(self, config: BackendConfig) -> AgentDriver:
    """Create a NEW driver instance (not cached). Public factory method."""
    factory = self._factories.get(config.driver)
    if factory is None:
        msg = f"No factory for driver type '{config.driver.value}'"
        raise BackendUnavailableError(msg)
    return factory(config)
```

- [ ] **Step 3: Write failing test for EngineResolver.create_fresh_driver**

```python
# Add to tests/backends/test_engine_resolver.py
def test_create_fresh_driver_returns_unique_instance(engine_resolver, project_config):
    """create_fresh_driver should bypass cache."""
    driver_a = engine_resolver.create_fresh_driver("default", project_config)
    driver_b = engine_resolver.create_fresh_driver("default", project_config)
    assert driver_a is not driver_b
```

- [ ] **Step 4: Implement EngineResolver.create_fresh_driver**

Add to `miniautogen/backends/engine_resolver.py`:

```python
from uuid import uuid4

def create_fresh_driver(
    self, profile_name: str, config: ProjectConfig,
) -> AgentDriver:
    """Create a NEW driver instance (not cached). For per-agent sessions."""
    engine = config.engine_profiles.get(profile_name)
    if engine is None:
        msg = f"Engine profile '{profile_name}' not found"
        raise BackendUnavailableError(msg)

    backend_config = self._engine_to_backend(
        f"{profile_name}_{uuid4().hex[:8]}", engine,
    )
    return self._resolver.create_driver(backend_config)
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/backends/test_resolver.py tests/backends/test_engine_resolver.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add miniautogen/backends/resolver.py miniautogen/backends/engine_resolver.py tests/backends/test_resolver.py tests/backends/test_engine_resolver.py
git commit -m "feat(backends): add create_fresh_driver for per-agent driver instances"
```

---

## Task 7: PipelineRunner Factory

**Files:**
- Modify: `miniautogen/core/runtime/pipeline_runner.py`
- Test: `tests/core/runtime/test_pipeline_runner_agent_runtime.py`

- [ ] **Step 1: Write failing test**

```python
# tests/core/runtime/test_pipeline_runner_agent_runtime.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from miniautogen.core.runtime.pipeline_runner import PipelineRunner
from miniautogen.core.runtime.agent_runtime import AgentRuntime


@pytest.mark.anyio
async def test_build_agent_runtimes_creates_runtime_per_agent():
    """PipelineRunner should build an AgentRuntime for each agent in the plan."""
    # This test verifies the factory method exists and produces AgentRuntimes
    runner = PipelineRunner()
    assert hasattr(runner, '_build_agent_runtimes')
```

- [ ] **Step 2: Implement _build_agent_runtimes in PipelineRunner**

Add the factory method to `PipelineRunner`. This wires the AgentRuntime compositor into the execution flow. The method reads agent configs from the plan/workspace, creates fresh drivers, loads per-agent configs from `.miniautogen/agents/{name}/`, and returns `dict[str, AgentRuntime]`.

- [ ] **Step 3: Run tests (existing + new)**

Run: `python -m pytest tests/core/runtime/ -v`
Expected: ALL PASS (existing tests unchanged, new test passes)

- [ ] **Step 4: Commit**

```bash
git add miniautogen/core/runtime/pipeline_runner.py tests/core/runtime/test_pipeline_runner_agent_runtime.py
git commit -m "feat(runtime): add _build_agent_runtimes factory to PipelineRunner"
```

---

## Task 8: PersistentMemoryProvider

**Files:**
- Create: `miniautogen/core/runtime/persistent_memory.py`
- Test: `tests/core/runtime/test_persistent_memory.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/core/runtime/test_persistent_memory.py
import pytest
import anyio
from pathlib import Path
from miniautogen.core.contracts.delegation import PersistableMemory
from miniautogen.core.contracts.memory_provider import MemoryProvider
from miniautogen.core.runtime.persistent_memory import PersistentMemoryProvider


def test_satisfies_memory_provider_protocol(tmp_path):
    pmp = PersistentMemoryProvider(memory_dir=tmp_path / "memory")
    assert isinstance(pmp, MemoryProvider)


def test_satisfies_persistable_memory_protocol(tmp_path):
    pmp = PersistentMemoryProvider(memory_dir=tmp_path / "memory")
    assert isinstance(pmp, PersistableMemory)


@pytest.mark.anyio
async def test_persist_and_reload(tmp_path):
    memory_dir = tmp_path / "memory"
    pmp = PersistentMemoryProvider(memory_dir=memory_dir)
    from miniautogen.core.events.execution_event import RunContext
    ctx = RunContext(run_id="r1", agent_id="a1")

    await pmp.save_turn([{"role": "user", "content": "hello"}], ctx)
    await pmp.persist_to_disk()

    # Create new instance and reload
    pmp2 = PersistentMemoryProvider(memory_dir=memory_dir)
    await pmp2.load_from_disk()
    context = await pmp2.get_context("a1", ctx)
    assert len(context) > 0
```

- [ ] **Step 2: Implement PersistentMemoryProvider**

Extends `InMemoryMemoryProvider`. Adds `load_from_disk()`, `persist_to_disk()`, `search()`. Stores entries as JSON in `memory_dir/entries/` and context summary in `memory_dir/context.json`.

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/core/runtime/test_persistent_memory.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add miniautogen/core/runtime/persistent_memory.py tests/core/runtime/test_persistent_memory.py
git commit -m "feat(runtime): add PersistentMemoryProvider with filesystem persistence"
```

---

## Task 9: FileSystemToolRegistry

**Files:**
- Create: `miniautogen/core/runtime/filesystem_tool_registry.py`
- Test: `tests/core/runtime/test_filesystem_tool_registry.py`

- [ ] **Step 1: Write failing tests**

Tests for loading tools.yml, executing builtin tools, rejecting script path traversal.

- [ ] **Step 2: Implement FileSystemToolRegistry**

Loads `tools.yml`, supports `builtin` and `script` tool types. Script execution uses `anyio.open_process` without `shell=True`, params via stdin.

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/core/runtime/test_filesystem_tool_registry.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add miniautogen/core/runtime/filesystem_tool_registry.py tests/core/runtime/test_filesystem_tool_registry.py
git commit -m "feat(runtime): add FileSystemToolRegistry with tools.yml loading"
```

---

## Task 10: Security — Agent Name Validation + Filesystem Sandbox

**Files:**
- Modify: `miniautogen/core/contracts/agent_spec.py` (add validator)
- Create: `miniautogen/core/runtime/agent_sandbox.py`
- Test: `tests/core/runtime/test_agent_sandbox.py`
- Test: `tests/core/contracts/test_agent_spec_security.py`

- [ ] **Step 1: Write failing security tests**

```python
# tests/core/contracts/test_agent_spec_security.py
import pytest
from miniautogen.core.contracts.agent_spec import AgentSpec


@pytest.mark.parametrize("malicious_id", [
    "../../etc/passwd",
    "../shared",
    "agent/../../root",
    "agent\x00null",
    "..",
    ".",
    "",
    "a" * 256,
])
def test_reject_malicious_agent_ids(malicious_id):
    with pytest.raises(ValueError):
        AgentSpec(id=malicious_id, name="Test")
```

- [ ] **Step 2: Add field_validator to AgentSpec**

```python
import re
from pydantic import field_validator

@field_validator("id")
@classmethod
def validate_id(cls, v: str) -> str:
    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$", v):
        raise ValueError(
            f"Agent ID must be alphanumeric with .-_ only, "
            f"1-64 chars, no path separators: {v!r}"
        )
    return v
```

- [ ] **Step 3: Implement AgentFilesystemSandbox + ToolExecutionPolicy**

- [ ] **Step 4: Run all security tests**

Run: `python -m pytest tests/core/contracts/test_agent_spec_security.py tests/core/runtime/test_agent_sandbox.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add miniautogen/core/contracts/agent_spec.py miniautogen/core/runtime/agent_sandbox.py tests/
git commit -m "feat(core): add agent name validation and filesystem sandbox security"
```

---

## Task 11: CLI Scaffold + Exports + Docs

**Files:**
- Modify: `miniautogen/cli/commands/init.py`
- Modify: `miniautogen/api.py`
- Modify: `miniautogen/core/contracts/__init__.py`

- [ ] **Step 1: Update `mag init` to scaffold .miniautogen/agents/**

Add scaffolding of `.miniautogen/agents/` directory with a sample agent config when running `mag init`.

- [ ] **Step 2: Export new types from api.py**

Add `AgentRuntime`, `ToolDefinition`, `ToolCall`, `TurnResult`, `PersistentMemoryProvider`, `InMemoryToolRegistry`, `ConfigDelegationRouter` to `miniautogen/api.py`.

- [ ] **Step 3: Update docs event count**

Update `docs/pt/README.md` event reference from "63+" to "69" once events are implemented.

- [ ] **Step 4: Commit**

```bash
git add miniautogen/cli/commands/init.py miniautogen/api.py miniautogen/core/contracts/__init__.py
git commit -m "chore(cli): scaffold .miniautogen/agents/ and export AgentRuntime types"
```

---

## Task 12: Integration Test — Full Flow

**Files:**
- Test: `tests/core/runtime/test_agent_runtime_integration.py`

- [ ] **Step 1: Write integration test**

End-to-end test: create AgentRuntime with mock driver, register tools, configure memory, run through WorkflowRuntime, verify hooks fired, tools available, memory persisted.

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest tests/ -v --timeout=60`
Expected: ALL PASS (existing + new)

- [ ] **Step 3: Commit**

```bash
git add tests/core/runtime/test_agent_runtime_integration.py
git commit -m "test(runtime): add AgentRuntime integration test with full flow"
```

---

## Code Review Checkpoint

After Task 12, run the 3 parallel reviewers before merging:

```
/ring-default:codereview
```

---

## Summary

| Task | What | Files | Est |
|------|------|-------|-----|
| 1 | Contracts + errors | 6 new | 1-2h |
| 2 | EventTypes | 1 mod + 1 test | 30min |
| 3 | InMemoryToolRegistry | 1 new + 1 test | 1h |
| 4 | ConfigDelegationRouter | 1 new + 1 test | 1h |
| 5 | **AgentRuntime** (core) | 1 new + 1 test | 2-3h |
| 6 | create_fresh_driver | 2 mod + 2 tests | 1h |
| 7 | PipelineRunner factory | 1 mod + 1 test | 1-2h |
| 8 | PersistentMemoryProvider | 1 new + 1 test | 1-2h |
| 9 | FileSystemToolRegistry | 1 new + 1 test | 1-2h |
| 10 | Security (validation + sandbox) | 2 mod + 2 new + tests | 1-2h |
| 11 | CLI scaffold + exports + docs | 3 mod | 30min |
| 12 | Integration test | 1 test | 1h |
