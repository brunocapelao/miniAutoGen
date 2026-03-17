# Terminal Harness Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 3 new CLI commands (`chat`, `gateway serve`, `backend ping/list`) to MiniAutoGen following Claude Code UX patterns.

**Architecture:** Click commands delegate to async service functions via `run_async()`. Backend resolution bridges `ProjectConfig` (YAML) to `BackendResolver` via a new `build_resolver_from_config()` helper. New CLI-layer events use `scope="cli.*"` to coexist with existing `BACKEND_*` driver events.

**Tech Stack:** Click (CLI), AnyIO (async), Pydantic (models), uvicorn (gateway), pytest + click.testing (tests)

**Spec:** `docs/superpowers/specs/2026-03-17-terminal-harness-design.md`

---

## File Structure

### New files

| File | Responsibility |
|------|---------------|
| `miniautogen/cli/commands/chat.py` | Click command: flags, TTY detection, routing to service |
| `miniautogen/cli/commands/gateway.py` | Click group + `serve` subcommand |
| `miniautogen/cli/commands/backend.py` | Click group + `ping`/`list` subcommands |
| `miniautogen/cli/services/chat_service.py` | `run_interactive_chat()`, `run_single_turn()` |
| `miniautogen/cli/services/gateway_service.py` | `start_gateway_server()` |
| `miniautogen/cli/services/backend_service.py` | `ping_backend()`, `list_backends()` |
| `miniautogen/cli/services/operator_input.py` | `OperatorInput` protocol + `StdlibOperatorInput` |
| `miniautogen/cli/services/slash_commands.py` | `SlashCommandHandler`, `SlashCommandRegistry`, built-ins |
| `miniautogen/cli/services/resolver_factory.py` | `build_resolver_from_config()` |
| `tests/cli/commands/test_chat.py` | Chat command tests |
| `tests/cli/commands/test_gateway.py` | Gateway command tests |
| `tests/cli/commands/test_backend.py` | Backend command tests |
| `tests/cli/services/test_chat_service.py` | Chat service tests |
| `tests/cli/services/test_backend_service.py` | Backend service tests |
| `tests/cli/services/test_gateway_service.py` | Gateway service tests |
| `tests/cli/services/test_operator_input.py` | OperatorInput tests |
| `tests/cli/services/test_slash_commands.py` | Slash command tests |
| `tests/cli/services/test_resolver_factory.py` | Resolver factory tests |

### Modified files

| File | Change |
|------|--------|
| `miniautogen/cli/config.py:60-73` | Add `backends` field to `ProjectConfig` |
| `miniautogen/cli/errors.py:35-37` | Add `BackendNotFoundError(10)`, `TurnTimeoutError(11)`, `TurnCancelledError(12)` |
| `miniautogen/cli/main.py:46-48` | Register 3 new commands |
| `miniautogen/core/events/types.py:47-89` | Add 12 new CLI event types + `CLI_EVENT_TYPES` set |

---

## Task 1: Foundation — Config, errors, events, resolver factory

**Files:**
- Modify: `miniautogen/cli/config.py:60-73`
- Modify: `miniautogen/cli/errors.py:35-37`
- Modify: `miniautogen/core/events/types.py:47-89`
- Create: `miniautogen/cli/services/resolver_factory.py`
- Test: `tests/cli/services/test_resolver_factory.py`
- Test: `tests/cli/test_errors.py` (extend)

### Review checkpoint after this task.

- [ ] **Step 1: Write failing tests for new error classes**

Create `tests/cli/test_errors.py` additions:

```python
# Append to existing tests/cli/test_errors.py
import pytest
from miniautogen.cli.errors import (
    BackendNotFoundError,
    TurnTimeoutError,
    TurnCancelledError,
    CLIError,
)


def test_backend_not_found_error_exit_code():
    err = BackendNotFoundError("backend 'x' not found")
    assert isinstance(err, CLIError)
    assert err.exit_code == 10


def test_turn_timeout_error_exit_code():
    err = TurnTimeoutError("turn timed out")
    assert isinstance(err, CLIError)
    assert err.exit_code == 11


def test_turn_cancelled_error_exit_code():
    err = TurnCancelledError("cancelled by user")
    assert isinstance(err, CLIError)
    assert err.exit_code == 12
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/cli/test_errors.py -v -k "backend_not_found or turn_timeout or turn_cancelled"`
Expected: FAIL with `ImportError` — classes don't exist yet.

- [ ] **Step 3: Implement new error classes**

Add to `miniautogen/cli/errors.py` after line 37:

```python
class BackendNotFoundError(CLIError):
    """Referenced backend does not exist in project config."""
    exit_code = 10


class TurnTimeoutError(CLIError):
    """Turn execution exceeded timeout."""
    exit_code = 11


class TurnCancelledError(CLIError):
    """Turn cancelled by user (Ctrl+C)."""
    exit_code = 12
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/cli/test_errors.py -v`
Expected: ALL PASS

- [ ] **Step 5: Write failing tests for EventType additions**

Create `tests/core/events/test_cli_event_types.py`:

```python
from miniautogen.core.events.types import EventType, CLI_EVENT_TYPES


def test_cli_chat_event_types_exist():
    assert EventType.CHAT_SESSION_STARTED.value == "chat_session_started"
    assert EventType.CHAT_TURN_STARTED.value == "chat_turn_started"
    assert EventType.CHAT_RESPONSE_DELTA.value == "chat_response_delta"
    assert EventType.CHAT_TURN_COMPLETED.value == "chat_turn_completed"
    assert EventType.CHAT_TURN_CANCELLED.value == "chat_turn_cancelled"
    assert EventType.CHAT_TURN_FAILED.value == "chat_turn_failed"
    assert EventType.CHAT_SESSION_CLOSED.value == "chat_session_closed"


def test_cli_gateway_event_types_exist():
    assert EventType.GATEWAY_SERVER_STARTING.value == "gateway_server_starting"
    assert EventType.GATEWAY_SERVER_STARTED.value == "gateway_server_started"
    assert EventType.GATEWAY_SERVER_STOPPED.value == "gateway_server_stopped"
    assert EventType.GATEWAY_SERVER_FAILED.value == "gateway_server_failed"


def test_cli_backend_event_types_exist():
    assert EventType.CLI_BACKEND_HEALTH_CHECKED.value == "backend_health_checked"


def test_cli_event_types_set():
    assert EventType.CHAT_SESSION_STARTED in CLI_EVENT_TYPES
    assert EventType.GATEWAY_SERVER_STARTING in CLI_EVENT_TYPES
    assert EventType.CLI_BACKEND_HEALTH_CHECKED in CLI_EVENT_TYPES
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `python -m pytest tests/core/events/test_cli_event_types.py -v`
Expected: FAIL with `ImportError` — new enum members don't exist yet

- [ ] **Step 7: Add new event types to EventType enum**

Add to `miniautogen/core/events/types.py` after the APPROVAL events block (line 53):

```python
    # CLI operator events
    CHAT_SESSION_STARTED = "chat_session_started"
    CHAT_TURN_STARTED = "chat_turn_started"
    CHAT_RESPONSE_DELTA = "chat_response_delta"
    CHAT_TURN_COMPLETED = "chat_turn_completed"
    CHAT_TURN_CANCELLED = "chat_turn_cancelled"
    CHAT_TURN_FAILED = "chat_turn_failed"
    CHAT_SESSION_CLOSED = "chat_session_closed"

    GATEWAY_SERVER_STARTING = "gateway_server_starting"
    GATEWAY_SERVER_STARTED = "gateway_server_started"
    GATEWAY_SERVER_STOPPED = "gateway_server_stopped"
    GATEWAY_SERVER_FAILED = "gateway_server_failed"

    CLI_BACKEND_HEALTH_CHECKED = "backend_health_checked"
```

And add after line 89:

```python
CLI_EVENT_TYPES: set[EventType] = {
    EventType.CHAT_SESSION_STARTED,
    EventType.CHAT_TURN_STARTED,
    EventType.CHAT_RESPONSE_DELTA,
    EventType.CHAT_TURN_COMPLETED,
    EventType.CHAT_TURN_CANCELLED,
    EventType.CHAT_TURN_FAILED,
    EventType.CHAT_SESSION_CLOSED,
    EventType.GATEWAY_SERVER_STARTING,
    EventType.GATEWAY_SERVER_STARTED,
    EventType.GATEWAY_SERVER_STOPPED,
    EventType.GATEWAY_SERVER_FAILED,
    EventType.CLI_BACKEND_HEALTH_CHECKED,
}
```

- [ ] **Step 8: Run event type tests to verify they pass**

Run: `python -m pytest tests/core/events/test_cli_event_types.py -v`
Expected: ALL PASS

- [ ] **Step 9: Add `backends` field to `ProjectConfig`**

In `miniautogen/cli/config.py`, add imports at top:

```python
from miniautogen.backends.config import BackendConfig
from pydantic import model_validator  # add to existing import if not present
```

Add field to `ProjectConfig` class after line 73 (`database` field):

```python
    backends: dict[str, BackendConfig] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def inject_backend_ids(cls, data: dict) -> dict:
        """Inject YAML dict keys as backend_id into each BackendConfig."""
        if isinstance(data, dict) and "backends" in data:
            for bid, entry in data["backends"].items():
                if isinstance(entry, dict):
                    entry["backend_id"] = bid
        return data
```

This ensures YAML keys (e.g., `gemini`) are injected as `backend_id` into each `BackendConfig` before Pydantic validation runs.

- [ ] **Step 10: Write failing tests for resolver factory**

Create `tests/cli/services/test_resolver_factory.py`:

```python
"""Tests for build_resolver_from_config."""
from __future__ import annotations

import pytest

from miniautogen.backends.config import BackendConfig, DriverType
from miniautogen.backends.errors import BackendUnavailableError
from miniautogen.cli.config import ProjectConfig, ProjectMeta
from miniautogen.cli.services.resolver_factory import build_resolver_from_config


def _make_config(**backend_entries: dict) -> ProjectConfig:
    backends = {}
    for bid, entry in backend_entries.items():
        backends[bid] = BackendConfig(backend_id=bid, **entry)
    return ProjectConfig(
        project=ProjectMeta(name="test"),
        backends=backends,
    )


def test_empty_config_returns_empty_resolver():
    config = ProjectConfig(project=ProjectMeta(name="test"))
    resolver = build_resolver_from_config(config)
    assert resolver.list_backends() == []


def test_resolver_lists_configured_backends():
    config = _make_config(
        gemini={"driver": "agentapi", "endpoint": "http://localhost:8000"},
    )
    resolver = build_resolver_from_config(config)
    assert "gemini" in resolver.list_backends()


def test_resolver_stores_config():
    config = _make_config(
        gemini={"driver": "agentapi", "endpoint": "http://localhost:8000"},
    )
    resolver = build_resolver_from_config(config)
    bc = resolver.get_config("gemini")
    assert bc is not None
    assert bc.endpoint == "http://localhost:8000"


def test_resolver_raises_for_unknown_backend():
    config = _make_config(
        gemini={"driver": "agentapi", "endpoint": "http://localhost:8000"},
    )
    resolver = build_resolver_from_config(config)
    with pytest.raises(BackendUnavailableError):
        resolver.get_driver("nonexistent")
```

- [ ] **Step 11: Run resolver factory tests to verify they fail**

Run: `python -m pytest tests/cli/services/test_resolver_factory.py -v`
Expected: FAIL with `ImportError` — module doesn't exist yet.

- [ ] **Step 12: Implement resolver factory**

Create `miniautogen/cli/services/resolver_factory.py`:

```python
"""Bridge between ProjectConfig and BackendResolver.

Populates a BackendResolver from the backends declared in miniautogen.yaml.
"""
from __future__ import annotations

from miniautogen.backends.agentapi.factory import agentapi_factory
from miniautogen.backends.config import DriverType
from miniautogen.backends.resolver import BackendResolver
from miniautogen.cli.config import ProjectConfig


def build_resolver_from_config(config: ProjectConfig) -> BackendResolver:
    """Create a BackendResolver populated from project config.

    Registers known driver factories and adds all configured backends.
    """
    resolver = BackendResolver()

    # Register built-in factories
    resolver.register_factory(DriverType.AGENT_API, agentapi_factory)

    # Add all backends from config
    for backend_config in config.backends.values():
        resolver.add_backend(backend_config)

    return resolver
```

- [ ] **Step 13: Run resolver factory tests to verify they pass**

Run: `python -m pytest tests/cli/services/test_resolver_factory.py -v`
Expected: ALL PASS

- [ ] **Step 14: Commit**

```bash
git add miniautogen/cli/errors.py miniautogen/core/events/types.py miniautogen/cli/config.py miniautogen/cli/services/resolver_factory.py tests/cli/test_errors.py tests/cli/services/test_resolver_factory.py
git commit -m "feat: add foundation for terminal harness — errors, events, config, resolver factory"
```

---

## Task 2: OperatorInput + Slash Commands

**Files:**
- Create: `miniautogen/cli/services/operator_input.py`
- Create: `miniautogen/cli/services/slash_commands.py`
- Test: `tests/cli/services/test_operator_input.py`
- Test: `tests/cli/services/test_slash_commands.py`

- [ ] **Step 1: Write failing tests for OperatorInput**

Create `tests/cli/services/test_operator_input.py`:

```python
"""Tests for OperatorInput protocol and StdlibOperatorInput."""
from __future__ import annotations

from unittest.mock import patch

import anyio
import pytest

from miniautogen.cli.services.operator_input import (
    OperatorInput,
    StdlibOperatorInput,
)


@pytest.mark.anyio
async def test_stdlib_input_returns_user_text():
    op = StdlibOperatorInput()
    with patch("builtins.input", return_value="hello"):
        result = await op.read_line(">>> ")
    assert result == "hello"


@pytest.mark.anyio
async def test_stdlib_input_returns_none_on_eof():
    op = StdlibOperatorInput()
    with patch("builtins.input", side_effect=EOFError):
        result = await op.read_line(">>> ")
    assert result is None


@pytest.mark.anyio
async def test_stdlib_input_returns_none_on_keyboard_interrupt():
    op = StdlibOperatorInput()
    with patch("builtins.input", side_effect=KeyboardInterrupt):
        result = await op.read_line(">>> ")
    assert result is None


def test_stdlib_input_implements_protocol():
    op = StdlibOperatorInput()
    assert isinstance(op, OperatorInput)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/cli/services/test_operator_input.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement OperatorInput**

Create `miniautogen/cli/services/operator_input.py`:

```python
"""Operator input abstraction for the chat REPL.

Encapsulates input capture so the chat service never calls input() directly.
MVP uses StdlibOperatorInput; replaceable by PromptToolkit, Textual, etc.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

import anyio


@runtime_checkable
class OperatorInput(Protocol):
    """Protocol for reading operator input in the chat REPL."""

    async def read_line(self, prompt: str = ">>> ") -> str | None:
        """Read a line of input. Returns None on EOF or interrupt."""
        ...


class StdlibOperatorInput:
    """OperatorInput using stdlib input() via anyio thread offload."""

    async def read_line(self, prompt: str = ">>> ") -> str | None:
        try:
            return await anyio.to_thread.run_sync(lambda: input(prompt))
        except (EOFError, KeyboardInterrupt):
            return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/cli/services/test_operator_input.py -v`
Expected: ALL PASS

- [ ] **Step 5: Write failing tests for slash commands**

Create `tests/cli/services/test_slash_commands.py`:

```python
"""Tests for SlashCommandRegistry and built-in commands."""
from __future__ import annotations

import pytest

from miniautogen.cli.services.slash_commands import (
    SlashCommandRegistry,
    create_default_registry,
)


def test_resolve_known_command():
    registry = create_default_registry()
    result = registry.resolve("/help")
    assert result is not None
    handler, args = result
    assert args == ""


def test_resolve_command_with_args():
    registry = create_default_registry()
    result = registry.resolve("/help something")
    assert result is not None
    _, args = result
    assert args == "something"


def test_resolve_unknown_command_returns_error_handler():
    registry = create_default_registry()
    result = registry.resolve("/nonexistent")
    assert result is not None  # returns an error handler, not None
    handler, args = result
    # handler should produce error message when called


def test_resolve_non_slash_returns_none():
    registry = create_default_registry()
    result = registry.resolve("hello world")
    assert result is None


def test_default_registry_has_builtins():
    registry = create_default_registry()
    for cmd in ["/exit", "/clear", "/help"]:
        assert registry.resolve(cmd) is not None, f"{cmd} not found"


def test_register_custom_command():
    registry = SlashCommandRegistry()

    async def handler(args: str, context: object) -> str | None:
        return f"handled: {args}"

    registry.register("test", handler)
    result = registry.resolve("/test foo")
    assert result is not None
    h, a = result
    assert a == "foo"
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `python -m pytest tests/cli/services/test_slash_commands.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 7: Implement slash commands**

Create `miniautogen/cli/services/slash_commands.py`:

```python
"""Extensible slash command registry for the chat REPL.

Inputs starting with '/' are intercepted and dispatched to registered handlers.
Unknown commands produce an error listing available commands.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable


SlashHandler = Callable[[str, Any], Awaitable[str | None]]


class SlashCommandRegistry:
    """Registry that maps slash command names to handlers."""

    def __init__(self) -> None:
        self._handlers: dict[str, SlashHandler] = {}

    def register(self, name: str, handler: SlashHandler) -> None:
        """Register a handler for a slash command name (without leading /)."""
        self._handlers[name] = handler

    def resolve(self, input_line: str) -> tuple[SlashHandler, str] | None:
        """Parse input and return (handler, args) if it's a slash command.

        Returns None if input is not a slash command or command is unknown.
        """
        if not input_line.startswith("/"):
            return None

        parts = input_line[1:].split(maxsplit=1)
        if not parts:
            return None

        name = parts[0]
        args = parts[1] if len(parts) > 1 else ""

        handler = self._handlers.get(name)
        if handler is None:
            # Unknown slash command — return error handler (never send to backend)
            async def _unknown(a: str, ctx: Any) -> str | None:
                cmds = ", ".join(f"/{c}" for c in sorted(self._handlers.keys()))
                return f"Unknown command '/{name}'. Available: {cmds}"
            return _unknown, args

        return handler, args

    def list_commands(self) -> list[str]:
        """Return sorted list of registered command names."""
        return sorted(self._handlers.keys())


# Built-in handlers

async def _handle_exit(args: str, context: Any) -> str | None:
    """Signal the REPL to exit."""
    return "__exit__"


async def _handle_clear(args: str, context: Any) -> str | None:
    """Clear the in-memory transcript."""
    return "__clear__"


async def _handle_help(args: str, context: Any) -> str | None:
    """List available commands."""
    return "__help__"


def create_default_registry() -> SlashCommandRegistry:
    """Create a registry with built-in slash commands."""
    registry = SlashCommandRegistry()
    registry.register("exit", _handle_exit)
    registry.register("clear", _handle_clear)
    registry.register("help", _handle_help)
    return registry
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `python -m pytest tests/cli/services/test_slash_commands.py -v`
Expected: ALL PASS

- [ ] **Step 9: Commit**

```bash
git add miniautogen/cli/services/operator_input.py miniautogen/cli/services/slash_commands.py tests/cli/services/test_operator_input.py tests/cli/services/test_slash_commands.py
git commit -m "feat: add OperatorInput protocol and slash command registry"
```

---

## Task 3: Backend service + `backend` command

**Files:**
- Create: `miniautogen/cli/services/backend_service.py`
- Create: `miniautogen/cli/commands/backend.py`
- Test: `tests/cli/services/test_backend_service.py`
- Test: `tests/cli/commands/test_backend.py`
- Modify: `miniautogen/cli/main.py:46-48`

### Review checkpoint after this task.

- [ ] **Step 1: Write failing tests for backend service**

Create `tests/cli/services/test_backend_service.py`:

```python
"""Tests for backend ping/list service functions."""
from __future__ import annotations

from unittest.mock import AsyncMock

import anyio
import pytest

from miniautogen.backends.config import BackendConfig, DriverType
from miniautogen.backends.models import BackendCapabilities, StartSessionResponse
from miniautogen.backends.resolver import BackendResolver
from miniautogen.cli.services.backend_service import ping_backend, list_backends


def _make_resolver_with_mock_driver(
    backend_id: str = "test",
    capabilities: BackendCapabilities | None = None,
) -> tuple[BackendResolver, AsyncMock]:
    caps = capabilities or BackendCapabilities(sessions=True, tools=True)
    driver = AsyncMock()
    driver.capabilities = AsyncMock(return_value=caps)
    driver.start_session = AsyncMock(
        return_value=StartSessionResponse(
            session_id="sess-1",
            capabilities=caps,
        )
    )
    driver.close_session = AsyncMock()

    resolver = BackendResolver()
    config = BackendConfig(
        backend_id=backend_id,
        driver=DriverType.AGENT_API,
        endpoint="http://localhost:8000",
    )
    resolver.add_backend(config)
    resolver._cache[backend_id] = driver
    return resolver, driver


@pytest.mark.anyio
async def test_ping_basic_returns_ok():
    resolver, driver = _make_resolver_with_mock_driver()
    result = await ping_backend(resolver, "test", timeout=5.0, deep=False)
    assert result["status"] == "ok"
    assert result["reachable"] is True
    assert "latency_ms" in result
    assert result["probe"] == "basic"
    driver.capabilities.assert_awaited_once()


@pytest.mark.anyio
async def test_ping_deep_calls_session():
    resolver, driver = _make_resolver_with_mock_driver()
    result = await ping_backend(resolver, "test", timeout=5.0, deep=True)
    assert result["status"] == "ok"
    assert result["probe"] == "deep"
    driver.start_session.assert_awaited_once()
    driver.close_session.assert_awaited_once()


@pytest.mark.anyio
async def test_ping_unreachable():
    resolver, driver = _make_resolver_with_mock_driver()
    driver.capabilities = AsyncMock(side_effect=ConnectionError("refused"))
    result = await ping_backend(resolver, "test", timeout=5.0, deep=False)
    assert result["status"] == "unreachable"
    assert result["reachable"] is False


@pytest.mark.anyio
async def test_ping_timeout():
    resolver, driver = _make_resolver_with_mock_driver()

    async def slow_caps():
        await anyio.sleep(10)
        return BackendCapabilities()

    driver.capabilities = slow_caps
    result = await ping_backend(resolver, "test", timeout=0.1, deep=False)
    assert result["status"] == "timeout"
    assert result["reachable"] is False


def test_list_backends_returns_configured():
    resolver, _ = _make_resolver_with_mock_driver("gemini")
    result = list_backends(resolver)
    assert len(result) == 1
    assert result[0]["backend_id"] == "gemini"
    assert result[0]["driver"] == "agentapi"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/cli/services/test_backend_service.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement backend service**

Create `miniautogen/cli/services/backend_service.py`:

```python
"""Backend diagnostic services for the CLI.

Provides ping (health check + capabilities) and list operations.
"""
from __future__ import annotations

import time
from typing import Any

import anyio

from miniautogen.backends.config import DriverType
from miniautogen.backends.errors import BackendUnavailableError
from miniautogen.backends.models import StartSessionRequest
from miniautogen.backends.resolver import BackendResolver


async def ping_backend(
    resolver: BackendResolver,
    backend_id: str,
    *,
    timeout: float = 5.0,
    deep: bool = False,
) -> dict[str, Any]:
    """Ping a backend and return status, capabilities, and latency."""
    config = resolver.get_config(backend_id)
    if config is None:
        return {
            "backend_id": backend_id,
            "status": "misconfigured",
            "reachable": False,
            "latency_ms": 0,
            "driver": "unknown",
            "target": "unknown",
            "probe": "deep" if deep else "basic",
            "capabilities": {},
            "error": f"Backend '{backend_id}' not found in config",
        }

    driver = resolver.get_driver(backend_id)
    target = config.endpoint or " ".join(config.command or []) or "-"
    probe = "deep" if deep else "basic"

    start = time.monotonic()
    try:
        async with anyio.fail_after(timeout):
            caps = await driver.capabilities()

            if deep:
                req = StartSessionRequest(backend_id=backend_id)
                resp = await driver.start_session(req)
                try:
                    await driver.close_session(resp.session_id)
                except BaseException:
                    with anyio.move_on_after(2.0):
                        await driver.close_session(resp.session_id)
                    raise

    except TimeoutError:
        elapsed = (time.monotonic() - start) * 1000
        return {
            "backend_id": backend_id,
            "status": "timeout",
            "reachable": False,
            "latency_ms": round(elapsed),
            "driver": config.driver.value,
            "target": target,
            "probe": probe,
            "capabilities": {},
            "error": f"Timed out after {timeout}s",
        }
    except (ConnectionError, OSError) as exc:
        elapsed = (time.monotonic() - start) * 1000
        return {
            "backend_id": backend_id,
            "status": "unreachable",
            "reachable": False,
            "latency_ms": round(elapsed),
            "driver": config.driver.value,
            "target": target,
            "probe": probe,
            "capabilities": {},
            "error": str(exc),
        }
    except Exception as exc:
        elapsed = (time.monotonic() - start) * 1000
        return {
            "backend_id": backend_id,
            "status": "unreachable",
            "reachable": False,
            "latency_ms": round(elapsed),
            "driver": config.driver.value,
            "target": target,
            "probe": probe,
            "capabilities": {},
            "error": str(exc),
        }

    elapsed = (time.monotonic() - start) * 1000
    caps_dict = caps.model_dump()
    return {
        "backend_id": backend_id,
        "status": "ok",
        "reachable": True,
        "latency_ms": round(elapsed),
        "driver": config.driver.value,
        "target": target,
        "probe": probe,
        "capabilities": caps_dict,
        "error": None,
    }


def list_backends(resolver: BackendResolver) -> list[dict[str, Any]]:
    """List all configured backends without connecting."""
    results = []
    for bid in resolver.list_backends():
        config = resolver.get_config(bid)
        if config is None:
            continue
        target = config.endpoint or " ".join(config.command or []) or "-"
        results.append({
            "backend_id": bid,
            "driver": config.driver.value,
            "target": target,
        })
    return results
```

- [ ] **Step 4: Run service tests to verify they pass**

Run: `python -m pytest tests/cli/services/test_backend_service.py -v`
Expected: ALL PASS

- [ ] **Step 5: Write failing tests for backend CLI command**

Create `tests/cli/commands/test_backend.py`:

```python
"""Tests for miniautogen backend ping/list commands."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from click.testing import CliRunner

from miniautogen.cli.main import cli


@patch("miniautogen.cli.commands.backend.require_project_config")
@patch("miniautogen.cli.commands.backend.build_resolver_from_config")
@patch("miniautogen.cli.commands.backend.ping_backend", new_callable=AsyncMock)
def test_backend_ping_text_output(mock_ping, mock_resolver, mock_config):
    from miniautogen.cli.config import ProjectConfig, ProjectMeta

    mock_config.return_value = (
        "/tmp",
        ProjectConfig(project=ProjectMeta(name="test")),
    )
    mock_resolver.return_value = AsyncMock()
    mock_ping.return_value = {
        "backend_id": "gemini",
        "status": "ok",
        "reachable": True,
        "latency_ms": 42,
        "driver": "agentapi",
        "target": "http://localhost:8000",
        "probe": "basic",
        "capabilities": {
            "sessions": True,
            "streaming": False,
            "cancel": False,
            "tools": True,
            "artifacts": False,
            "multimodal": False,
        },
        "error": None,
    }

    runner = CliRunner()
    result = runner.invoke(cli, ["backend", "ping", "gemini"])
    assert result.exit_code == 0
    assert "gemini" in result.output
    assert "ok" in result.output


@patch("miniautogen.cli.commands.backend.require_project_config")
@patch("miniautogen.cli.commands.backend.build_resolver_from_config")
@patch("miniautogen.cli.commands.backend.list_backends_svc")
def test_backend_list_text_output(mock_list, mock_resolver, mock_config):
    from miniautogen.cli.config import ProjectConfig, ProjectMeta
    from miniautogen.cli.config import ProjectConfig, ProjectMeta

    mock_config.return_value = (
        "/tmp",
        ProjectConfig(project=ProjectMeta(name="test")),
    )
    mock_resolver.return_value = AsyncMock()
    mock_list.return_value = [
        {"backend_id": "gemini", "driver": "agentapi", "target": "http://localhost:8000"},
    ]

    runner = CliRunner()
    result = runner.invoke(cli, ["backend", "list"])
    assert result.exit_code == 0
    assert "gemini" in result.output
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `python -m pytest tests/cli/commands/test_backend.py -v`
Expected: FAIL — command not registered yet.

- [ ] **Step 7: Implement backend CLI command**

Create `miniautogen/cli/commands/backend.py`:

```python
"""miniautogen backend command group — ping and list subcommands."""
from __future__ import annotations

import click

from miniautogen.cli.config import require_project_config
from miniautogen.cli.errors import BackendNotFoundError
from miniautogen.cli.main import run_async
from miniautogen.cli.output import echo_error, echo_json, echo_success, echo_table
from miniautogen.cli.services.backend_service import (
    list_backends as list_backends_svc,
    ping_backend,
)
from miniautogen.cli.services.resolver_factory import build_resolver_from_config
from miniautogen.backends.errors import BackendUnavailableError


@click.group("backend")
def backend_group() -> None:
    """Manage and diagnose backends."""


@backend_group.command("ping")
@click.argument("backend_id")
@click.option("--timeout", "-t", type=float, default=5.0, help="Timeout in seconds.")
@click.option("--deep", is_flag=True, default=False, help="Include session probe.")
@click.option(
    "--output-format", "-o",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def backend_ping(backend_id: str, timeout: float, deep: bool, output_format: str) -> None:
    """Check if a backend is reachable and show capabilities."""
    _root, config = require_project_config()
    resolver = build_resolver_from_config(config)

    if backend_id not in [b for b in resolver.list_backends()]:
        raise BackendNotFoundError(f"Backend '{backend_id}' not found in config")

    result = run_async(ping_backend, resolver, backend_id, timeout=timeout, deep=deep)

    if output_format == "json":
        echo_json(result)
    else:
        status = result["status"]
        latency = result["latency_ms"]
        if result["reachable"]:
            echo_success(f"Backend '{backend_id}' is reachable ({latency}ms)")
        else:
            echo_error(f"Backend '{backend_id}' is {status} ({latency}ms)")

        click.echo(f"\n  Driver:    {result['driver']}")
        click.echo(f"  Target:    {result['target']}")
        click.echo(f"  Status:    {status}")
        click.echo(f"  Probe:     {result['probe']}")

        caps = result.get("capabilities", {})
        if caps:
            click.echo("\n  Capabilities:")
            for cap, enabled in caps.items():
                val = "yes" if enabled else "no"
                click.echo(f"    {cap:<13}{val}")

    if not result["reachable"]:
        if status == "timeout":
            from miniautogen.cli.errors import TurnTimeoutError
            raise TurnTimeoutError(f"Backend timed out after {timeout}s")
        raise SystemExit(1)


@backend_group.command("list")
@click.option(
    "--output-format", "-o",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def backend_list(output_format: str) -> None:
    """List all configured backends."""
    _root, config = require_project_config()
    resolver = build_resolver_from_config(config)
    backends = list_backends_svc(resolver)

    if output_format == "json":
        echo_json(backends)
    else:
        if not backends:
            click.echo("No backends configured.")
            return
        click.echo("Backends configured:")
        echo_table(
            ["ID", "Driver", "Target"],
            [[b["backend_id"], b["driver"], b["target"]] for b in backends],
        )
```

- [ ] **Step 8: Register backend command in main.py**

Add to `miniautogen/cli/main.py` after the sessions import block:

```python
from miniautogen.cli.commands.backend import backend_group  # noqa: E402

cli.add_command(backend_group)
```

- [ ] **Step 9: Run all backend tests**

Run: `python -m pytest tests/cli/commands/test_backend.py tests/cli/services/test_backend_service.py -v`
Expected: ALL PASS

- [ ] **Step 10: Commit**

```bash
git add miniautogen/cli/commands/backend.py miniautogen/cli/services/backend_service.py miniautogen/cli/main.py tests/cli/commands/test_backend.py tests/cli/services/test_backend_service.py
git commit -m "feat: add backend ping and list commands"
```

---

## Task 4: Gateway service + `gateway serve` command

**Files:**
- Create: `miniautogen/cli/services/gateway_service.py`
- Create: `miniautogen/cli/commands/gateway.py`
- Test: `tests/cli/services/test_gateway_service.py`
- Test: `tests/cli/commands/test_gateway.py`
- Modify: `miniautogen/cli/main.py`

- [ ] **Step 1: Write failing tests for gateway service**

Create `tests/cli/services/test_gateway_service.py`:

```python
"""Tests for gateway service."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from miniautogen.cli.services.gateway_service import start_gateway_server


@pytest.mark.anyio
async def test_gateway_server_calls_uvicorn_serve():
    mock_server = AsyncMock()
    mock_server.serve = AsyncMock()

    with (
        patch("miniautogen.cli.services.gateway_service.import_gateway_app") as mock_import,
        patch("miniautogen.cli.services.gateway_service.uvicorn") as mock_uvicorn,
    ):
        mock_import.return_value = MagicMock()
        mock_config_instance = MagicMock()
        mock_uvicorn.Config.return_value = mock_config_instance
        mock_uvicorn.Server.return_value = mock_server

        await start_gateway_server(host="127.0.0.1", port=8000)

        mock_uvicorn.Config.assert_called_once()
        mock_uvicorn.Server.assert_called_once_with(mock_config_instance)
        mock_server.serve.assert_awaited_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/cli/services/test_gateway_service.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement gateway service**

Create `miniautogen/cli/services/gateway_service.py`:

```python
"""Gateway server service for the CLI.

Wraps the gemini_cli_gateway FastAPI app behind uvicorn.Server.serve().
"""
from __future__ import annotations

from typing import Any

import uvicorn

from miniautogen.cli.errors import CLIError


def import_gateway_app() -> Any:
    """Import the gateway FastAPI app. Raises CLIError if not available."""
    try:
        from gemini_cli_gateway.app import app
        return app
    except ImportError as exc:
        raise CLIError(
            "gemini_cli_gateway is not installed. "
            "Install it with: pip install -e ./gemini_cli_gateway"
        ) from exc


async def start_gateway_server(
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = False,
    log_level: str = "info",
) -> None:
    """Start the gateway server using uvicorn async API."""
    app = import_gateway_app()

    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
    )
    server = uvicorn.Server(config)
    await server.serve()
```

- [ ] **Step 4: Run service tests to verify they pass**

Run: `python -m pytest tests/cli/services/test_gateway_service.py -v`
Expected: ALL PASS

- [ ] **Step 5: Write failing tests for gateway CLI command**

Create `tests/cli/commands/test_gateway.py`:

```python
"""Tests for miniautogen gateway serve command."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

from miniautogen.cli.main import cli


@patch("miniautogen.cli.commands.gateway.start_gateway_server")
def test_gateway_serve_invokes_service(mock_serve):
    mock_serve.return_value = None  # run_async wraps the coroutine

    runner = CliRunner()
    result = runner.invoke(cli, ["gateway", "serve", "--port", "9000"])
    # The command will try to run_async, which calls anyio.run
    # In test context, we verify the command is registered and parses args
    assert "gateway" in cli.commands or result.exit_code is not None


def test_gateway_group_exists():
    runner = CliRunner()
    result = runner.invoke(cli, ["gateway", "--help"])
    assert result.exit_code == 0
    assert "serve" in result.output
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `python -m pytest tests/cli/commands/test_gateway.py -v`
Expected: FAIL — command not registered yet.

- [ ] **Step 7: Implement gateway CLI command**

Create `miniautogen/cli/commands/gateway.py`:

```python
"""miniautogen gateway command group."""
from __future__ import annotations

import click

from miniautogen.cli.main import run_async
from miniautogen.cli.output import echo_info
from miniautogen.cli.services.gateway_service import (
    import_gateway_app,
    start_gateway_server,
)


@click.group("gateway")
def gateway_group() -> None:
    """Manage agent gateways."""


@gateway_group.command("serve")
@click.option("--host", default="127.0.0.1", help="Bind address.")
@click.option("--port", "-p", type=int, default=8000, help="Port.")
@click.option("--reload", is_flag=True, default=False, help="Hot reload (dev only).")
@click.option(
    "--log-level",
    type=click.Choice(["critical", "error", "warning", "info", "debug"]),
    default="info",
    help="Uvicorn log level.",
)
def gateway_serve(host: str, port: int, reload: bool, log_level: str) -> None:
    """Start the Gemini CLI gateway server."""
    # Validate import early for clear error message
    import_gateway_app()

    reload_str = "on" if reload else "off"
    echo_info("MiniAutoGen Gateway")
    echo_info(f"  App:     gemini_cli_gateway")
    echo_info(f"  Bind:    http://{host}:{port}")
    echo_info(f"  Reload:  {reload_str}")

    run_async(
        start_gateway_server,
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
    )
```

- [ ] **Step 8: Register gateway command in main.py**

Add to `miniautogen/cli/main.py` after the backend import:

```python
from miniautogen.cli.commands.gateway import gateway_group  # noqa: E402

cli.add_command(gateway_group)
```

- [ ] **Step 9: Run gateway tests**

Run: `python -m pytest tests/cli/commands/test_gateway.py tests/cli/services/test_gateway_service.py -v`
Expected: ALL PASS

- [ ] **Step 10: Commit**

```bash
git add miniautogen/cli/commands/gateway.py miniautogen/cli/services/gateway_service.py miniautogen/cli/main.py tests/cli/commands/test_gateway.py tests/cli/services/test_gateway_service.py
git commit -m "feat: add gateway serve command"
```

---

## Task 5: Chat service + `chat` command

**Files:**
- Create: `miniautogen/cli/services/chat_service.py`
- Create: `miniautogen/cli/commands/chat.py`
- Test: `tests/cli/services/test_chat_service.py`
- Test: `tests/cli/commands/test_chat.py`
- Modify: `miniautogen/cli/main.py`

### Review checkpoint after this task.

- [ ] **Step 1: Write failing tests for chat service**

Create `tests/cli/services/test_chat_service.py`:

```python
"""Tests for chat service — single turn and interactive."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from miniautogen.backends.config import BackendConfig, DriverType
from miniautogen.backends.models import (
    AgentEvent,
    BackendCapabilities,
    StartSessionResponse,
)
from miniautogen.backends.resolver import BackendResolver
from miniautogen.cli.services.chat_service import run_single_turn
from miniautogen.core.events.event_sink import InMemoryEventSink


def _make_resolver_with_chat_driver(
    backend_id: str = "test",
    response_text: str = "Hello from backend!",
) -> tuple[BackendResolver, AsyncMock]:
    driver = AsyncMock()
    driver.capabilities = AsyncMock(
        return_value=BackendCapabilities(sessions=True)
    )
    driver.start_session = AsyncMock(
        return_value=StartSessionResponse(
            session_id="sess-1",
            capabilities=BackendCapabilities(sessions=True),
        )
    )
    driver.close_session = AsyncMock()

    async def mock_send_turn(request):
        yield AgentEvent(
            type="message_completed",
            session_id="sess-1",
            payload={"content": response_text},
        )

    driver.send_turn = mock_send_turn

    resolver = BackendResolver()
    config = BackendConfig(
        backend_id=backend_id,
        driver=DriverType.AGENT_API,
        endpoint="http://localhost:8000",
    )
    resolver.add_backend(config)
    resolver._cache[backend_id] = driver
    return resolver, driver


@pytest.mark.anyio
async def test_single_turn_returns_response():
    resolver, driver = _make_resolver_with_chat_driver(
        response_text="42 is the answer"
    )
    sink = InMemoryEventSink()
    result = await run_single_turn(
        resolver=resolver,
        backend_id="test",
        message="What is the meaning of life?",
        event_sink=sink,
    )
    assert result["status"] == "ok"
    assert "42" in result["output_text"]
    assert result["session_id"] == "sess-1"
    driver.start_session.assert_awaited_once()
    driver.close_session.assert_awaited_once()


@pytest.mark.anyio
async def test_single_turn_emits_events():
    resolver, _ = _make_resolver_with_chat_driver()
    sink = InMemoryEventSink()
    await run_single_turn(
        resolver=resolver,
        backend_id="test",
        message="hello",
        event_sink=sink,
    )
    event_types = [e.type for e in sink.events]
    assert "chat_session_started" in event_types
    assert "chat_turn_started" in event_types
    assert "chat_turn_completed" in event_types
    assert "chat_session_closed" in event_types


@pytest.mark.anyio
async def test_single_turn_with_system_prompt():
    resolver, driver = _make_resolver_with_chat_driver()
    sink = InMemoryEventSink()
    await run_single_turn(
        resolver=resolver,
        backend_id="test",
        message="hello",
        system_prompt="Be concise",
        event_sink=sink,
    )
    call_args = driver.start_session.call_args
    assert call_args[0][0].system_prompt == "Be concise"


@pytest.mark.anyio
async def test_single_turn_closes_session_on_error():
    resolver, driver = _make_resolver_with_chat_driver()
    driver.start_session = AsyncMock(
        return_value=StartSessionResponse(
            session_id="sess-err",
            capabilities=BackendCapabilities(),
        )
    )

    async def failing_send(request):
        raise RuntimeError("backend exploded")
        yield  # noqa: unreachable — makes it an async generator

    driver.send_turn = failing_send
    sink = InMemoryEventSink()
    result = await run_single_turn(
        resolver=resolver,
        backend_id="test",
        message="hello",
        event_sink=sink,
    )
    assert result["status"] == "error"
    driver.close_session.assert_awaited_once_with("sess-err")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/cli/services/test_chat_service.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement chat service**

Create `miniautogen/cli/services/chat_service.py`:

```python
"""Chat service for the CLI — single turn and interactive REPL."""
from __future__ import annotations

import uuid
from typing import Any

import anyio
import structlog

from miniautogen.backends.models import SendTurnRequest, StartSessionRequest
from miniautogen.backends.resolver import BackendResolver
from miniautogen.cli.services.operator_input import OperatorInput, StdlibOperatorInput
from miniautogen.cli.services.slash_commands import SlashCommandRegistry, create_default_registry
from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.events.types import EventType

logger = structlog.get_logger()

MAX_TRANSCRIPT_TURNS = 200


async def _emit_async(sink: InMemoryEventSink, event_type: EventType, scope: str, **payload: Any) -> None:
    event = ExecutionEvent(type=event_type.value, scope=scope, payload=payload)
    await sink.publish(event)


async def _collect_response(driver: Any, session_id: str, messages: list[dict[str, Any]]) -> str:
    """Send a turn and collect the full response text."""
    request = SendTurnRequest(session_id=session_id, messages=messages)
    chunks: list[str] = []
    async for event in driver.send_turn(request):
        content = event.payload.get("content", "")
        if content:
            chunks.append(content)
    return "".join(chunks)


async def run_single_turn(
    *,
    resolver: BackendResolver,
    backend_id: str,
    message: str,
    system_prompt: str | None = None,
    model: str | None = None,
    timeout: float | None = None,
    event_sink: InMemoryEventSink | None = None,
) -> dict[str, Any]:
    """Execute a single chat turn (print mode)."""
    sink = event_sink or InMemoryEventSink()
    session_id: str | None = None

    driver = resolver.get_driver(backend_id)

    try:
        req = StartSessionRequest(
            backend_id=backend_id,
            system_prompt=system_prompt,
        )
        resp = await driver.start_session(req)
        session_id = resp.session_id

        await _emit_async(
            sink, EventType.CHAT_SESSION_STARTED, "cli.chat",
            backend_id=backend_id, session_id=session_id, model=model,
        )

        await _emit_async(
            sink, EventType.CHAT_TURN_STARTED, "cli.chat",
            session_id=session_id, turn_index=0,
            message_preview=message[:100],
        )

        messages = [{"role": "user", "content": message}]

        if timeout:
            async with anyio.fail_after(timeout):
                response_text = await _collect_response(driver, session_id, messages)
        else:
            response_text = await _collect_response(driver, session_id, messages)

        await _emit_async(
            sink, EventType.CHAT_TURN_COMPLETED, "cli.chat",
            session_id=session_id, turn_index=0,
            response_length=len(response_text),
        )

        return {
            "status": "ok",
            "backend": backend_id,
            "model": model,
            "output_text": response_text,
            "session_id": session_id,
            "usage": None,
            "error": None,
        }

    except TimeoutError:
        await _emit_async(
            sink, EventType.CHAT_TURN_CANCELLED, "cli.chat",
            session_id=session_id or "", turn_index=0, reason="timeout",
        )
        return {
            "status": "error",
            "backend": backend_id,
            "model": model,
            "output_text": "",
            "session_id": session_id,
            "usage": None,
            "error": "Turn timed out",
        }
    except Exception as exc:
        await _emit_async(
            sink, EventType.CHAT_TURN_FAILED, "cli.chat",
            session_id=session_id or "", turn_index=0, error=str(exc),
        )
        return {
            "status": "error",
            "backend": backend_id,
            "model": model,
            "output_text": "",
            "session_id": session_id,
            "usage": None,
            "error": str(exc),
        }
    finally:
        if session_id:
            try:
                await driver.close_session(session_id)
            except Exception:
                logger.warning("Failed to close session", session_id=session_id)
            await _emit_async(
                sink, EventType.CHAT_SESSION_CLOSED, "cli.chat",
                session_id=session_id, turns_completed=1,
            )


async def run_interactive_chat(
    *,
    resolver: BackendResolver,
    backend_id: str,
    system_prompt: str | None = None,
    model: str | None = None,
    timeout: float | None = None,
    event_sink: InMemoryEventSink | None = None,
    operator_input: OperatorInput | None = None,
    slash_registry: SlashCommandRegistry | None = None,
    output_fn: Any = None,
) -> None:
    """Run an interactive chat REPL."""
    import click

    sink = event_sink or InMemoryEventSink()
    op_input = operator_input or StdlibOperatorInput()
    registry = slash_registry or create_default_registry()
    echo = output_fn or click.echo

    driver = resolver.get_driver(backend_id)
    session_id: str | None = None
    transcript: list[dict[str, Any]] = []
    turn_index = 0

    try:
        req = StartSessionRequest(
            backend_id=backend_id,
            system_prompt=system_prompt,
        )
        resp = await driver.start_session(req)
        session_id = resp.session_id

        await _emit_async(
            sink, EventType.CHAT_SESSION_STARTED, "cli.chat",
            backend_id=backend_id, session_id=session_id, model=model,
        )

        while True:
            line = await op_input.read_line(">>> ")
            if line is None:
                break

            line = line.strip()
            if not line:
                continue

            # Check slash commands
            cmd_result = registry.resolve(line)
            if cmd_result is not None:
                handler, args = cmd_result
                result = await handler(args, None)
                if result == "__exit__":
                    break
                elif result == "__clear__":
                    transcript.clear()
                    echo("Transcript cleared.")
                    continue
                elif result == "__help__":
                    cmds = registry.list_commands()
                    echo("Available commands: " + ", ".join(f"/{c}" for c in cmds))
                    continue
                elif result:
                    echo(result)
                continue

            # Normal message
            await _emit_async(
                sink, EventType.CHAT_TURN_STARTED, "cli.chat",
                session_id=session_id, turn_index=turn_index,
                message_preview=line[:100],
            )

            transcript.append({"role": "user", "content": line})

            # Enforce sliding window
            if len(transcript) > MAX_TRANSCRIPT_TURNS:
                transcript[:] = transcript[-MAX_TRANSCRIPT_TURNS:]

            try:
                if timeout:
                    async with anyio.fail_after(timeout):
                        response_text = await _collect_response(
                            driver, session_id, list(transcript),
                        )
                else:
                    response_text = await _collect_response(
                        driver, session_id, list(transcript),
                    )

                transcript.append({"role": "assistant", "content": response_text})
                echo(response_text)

                await _emit_async(
                    sink, EventType.CHAT_TURN_COMPLETED, "cli.chat",
                    session_id=session_id, turn_index=turn_index,
                    response_length=len(response_text),
                )

            except TimeoutError:
                echo("Turn timed out.")
                await _emit_async(
                    sink, EventType.CHAT_TURN_CANCELLED, "cli.chat",
                    session_id=session_id, turn_index=turn_index,
                    reason="timeout",
                )
            except Exception as exc:
                echo(f"Error: {exc}")
                await _emit_async(
                    sink, EventType.CHAT_TURN_FAILED, "cli.chat",
                    session_id=session_id, turn_index=turn_index,
                    error=str(exc),
                )

            turn_index += 1

    finally:
        if session_id:
            try:
                await driver.close_session(session_id)
            except Exception:
                logger.warning("Failed to close session", session_id=session_id)
            await _emit_async(
                sink, EventType.CHAT_SESSION_CLOSED, "cli.chat",
                session_id=session_id, turns_completed=turn_index,
            )
```

- [ ] **Step 4: Run service tests to verify they pass**

Run: `python -m pytest tests/cli/services/test_chat_service.py -v`
Expected: ALL PASS

- [ ] **Step 5: Write failing tests for chat CLI command**

Create `tests/cli/commands/test_chat.py`:

```python
"""Tests for miniautogen chat command."""
from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from miniautogen.cli.main import cli


@patch("miniautogen.cli.commands.chat.require_project_config")
@patch("miniautogen.cli.commands.chat.build_resolver_from_config")
@patch("miniautogen.cli.commands.chat.run_single_turn", new_callable=AsyncMock)
def test_chat_print_mode(mock_single, mock_resolver, mock_config):
    from miniautogen.cli.config import ProjectConfig, ProjectMeta

    mock_config.return_value = (
        "/tmp",
        ProjectConfig(project=ProjectMeta(name="test")),
    )
    mock_resolver.return_value = AsyncMock()
    mock_single.return_value = {
        "status": "ok",
        "backend": "gemini",
        "model": None,
        "output_text": "Hello world!",
        "session_id": "sess-1",
        "usage": None,
        "error": None,
    }

    runner = CliRunner()
    result = runner.invoke(cli, ["chat", "-b", "gemini", "-p", "hello"])
    assert result.exit_code == 0
    assert "Hello world!" in result.output


@patch("miniautogen.cli.commands.chat.require_project_config")
@patch("miniautogen.cli.commands.chat.build_resolver_from_config")
@patch("miniautogen.cli.commands.chat.run_single_turn", new_callable=AsyncMock)
def test_chat_print_json_mode(mock_single, mock_resolver, mock_config):
    from miniautogen.cli.config import ProjectConfig, ProjectMeta

    mock_config.return_value = (
        "/tmp",
        ProjectConfig(project=ProjectMeta(name="test")),
    )
    mock_resolver.return_value = AsyncMock()
    mock_single.return_value = {
        "status": "ok",
        "backend": "gemini",
        "model": None,
        "output_text": "Hello!",
        "session_id": "sess-1",
        "usage": None,
        "error": None,
    }

    runner = CliRunner()
    result = runner.invoke(cli, ["chat", "-b", "gemini", "-p", "hi", "-o", "json"])
    assert result.exit_code == 0
    assert '"status"' in result.output
    assert '"ok"' in result.output


def test_chat_requires_backend():
    runner = CliRunner()
    result = runner.invoke(cli, ["chat", "-p", "hello"])
    assert result.exit_code != 0


def test_chat_mutual_exclusivity():
    runner = CliRunner()
    result = runner.invoke(cli, [
        "chat", "-b", "x", "-s", "override",
        "--append-system-prompt", "extra",
    ])
    assert result.exit_code != 0
    assert "mutually exclusive" in result.output.lower() or result.exit_code == 2
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `python -m pytest tests/cli/commands/test_chat.py -v`
Expected: FAIL — command not registered yet.

- [ ] **Step 7: Implement chat CLI command**

Create `miniautogen/cli/commands/chat.py`:

```python
"""miniautogen chat command — interactive REPL and print mode."""
from __future__ import annotations

import sys
from pathlib import Path

import click

from miniautogen.cli.config import require_project_config
from miniautogen.cli.errors import BackendNotFoundError, ConfigurationError, TurnTimeoutError
from miniautogen.cli.main import run_async
from miniautogen.cli.output import echo_error, echo_json
from miniautogen.cli.services.chat_service import run_interactive_chat, run_single_turn
from miniautogen.cli.services.resolver_factory import build_resolver_from_config


@click.command("chat")
@click.option("--backend", "-b", required=True, help="Backend ID.")
@click.option("--print", "-p", "print_msg", default=None, type=str, help="Single-shot message.")
@click.option("--system-prompt", "-s", default=None, help="System prompt (replaces base).")
@click.option("--append-system-prompt", default=None, help="Text appended to base system prompt.")
@click.option(
    "--append-system-prompt-file", default=None, type=click.Path(exists=False),
    help="File content appended to base system prompt.",
)
@click.option("--timeout", type=float, default=None, help="Turn timeout in seconds.")
@click.option(
    "--output-format", "-o",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.option("--model", "-m", default=None, help="Model override.")
def chat_command(
    backend: str,
    print_msg: str | None,
    system_prompt: str | None,
    append_system_prompt: str | None,
    append_system_prompt_file: str | None,
    timeout: float | None,
    output_format: str,
    model: str | None,
) -> None:
    """Chat with a backend — interactive REPL or single-shot."""
    # Mutual exclusivity validation
    if system_prompt and (append_system_prompt or append_system_prompt_file):
        raise click.UsageError(
            "--system-prompt and --append-system-prompt/--append-system-prompt-file "
            "are mutually exclusive"
        )

    # Build final system prompt
    final_prompt = system_prompt
    if not system_prompt:
        parts: list[str] = []
        if append_system_prompt:
            parts.append(append_system_prompt)
        if append_system_prompt_file:
            path = Path(append_system_prompt_file)
            if not path.is_file():
                raise ConfigurationError(
                    f"System prompt file not found: {append_system_prompt_file}"
                )
            parts.append(path.read_text())
        if parts:
            final_prompt = "\n".join(parts)

    # TTY detection for pipe mode
    if not sys.stdin.isatty() and print_msg is None:
        print_msg = sys.stdin.read().strip()

    # Resolve config and backend
    _root, config = require_project_config()
    resolver = build_resolver_from_config(config)

    if backend not in resolver.list_backends():
        raise BackendNotFoundError(f"Backend '{backend}' not found in config")

    if print_msg is not None:
        # Single-shot print mode
        result = run_async(
            run_single_turn,
            resolver=resolver,
            backend_id=backend,
            message=print_msg,
            system_prompt=final_prompt,
            model=model,
            timeout=timeout,
        )

        if output_format == "json":
            echo_json(result)
        else:
            if result["status"] == "ok":
                click.echo(result["output_text"])
            else:
                echo_error(result.get("error", "Unknown error"))
                raise SystemExit(1)
    else:
        # Interactive REPL mode
        run_async(
            run_interactive_chat,
            resolver=resolver,
            backend_id=backend,
            system_prompt=final_prompt,
            model=model,
            timeout=timeout,
        )
```

- [ ] **Step 8: Register chat command in main.py**

Add to `miniautogen/cli/main.py` after the gateway import:

```python
from miniautogen.cli.commands.chat import chat_command  # noqa: E402

cli.add_command(chat_command)
```

- [ ] **Step 9: Run all chat tests**

Run: `python -m pytest tests/cli/commands/test_chat.py tests/cli/services/test_chat_service.py -v`
Expected: ALL PASS

- [ ] **Step 10: Commit**

```bash
git add miniautogen/cli/commands/chat.py miniautogen/cli/services/chat_service.py miniautogen/cli/main.py tests/cli/commands/test_chat.py tests/cli/services/test_chat_service.py
git commit -m "feat: add chat command with REPL and print mode"
```

---

## Task 6: Integration verification

**Files:** None new — verification only.

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/ -v --tb=short`
Expected: ALL PASS, no regressions.

- [ ] **Step 2: Verify CLI help shows all new commands**

Run: `python -m miniautogen --help`
Expected output includes: `chat`, `backend`, `gateway` alongside existing `init`, `check`, `run`, `sessions`.

- [ ] **Step 3: Verify subcommand help**

Run: `python -m miniautogen backend --help`
Expected: shows `ping` and `list` subcommands.

Run: `python -m miniautogen gateway --help`
Expected: shows `serve` subcommand.

Run: `python -m miniautogen chat --help`
Expected: shows all flags including `-b`, `-p`, `-s`, `--append-system-prompt`, `--append-system-prompt-file`, `--timeout`, `-o`, `-m`.

- [ ] **Step 4: Commit if any fixes were needed**

```bash
git add -u
git commit -m "fix: integration fixes for terminal harness"
```

Only commit if changes were made. If all tests passed, skip this step.
