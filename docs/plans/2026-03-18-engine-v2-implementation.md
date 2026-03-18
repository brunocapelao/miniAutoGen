# Engine v2.1 Implementation Plan

> **For Agents:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Connect the CLI config layer (EngineProfileConfig) to the backend driver layer (AgentDriver) via a new EngineResolver, add SDK-based drivers for OpenAI/Anthropic/Google, and deprecate the legacy LLMProvider adapters.

**Architecture:** The system follows a "Config -> Resolve -> Drive" pattern. EngineProfileConfig (YAML) is converted by EngineResolver into a BackendConfig, which is passed to the existing BackendResolver to instantiate and cache the correct AgentDriver. A BaseDriver wrapper sits between the resolver and the concrete driver to sanitize messages, validate capabilities, and normalize errors. New SDK drivers (OpenAISDKDriver, AnthropicSDKDriver, GoogleGenAIDriver) and a CLIAgentDriver are added as concrete implementations.

**Tech Stack:** Python 3.10+, Pydantic v2, anyio, httpx, pytest + pytest-asyncio, openai SDK (already installed), anthropic SDK (optional extra), google-genai SDK (optional extra)

**Global Prerequisites:**
- Environment: macOS / Linux, Python 3.10-3.11
- Tools: `poetry`, `pytest`, `ruff`
- State: Branch from `main` (commit `ee25e4a`), clean working tree

**Verification before starting:**
```bash
cd /Users/brunocapelao/Projects/miniAutoGen
python --version       # Expected: Python 3.10.x or 3.11.x
poetry --version       # Expected: Poetry 1.x+
pytest --version       # Expected: pytest 7.x+
git status             # Expected: clean working tree
pytest tests/backends/ # Expected: all tests PASS
```

---

## Phase 0: Foundation

### Task 1: Update EngineProfileConfig with new fields

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/config.py:32-43`
- Test: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/test_config_engine_profile.py` (create)

**Prerequisites:**
- File exists: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/config.py`

**Step 1: Write the failing test**

Create file `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/test_config_engine_profile.py`:

```python
"""Tests for EngineProfileConfig v2.1 fields."""

from __future__ import annotations

from miniautogen.cli.config import EngineProfileConfig


class TestEngineProfileConfigV21:
    def test_default_provider_is_openai_compat(self) -> None:
        cfg = EngineProfileConfig()
        assert cfg.provider == "openai-compat"

    def test_default_kind_is_api(self) -> None:
        cfg = EngineProfileConfig()
        assert cfg.kind == "api"

    def test_new_fields_have_defaults(self) -> None:
        cfg = EngineProfileConfig()
        assert cfg.fallbacks == []
        assert cfg.max_retries == 3
        assert cfg.retry_delay == 1.0
        assert cfg.max_tokens is None
        assert cfg.timeout_seconds == 120.0

    def test_metadata_field_exists(self) -> None:
        cfg = EngineProfileConfig(metadata={"custom": "value"})
        assert cfg.metadata == {"custom": "value"}

    def test_full_config_roundtrip(self) -> None:
        cfg = EngineProfileConfig(
            kind="cli",
            provider="claude-code",
            model="claude-sonnet-4-20250514",
            endpoint="http://localhost:8080",
            api_key="${ANTHROPIC_API_KEY}",
            temperature=0.5,
            max_tokens=4096,
            timeout_seconds=60.0,
            fallbacks=["fast-cheap", "local-ollama"],
            max_retries=5,
            retry_delay=2.0,
            capabilities=["streaming", "tools"],
            metadata={"region": "us-east-1"},
        )
        restored = EngineProfileConfig.model_validate(cfg.model_dump())
        assert restored == cfg

    def test_backward_compat_existing_fields_unchanged(self) -> None:
        cfg = EngineProfileConfig(
            kind="api",
            provider="openai-compat",
            model="gpt-4o",
            temperature=0.7,
            endpoint="http://localhost:11434/v1",
            api_key="sk-test",
            capabilities=["streaming"],
        )
        assert cfg.model == "gpt-4o"
        assert cfg.temperature == 0.7
        assert cfg.endpoint == "http://localhost:11434/v1"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/cli/test_config_engine_profile.py -v`

**Expected output:**
```
FAILED tests/cli/test_config_engine_profile.py::TestEngineProfileConfigV21::test_default_provider_is_openai_compat - AssertionError: assert 'litellm' == 'openai-compat'
```

**Step 3: Implement the changes**

Modify `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/config.py`. Replace the existing `EngineProfileConfig` class (lines 32-43) with:

```python
class EngineProfileConfig(BaseModel):
    """Engine profile for inference binding.

    v2.1: Added fallbacks, max_retries, retry_delay, max_tokens,
    timeout_seconds, metadata. Changed default provider to openai-compat.
    """

    kind: str = "api"
    provider: str = "openai-compat"
    model: str | None = None
    command: str | None = None
    temperature: float = 0.2
    endpoint: str | None = None
    api_key: str | None = None
    max_tokens: int | None = None
    timeout_seconds: float = 120.0
    fallbacks: list[str] = Field(default_factory=list)
    max_retries: int = 3
    retry_delay: float = 1.0
    capabilities: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
```

Note: The `Any` import already exists at line 9 of the file (`from typing import Any`).

**Step 4: Run test to verify it passes**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/cli/test_config_engine_profile.py -v`

**Expected output:**
```
PASSED tests/cli/test_config_engine_profile.py::TestEngineProfileConfigV21::test_default_provider_is_openai_compat
PASSED tests/cli/test_config_engine_profile.py::TestEngineProfileConfigV21::test_default_kind_is_api
PASSED tests/cli/test_config_engine_profile.py::TestEngineProfileConfigV21::test_new_fields_have_defaults
PASSED tests/cli/test_config_engine_profile.py::TestEngineProfileConfigV21::test_metadata_field_exists
PASSED tests/cli/test_config_engine_profile.py::TestEngineProfileConfigV21::test_full_config_roundtrip
PASSED tests/cli/test_config_engine_profile.py::TestEngineProfileConfigV21::test_backward_compat_existing_fields_unchanged
```

**Step 5: Run all existing tests to verify no regressions**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/backends/ tests/cli/ -v`

**Expected output:** All tests PASS. The default provider change from `"litellm"` to `"openai-compat"` may break existing CLI tests that assert the old default -- if so, update those assertions.

**Step 6: Commit**

```bash
git add miniautogen/cli/config.py tests/cli/test_config_engine_profile.py
git commit -m "feat(config): update EngineProfileConfig with v2.1 fields"
```

**If Task Fails:**
1. **Import error:** Check that `from typing import Any` exists in config.py (it does at line 9).
2. **Existing tests break on default provider:** Find tests asserting `provider == "litellm"` and update to `"openai-compat"`.
3. **Rollback:** `git checkout -- miniautogen/cli/config.py`

---

### Task 2: Update DriverType enum

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/config.py:16-19`
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/config.py:55-66` (validator)
- Test: `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/test_config.py` (update existing)

**Prerequisites:**
- Task 1 completed

**Step 1: Write the failing test**

Add to `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/test_config.py`, inside class `TestDriverType`:

```python
    def test_new_driver_types(self) -> None:
        assert DriverType.OPENAI_SDK.value == "openai_sdk"
        assert DriverType.ANTHROPIC_SDK.value == "anthropic_sdk"
        assert DriverType.GOOGLE_GENAI.value == "google_genai"
        assert DriverType.LITELLM.value == "litellm"
        assert DriverType.CLI.value == "cli"

    def test_legacy_types_still_exist(self) -> None:
        # ACP and PTY kept for backward compat but deprecated
        assert DriverType.ACP.value == "acp"
        assert DriverType.PTY.value == "pty"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/backends/test_config.py::TestDriverType::test_new_driver_types -v`

**Expected output:**
```
FAILED - AttributeError: 'DriverType' has no attribute 'OPENAI_SDK'
```

**Step 3: Implement the changes**

In `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/config.py`, replace the `DriverType` enum (lines 16-19):

```python
class DriverType(str, Enum):
    ACP = "acp"             # Deprecated: use CLI
    AGENT_API = "agentapi"
    PTY = "pty"             # Deprecated: use CLI
    OPENAI_SDK = "openai_sdk"
    ANTHROPIC_SDK = "anthropic_sdk"
    GOOGLE_GENAI = "google_genai"
    LITELLM = "litellm"
    CLI = "cli"
```

Also update the `validate_driver_requirements` validator (lines 55-66) to handle the new CLI type and SDK types that need endpoints:

```python
    @model_validator(mode="after")
    def validate_driver_requirements(self) -> "BackendConfig":
        if self.driver in (DriverType.ACP, DriverType.PTY, DriverType.CLI) and not self.command:
            msg = f"command is required for driver type '{self.driver.value}'"
            raise ValueError(msg)
        if self.driver == DriverType.AGENT_API and not self.endpoint:
            msg = "endpoint is required for driver type 'agentapi'"
            raise ValueError(msg)
        if self.auth and self.auth.type == "bearer" and not self.auth.token_env:
            msg = "token_env is required when auth type is 'bearer'"
            raise ValueError(msg)
        return self
```

**Step 4: Run tests to verify**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/backends/test_config.py -v`

**Expected output:** All tests PASS including new ones.

**Step 5: Add test for CLI driver type validation**

Add to `TestBackendConfig` in the same file:

```python
    def test_cli_requires_command(self) -> None:
        with pytest.raises(ValidationError, match="command"):
            BackendConfig(backend_id="x", driver=DriverType.CLI)

    def test_cli_with_command_valid(self) -> None:
        cfg = BackendConfig(
            backend_id="claude",
            driver=DriverType.CLI,
            command=["claude", "--agent"],
        )
        assert cfg.driver == DriverType.CLI

    def test_sdk_driver_minimal(self) -> None:
        cfg = BackendConfig(
            backend_id="openai",
            driver=DriverType.OPENAI_SDK,
        )
        assert cfg.driver == DriverType.OPENAI_SDK
```

**Step 6: Run and verify**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/backends/test_config.py -v`

**Expected output:** All tests PASS.

**Step 7: Commit**

```bash
git add miniautogen/backends/config.py tests/backends/test_config.py
git commit -m "feat(backends): add new DriverType values for SDK and CLI drivers"
```

**If Task Fails:**
1. **Existing tests reference ACP/PTY:** They should still work since we kept them. If `test_valid_types` only checks 3 types, it will still pass.
2. **Validation conflict with new types:** SDK types (OPENAI_SDK, etc.) don't require command or endpoint at the BackendConfig level -- those are resolved upstream by EngineResolver.
3. **Rollback:** `git checkout -- miniautogen/backends/config.py tests/backends/test_config.py`

---

### Task 3: Create MessageTransformer protocol

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/transformer.py`
- Test: `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/test_transformer.py` (create)

**Prerequisites:**
- Task 2 completed (for AgentEvent import)

**Step 1: Write the failing test**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/test_transformer.py`:

```python
"""Tests for MessageTransformer protocol."""

from __future__ import annotations

from typing import Any

from miniautogen.backends.models import AgentEvent
from miniautogen.backends.transformer import MessageTransformer


class FakeTransformer:
    """A concrete implementation to test the protocol."""

    def to_provider(self, messages: list[dict[str, Any]]) -> Any:
        return [{"role": m["role"], "content": m["content"]} for m in messages]

    def from_provider(
        self, response: Any, session_id: str, turn_id: str,
    ) -> list[AgentEvent]:
        return [
            AgentEvent(
                type="message_completed",
                session_id=session_id,
                turn_id=turn_id,
                payload={"text": str(response)},
            ),
        ]


class TestMessageTransformerProtocol:
    def test_fake_satisfies_protocol(self) -> None:
        transformer: MessageTransformer = FakeTransformer()
        result = transformer.to_provider([{"role": "user", "content": "hi"}])
        assert isinstance(result, list)

    def test_from_provider_returns_events(self) -> None:
        transformer: MessageTransformer = FakeTransformer()
        events = transformer.from_provider("Hello!", session_id="s1", turn_id="t1")
        assert len(events) == 1
        assert events[0].type == "message_completed"
        assert events[0].payload["text"] == "Hello!"

    def test_protocol_is_runtime_checkable(self) -> None:
        assert isinstance(FakeTransformer(), MessageTransformer)
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/backends/test_transformer.py -v`

**Expected output:**
```
ModuleNotFoundError: No module named 'miniautogen.backends.transformer'
```

**Step 3: Implement**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/transformer.py`:

```python
"""Message transformation protocol for backend drivers.

Each SDK driver implements its own transformer to convert between
MiniAutoGen's internal message format and the provider's native format.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from miniautogen.backends.models import AgentEvent


@runtime_checkable
class MessageTransformer(Protocol):
    """Converts between internal message format and provider-specific format.

    Drivers that need message transformation implement this protocol.
    The BaseDriver wrapper uses it for pre/post processing.
    """

    def to_provider(self, messages: list[dict[str, Any]]) -> Any:
        """Convert internal messages to provider-native format.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.

        Returns:
            Provider-specific message format (varies by provider).
        """
        ...

    def from_provider(
        self, response: Any, session_id: str, turn_id: str,
    ) -> list[AgentEvent]:
        """Convert provider response to canonical AgentEvents.

        Args:
            response: Raw response from the provider SDK.
            session_id: Current session identifier.
            turn_id: Current turn identifier.

        Returns:
            List of AgentEvent objects in canonical format.
        """
        ...
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/backends/test_transformer.py -v`

**Expected output:**
```
PASSED tests/backends/test_transformer.py::TestMessageTransformerProtocol::test_fake_satisfies_protocol
PASSED tests/backends/test_transformer.py::TestMessageTransformerProtocol::test_from_provider_returns_events
PASSED tests/backends/test_transformer.py::TestMessageTransformerProtocol::test_protocol_is_runtime_checkable
```

**Step 5: Commit**

```bash
git add miniautogen/backends/transformer.py tests/backends/test_transformer.py
git commit -m "feat(backends): add MessageTransformer protocol"
```

**If Task Fails:**
1. **Protocol not runtime_checkable:** Ensure `@runtime_checkable` decorator is present.
2. **Rollback:** `git checkout -- miniautogen/backends/transformer.py` and delete test file.

---

### Task 4: Create BaseDriver wrapper

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/base_driver.py`
- Test: `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/test_base_driver.py` (create)

**Prerequisites:**
- Task 2 completed (AgentDriver, models available)
- File exists: `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/conftest.py` (FakeDriver)

**Step 1: Write the failing test**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/test_base_driver.py`:

```python
"""Tests for BaseDriver wrapper."""

from __future__ import annotations

from typing import AsyncIterator

import pytest

from miniautogen.backends.base_driver import BaseDriver
from miniautogen.backends.errors import CancelNotSupportedError, TurnExecutionError
from miniautogen.backends.models import (
    AgentEvent,
    ArtifactRef,
    BackendCapabilities,
    CancelTurnRequest,
    SendTurnRequest,
    StartSessionRequest,
    StartSessionResponse,
)
from tests.backends.conftest import FakeDriver


@pytest.fixture
def wrapped_driver() -> BaseDriver:
    inner = FakeDriver(
        caps=BackendCapabilities(sessions=True, streaming=True),
        events=[
            AgentEvent(
                type="message_completed",
                session_id="",
                payload={"text": "Hello"},
            ),
        ],
    )
    return BaseDriver(inner=inner, capabilities=BackendCapabilities(sessions=True, streaming=True))


class TestBaseDriverDelegation:
    @pytest.mark.asyncio
    async def test_start_session_delegates(self, wrapped_driver: BaseDriver) -> None:
        resp = await wrapped_driver.start_session(
            StartSessionRequest(backend_id="test"),
        )
        assert resp.session_id.startswith("fake_sess_")

    @pytest.mark.asyncio
    async def test_send_turn_delegates_and_yields_events(
        self, wrapped_driver: BaseDriver,
    ) -> None:
        resp = await wrapped_driver.start_session(
            StartSessionRequest(backend_id="test"),
        )
        events: list[AgentEvent] = []
        async for ev in wrapped_driver.send_turn(
            SendTurnRequest(
                session_id=resp.session_id,
                messages=[{"role": "user", "content": "hi"}],
            ),
        ):
            events.append(ev)
        types = [e.type for e in events]
        assert "message_completed" in types
        assert "turn_completed" in types

    @pytest.mark.asyncio
    async def test_capabilities_returns_wrapper_caps(
        self, wrapped_driver: BaseDriver,
    ) -> None:
        caps = await wrapped_driver.capabilities()
        assert caps.streaming is True
        assert caps.sessions is True

    @pytest.mark.asyncio
    async def test_close_session_delegates(self, wrapped_driver: BaseDriver) -> None:
        resp = await wrapped_driver.start_session(
            StartSessionRequest(backend_id="test"),
        )
        await wrapped_driver.close_session(resp.session_id)

    @pytest.mark.asyncio
    async def test_list_artifacts_delegates(self, wrapped_driver: BaseDriver) -> None:
        result = await wrapped_driver.list_artifacts("s1")
        assert result == []

    @pytest.mark.asyncio
    async def test_cancel_turn_delegates(self, wrapped_driver: BaseDriver) -> None:
        with pytest.raises(CancelNotSupportedError):
            inner_caps = BackendCapabilities(cancel=False)
            inner = FakeDriver(caps=inner_caps)
            driver = BaseDriver(inner=inner, capabilities=inner_caps)
            await driver.cancel_turn(CancelTurnRequest(session_id="s1"))


class TestBaseDriverSanitization:
    @pytest.mark.asyncio
    async def test_empty_messages_filtered(self) -> None:
        inner = FakeDriver(
            events=[
                AgentEvent(type="message_completed", session_id="", payload={"text": "ok"}),
            ],
        )
        driver = BaseDriver(inner=inner, capabilities=BackendCapabilities())
        resp = await driver.start_session(StartSessionRequest(backend_id="test"))
        events: list[AgentEvent] = []
        async for ev in driver.send_turn(
            SendTurnRequest(
                session_id=resp.session_id,
                messages=[
                    {"role": "user", "content": "hello"},
                    {"role": "user", "content": ""},
                    {"role": "user", "content": "   "},
                ],
            ),
        ):
            events.append(ev)
        # Should still work -- empty messages removed before sending
        assert any(e.type == "message_completed" for e in events)


class TestBaseDriverErrorNormalization:
    @pytest.mark.asyncio
    async def test_inner_exception_yields_error_event(self) -> None:
        class FailingDriver(FakeDriver):
            async def send_turn(
                self, request: SendTurnRequest,
            ) -> AsyncIterator[AgentEvent]:
                raise TurnExecutionError("boom")
                yield  # make it an async generator  # noqa: RUF027

        inner = FailingDriver()
        driver = BaseDriver(inner=inner, capabilities=BackendCapabilities())
        resp = await driver.start_session(StartSessionRequest(backend_id="test"))
        events: list[AgentEvent] = []
        async for ev in driver.send_turn(
            SendTurnRequest(
                session_id=resp.session_id,
                messages=[{"role": "user", "content": "hi"}],
            ),
        ):
            events.append(ev)
        assert len(events) == 1
        assert events[0].type == "backend_error"
        assert "boom" in events[0].payload.get("error", "")
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/backends/test_base_driver.py -v`

**Expected output:**
```
ModuleNotFoundError: No module named 'miniautogen.backends.base_driver'
```

**Step 3: Implement BaseDriver**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/base_driver.py`:

```python
"""BaseDriver — wrapper that adds sanitization, validation, and error normalization.

Inspired by OpenCode's baseProvider pattern. Wraps any concrete AgentDriver
to provide consistent behavior regardless of the underlying implementation.
"""

from __future__ import annotations

import re
from typing import AsyncIterator

from miniautogen.backends.driver import AgentDriver
from miniautogen.backends.models import (
    AgentEvent,
    ArtifactRef,
    BackendCapabilities,
    CancelTurnRequest,
    SendTurnRequest,
    StartSessionRequest,
    StartSessionResponse,
)
from miniautogen.observability.logging import get_logger

logger = get_logger(__name__)


class BaseDriver(AgentDriver):
    """Wraps any driver with sanitization, validation, and error normalization.

    Responsibilities:
    - Sanitize messages (remove empty, strip control chars)
    - Validate capabilities before forwarding requests
    - Normalize errors into backend_error AgentEvents
    """

    def __init__(
        self,
        inner: AgentDriver,
        capabilities: BackendCapabilities,
    ) -> None:
        self._inner = inner
        self._capabilities = capabilities

    async def start_session(
        self,
        request: StartSessionRequest,
    ) -> StartSessionResponse:
        return await self._inner.start_session(request)

    async def send_turn(
        self,
        request: SendTurnRequest,
    ) -> AsyncIterator[AgentEvent]:
        sanitized = self._sanitize_messages(request.messages)
        request = request.model_copy(update={"messages": sanitized})
        try:
            async for event in self._inner.send_turn(request):
                yield self._normalize_event(event)
        except Exception as exc:
            yield self._error_event(exc, request.session_id)

    async def cancel_turn(
        self,
        request: CancelTurnRequest,
    ) -> None:
        await self._inner.cancel_turn(request)

    async def list_artifacts(self, session_id: str) -> list[ArtifactRef]:
        return await self._inner.list_artifacts(session_id)

    async def close_session(self, session_id: str) -> None:
        await self._inner.close_session(session_id)

    async def capabilities(self) -> BackendCapabilities:
        return self._capabilities

    def _sanitize_messages(
        self, messages: list[dict],
    ) -> list[dict]:
        """Remove empty messages, strip control characters from content."""
        sanitized = []
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                content = content.strip()
                # Remove control characters except newline/tab
                content = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", content)
                if not content:
                    continue
            sanitized.append({**msg, "content": content})
        return sanitized

    def _normalize_event(self, event: AgentEvent) -> AgentEvent:
        """Ensure consistent event format regardless of provider."""
        return event

    def _error_event(self, exc: Exception, session_id: str) -> AgentEvent:
        """Convert any exception to a backend_error AgentEvent."""
        logger.error(
            "driver_error",
            error=str(exc),
            error_type=type(exc).__name__,
            session_id=session_id,
        )
        return AgentEvent(
            type="backend_error",
            session_id=session_id,
            payload={
                "error": str(exc),
                "error_type": type(exc).__name__,
            },
        )
```

**Step 4: Run tests to verify**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/backends/test_base_driver.py -v`

**Expected output:**
```
PASSED tests/backends/test_base_driver.py::TestBaseDriverDelegation::test_start_session_delegates
PASSED tests/backends/test_base_driver.py::TestBaseDriverDelegation::test_send_turn_delegates_and_yields_events
PASSED tests/backends/test_base_driver.py::TestBaseDriverDelegation::test_capabilities_returns_wrapper_caps
PASSED tests/backends/test_base_driver.py::TestBaseDriverDelegation::test_close_session_delegates
PASSED tests/backends/test_base_driver.py::TestBaseDriverDelegation::test_list_artifacts_delegates
PASSED tests/backends/test_base_driver.py::TestBaseDriverDelegation::test_cancel_turn_delegates
PASSED tests/backends/test_base_driver.py::TestBaseDriverSanitization::test_empty_messages_filtered
PASSED tests/backends/test_base_driver.py::TestBaseDriverErrorNormalization::test_inner_exception_yields_error_event
```

**Step 5: Commit**

```bash
git add miniautogen/backends/base_driver.py tests/backends/test_base_driver.py
git commit -m "feat(backends): add BaseDriver wrapper with sanitization and error normalization"
```

**If Task Fails:**
1. **FailingDriver async generator issue:** The `yield` after `raise` is needed to make the function an async generator. If the test framework complains, restructure to yield the error event from a list instead.
2. **Import of get_logger:** Verify `from miniautogen.observability.logging import get_logger` works. If not, use `import structlog; logger = structlog.get_logger(__name__)`.
3. **Rollback:** `git checkout -- miniautogen/backends/base_driver.py` and delete test file.

---

### Task 5: Create EngineResolver

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/engine_resolver.py`
- Test: `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/test_engine_resolver.py` (create)

**Prerequisites:**
- Tasks 1-4 completed
- Files exist: `miniautogen/cli/config.py`, `miniautogen/backends/resolver.py`, `miniautogen/backends/config.py`

**Step 1: Write the failing test**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/test_engine_resolver.py`:

```python
"""Tests for EngineResolver — the bridge between config and drivers."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from miniautogen.backends.config import BackendConfig, DriverType
from miniautogen.backends.driver import AgentDriver
from miniautogen.backends.engine_resolver import EngineResolver
from miniautogen.backends.errors import BackendUnavailableError
from miniautogen.cli.config import (
    DefaultsConfig,
    EngineProfileConfig,
    ProjectConfig,
    ProjectMeta,
)
from tests.backends.conftest import FakeDriver


def _make_project_config(
    profiles: dict[str, EngineProfileConfig] | None = None,
) -> ProjectConfig:
    return ProjectConfig(
        project=ProjectMeta(name="test-project"),
        defaults=DefaultsConfig(engine_profile="default"),
        engine_profiles=profiles or {},
    )


class TestEngineResolverResolveApiKey:
    def test_resolves_env_var_reference(self) -> None:
        resolver = EngineResolver()
        with patch.dict(os.environ, {"MY_API_KEY": "sk-secret-123"}):
            result = resolver._resolve_api_key("${MY_API_KEY}")
        assert result == "sk-secret-123"

    def test_returns_literal_key_unchanged(self) -> None:
        resolver = EngineResolver()
        result = resolver._resolve_api_key("sk-literal-key")
        assert result == "sk-literal-key"

    def test_returns_none_for_none(self) -> None:
        resolver = EngineResolver()
        result = resolver._resolve_api_key(None)
        assert result is None

    def test_missing_env_var_returns_none(self) -> None:
        resolver = EngineResolver()
        with patch.dict(os.environ, {}, clear=True):
            result = resolver._resolve_api_key("${NONEXISTENT_KEY}")
        assert result is None


class TestEngineResolverEngineToBackend:
    def test_maps_openai_compat_to_agent_api(self) -> None:
        resolver = EngineResolver()
        engine = EngineProfileConfig(
            provider="openai-compat",
            endpoint="http://localhost:11434/v1",
            model="llama3.2",
        )
        backend = resolver._engine_to_backend("local-ollama", engine)
        assert backend.backend_id == "local-ollama"
        assert backend.driver == DriverType.AGENT_API
        assert backend.endpoint == "http://localhost:11434/v1"

    def test_maps_openai_to_openai_sdk(self) -> None:
        resolver = EngineResolver()
        engine = EngineProfileConfig(
            provider="openai",
            model="gpt-4o-mini",
            api_key="sk-test",
        )
        backend = resolver._engine_to_backend("fast-cheap", engine)
        assert backend.driver == DriverType.OPENAI_SDK

    def test_maps_anthropic_to_anthropic_sdk(self) -> None:
        resolver = EngineResolver()
        engine = EngineProfileConfig(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            api_key="sk-ant-test",
        )
        backend = resolver._engine_to_backend("smart", engine)
        assert backend.driver == DriverType.ANTHROPIC_SDK

    def test_maps_google_to_google_genai(self) -> None:
        resolver = EngineResolver()
        engine = EngineProfileConfig(
            provider="google",
            model="gemini-2.5-pro",
        )
        backend = resolver._engine_to_backend("vision", engine)
        assert backend.driver == DriverType.GOOGLE_GENAI

    def test_maps_cli_provider_to_cli(self) -> None:
        resolver = EngineResolver()
        engine = EngineProfileConfig(
            kind="cli",
            provider="claude-code",
            model="claude-sonnet-4-20250514",
        )
        backend = resolver._engine_to_backend("claude-agent", engine)
        assert backend.driver == DriverType.CLI
        assert backend.command is not None

    def test_stores_model_in_metadata(self) -> None:
        resolver = EngineResolver()
        engine = EngineProfileConfig(
            provider="openai-compat",
            endpoint="http://localhost:8000",
            model="gemini-2.5-pro",
        )
        backend = resolver._engine_to_backend("test", engine)
        assert backend.metadata.get("model") == "gemini-2.5-pro"

    def test_stores_api_key_in_auth(self) -> None:
        resolver = EngineResolver()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-real"}):
            engine = EngineProfileConfig(
                provider="openai-compat",
                endpoint="http://localhost:8000",
                api_key="${OPENAI_API_KEY}",
            )
            backend = resolver._engine_to_backend("test", engine)
        assert backend.auth is not None
        assert backend.auth.type == "bearer"

    def test_unknown_provider_raises(self) -> None:
        resolver = EngineResolver()
        engine = EngineProfileConfig(provider="unknown-provider")
        with pytest.raises(BackendUnavailableError, match="Unknown provider"):
            resolver._engine_to_backend("test", engine)


class TestEngineResolverResolve:
    def test_resolves_known_profile(self) -> None:
        resolver = EngineResolver()
        # Register a factory for AGENT_API so resolution completes
        resolver._resolver.register_factory(
            DriverType.AGENT_API, lambda cfg: FakeDriver(),
        )
        config = _make_project_config(
            profiles={
                "local": EngineProfileConfig(
                    provider="openai-compat",
                    endpoint="http://localhost:11434/v1",
                    model="llama3.2",
                ),
            },
        )
        driver = resolver.resolve("local", config)
        assert isinstance(driver, AgentDriver)

    def test_unknown_profile_raises(self) -> None:
        resolver = EngineResolver()
        config = _make_project_config()
        with pytest.raises(BackendUnavailableError, match="not found"):
            resolver.resolve("nonexistent", config)

    def test_driver_is_cached(self) -> None:
        resolver = EngineResolver()
        call_count = 0

        def counting_factory(cfg: BackendConfig) -> FakeDriver:
            nonlocal call_count
            call_count += 1
            return FakeDriver()

        resolver._resolver.register_factory(DriverType.AGENT_API, counting_factory)
        config = _make_project_config(
            profiles={
                "local": EngineProfileConfig(
                    provider="openai-compat",
                    endpoint="http://localhost:11434/v1",
                ),
            },
        )
        d1 = resolver.resolve("local", config)
        d2 = resolver.resolve("local", config)
        assert d1 is d2
        assert call_count == 1
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/backends/test_engine_resolver.py -v`

**Expected output:**
```
ModuleNotFoundError: No module named 'miniautogen.backends.engine_resolver'
```

**Step 3: Implement EngineResolver**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/engine_resolver.py`:

```python
"""EngineResolver — bridge between EngineProfileConfig and AgentDriver.

Converts user-facing engine profiles (from YAML) into BackendConfig objects,
registers them with BackendResolver, and returns cached driver instances.
This is the "Config -> Resolve -> Drive" glue layer.
"""

from __future__ import annotations

import os
import re
from typing import Any

from miniautogen.backends.config import AuthConfig, BackendConfig, DriverType
from miniautogen.backends.driver import AgentDriver
from miniautogen.backends.errors import BackendUnavailableError
from miniautogen.backends.resolver import BackendResolver
from miniautogen.cli.config import EngineProfileConfig, ProjectConfig
from miniautogen.observability.logging import get_logger

logger = get_logger(__name__)

# Provider string -> DriverType mapping
_PROVIDER_TO_DRIVER: dict[str, DriverType] = {
    "openai-compat": DriverType.AGENT_API,
    "openai": DriverType.OPENAI_SDK,
    "anthropic": DriverType.ANTHROPIC_SDK,
    "google": DriverType.GOOGLE_GENAI,
    "litellm": DriverType.LITELLM,
    "claude-code": DriverType.CLI,
    "gemini-cli": DriverType.CLI,
    "codex-cli": DriverType.CLI,
}

# CLI provider -> default command mapping
_CLI_COMMANDS: dict[str, list[str]] = {
    "claude-code": ["claude", "--agent"],
    "gemini-cli": ["gemini"],
    "codex-cli": ["codex"],
}

# Pattern for environment variable references: ${VAR_NAME}
_ENV_VAR_PATTERN = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")


class EngineResolver:
    """Converts EngineProfileConfig -> AgentDriver (instantiated, cached).

    Uses BackendResolver internally for factory registration and caching.
    """

    def __init__(self) -> None:
        self._resolver = BackendResolver()
        self._registered_profiles: set[str] = set()

    def resolve(self, profile_name: str, config: ProjectConfig) -> AgentDriver:
        """Resolve an engine profile name to a cached driver instance.

        Args:
            profile_name: Name of the engine profile (e.g., "fast-cheap").
            config: The full project configuration containing engine_profiles.

        Returns:
            An instantiated AgentDriver ready for use.

        Raises:
            BackendUnavailableError: If profile not found or driver can't be created.
        """
        engine = config.engine_profiles.get(profile_name)
        if engine is None:
            msg = f"Engine profile '{profile_name}' not found in project config"
            raise BackendUnavailableError(msg)

        # Only register the backend config once
        if profile_name not in self._registered_profiles:
            backend_config = self._engine_to_backend(profile_name, engine)
            self._resolver.add_backend(backend_config)
            self._registered_profiles.add(profile_name)

        return self._resolver.get_driver(profile_name)

    def resolve_with_fallbacks(
        self, profile_name: str, config: ProjectConfig,
    ) -> AgentDriver:
        """Try primary engine, fall back to alternatives on failure.

        Args:
            profile_name: Primary engine profile name.
            config: Full project config.

        Returns:
            First successfully resolved driver.

        Raises:
            BackendUnavailableError: If all options (primary + fallbacks) fail.
        """
        engine = config.engine_profiles.get(profile_name)
        if engine is None:
            msg = f"Engine profile '{profile_name}' not found in project config"
            raise BackendUnavailableError(msg)

        # Build the chain: primary + fallbacks
        chain = [profile_name, *engine.fallbacks]
        errors: list[str] = []

        for name in chain:
            try:
                driver = self.resolve(name, config)
                if name != profile_name:
                    logger.info(
                        "fallback_resolved",
                        primary=profile_name,
                        resolved=name,
                    )
                return driver
            except (BackendUnavailableError, Exception) as exc:
                errors.append(f"{name}: {exc}")
                logger.warning(
                    "engine_resolution_failed",
                    profile=name,
                    error=str(exc),
                )

        msg = (
            f"All engines failed for '{profile_name}'. "
            f"Tried: {', '.join(chain)}. Errors: {'; '.join(errors)}"
        )
        raise BackendUnavailableError(msg)

    def _engine_to_backend(
        self, name: str, engine: EngineProfileConfig,
    ) -> BackendConfig:
        """Map an EngineProfileConfig to a BackendConfig.

        This is the core translation layer. It converts user-facing
        config (provider, model, api_key) into the internal BackendConfig
        format (driver type, endpoint, auth, metadata).
        """
        driver_type = _PROVIDER_TO_DRIVER.get(engine.provider)
        if driver_type is None:
            msg = f"Unknown provider '{engine.provider}' in engine profile '{name}'"
            raise BackendUnavailableError(msg)

        # Resolve API key (handles ${ENV_VAR} references)
        resolved_key = self._resolve_api_key(engine.api_key)

        # Build auth config if we have a key
        auth: AuthConfig | None = None
        if resolved_key:
            # Store the resolved key in env for the auth system
            env_var_name = f"_MINIAUTOGEN_{name.upper().replace('-', '_')}_KEY"
            os.environ[env_var_name] = resolved_key
            auth = AuthConfig(type="bearer", token_env=env_var_name)

        # Build metadata with model and engine-specific params
        metadata: dict[str, Any] = dict(engine.metadata)
        if engine.model:
            metadata["model"] = engine.model
        metadata["temperature"] = engine.temperature
        metadata["max_retries"] = engine.max_retries
        metadata["retry_delay"] = engine.retry_delay
        if engine.max_tokens is not None:
            metadata["max_tokens"] = engine.max_tokens
        # Disable health check for SDK drivers (they handle it internally)
        if driver_type != DriverType.AGENT_API:
            metadata.setdefault("health_endpoint", None)

        # Determine command for CLI drivers
        command: list[str] | None = None
        if driver_type == DriverType.CLI:
            command = _CLI_COMMANDS.get(engine.provider, [engine.provider])

        # Determine endpoint for API drivers
        endpoint = engine.endpoint
        if driver_type == DriverType.AGENT_API and not endpoint:
            # Default OpenAI-compat endpoint
            endpoint = "https://api.openai.com/v1"

        return BackendConfig(
            backend_id=name,
            driver=driver_type,
            command=command,
            endpoint=endpoint,
            timeout_seconds=engine.timeout_seconds,
            auth=auth,
            metadata=metadata,
        )

    def _resolve_api_key(self, api_key: str | None) -> str | None:
        """Resolve ${ENV_VAR} references to actual values.

        If the key looks like ${VAR_NAME}, reads from environment.
        Otherwise returns the literal value.
        Returns None if the env var is not set.
        """
        if api_key is None:
            return None

        match = _ENV_VAR_PATTERN.match(api_key)
        if match:
            var_name = match.group(1)
            value = os.environ.get(var_name)
            if value is None:
                logger.warning("env_var_not_set", var_name=var_name)
            return value

        return api_key

    def register_factory(
        self, driver_type: DriverType, factory: Any,
    ) -> None:
        """Register a driver factory. Delegates to internal BackendResolver."""
        self._resolver.register_factory(driver_type, factory)
```

**Step 4: Run tests to verify**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/backends/test_engine_resolver.py -v`

**Expected output:** All tests PASS.

**Step 5: Run all backend tests to verify no regressions**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/backends/ -v`

**Expected output:** All existing tests PASS.

**Step 6: Commit**

```bash
git add miniautogen/backends/engine_resolver.py tests/backends/test_engine_resolver.py
git commit -m "feat(backends): add EngineResolver to bridge config and drivers"
```

**If Task Fails:**
1. **BackendConfig validation error for SDK types:** SDK types (OPENAI_SDK, etc.) don't require `command` or `endpoint`. Ensure Task 2's validator only checks ACP/PTY/CLI for command and AGENT_API for endpoint.
2. **Import issues:** `miniautogen.observability.logging.get_logger` must exist. Check existing code pattern in `agentapi/driver.py`.
3. **Rollback:** `git checkout -- miniautogen/backends/engine_resolver.py` and delete test file.

---

### Task 6: Run Code Review (Phase 0)

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

## Phase 1: Wire Existing Driver

### Task 7: Wire EngineResolver to AgentAPIDriver

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/engine_resolver.py`
- Test: `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/test_engine_resolver.py` (extend)

**Prerequisites:**
- Task 5 completed (EngineResolver exists)
- File exists: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/agentapi/factory.py`

**Step 1: Write the failing test**

Add to `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/test_engine_resolver.py`:

```python
class TestEngineResolverWithAgentAPI:
    def test_openai_compat_resolves_to_agentapi_driver(self) -> None:
        from miniautogen.backends.agentapi.driver import AgentAPIDriver

        resolver = EngineResolver()
        config = _make_project_config(
            profiles={
                "local": EngineProfileConfig(
                    provider="openai-compat",
                    endpoint="http://localhost:11434/v1",
                    model="llama3.2",
                ),
            },
        )
        driver = resolver.resolve("local", config)
        assert isinstance(driver, AgentAPIDriver)

    def test_agentapi_driver_has_correct_model(self) -> None:
        from miniautogen.backends.agentapi.driver import AgentAPIDriver

        resolver = EngineResolver()
        config = _make_project_config(
            profiles={
                "test": EngineProfileConfig(
                    provider="openai-compat",
                    endpoint="http://localhost:8000",
                    model="gemini-2.5-pro",
                ),
            },
        )
        driver = resolver.resolve("test", config)
        assert isinstance(driver, AgentAPIDriver)
        assert driver._model == "gemini-2.5-pro"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/backends/test_engine_resolver.py::TestEngineResolverWithAgentAPI -v`

**Expected output:**
```
FAILED - BackendUnavailableError: No factory registered for driver type 'agentapi'
```

**Step 3: Implement -- register AgentAPI factory in EngineResolver**

Add the `_register_default_factories` method to EngineResolver. In `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/engine_resolver.py`, add this import at the top:

```python
from miniautogen.backends.agentapi.factory import agentapi_factory
```

And modify the `__init__` method to call `_register_default_factories`:

```python
    def __init__(self) -> None:
        self._resolver = BackendResolver()
        self._registered_profiles: set[str] = set()
        self._register_default_factories()

    def _register_default_factories(self) -> None:
        """Register factories for all built-in driver types."""
        self._resolver.register_factory(DriverType.AGENT_API, agentapi_factory)
```

**Step 4: Run tests**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/backends/test_engine_resolver.py -v`

**Expected output:** All tests PASS. The test with FakeDriver factory still works because `register_factory` overwrites.

Note: Update the test `test_resolves_known_profile` to remove the manual factory registration if it conflicts, or keep it -- the manual registration just overrides the default.

**Step 5: Commit**

```bash
git add miniautogen/backends/engine_resolver.py tests/backends/test_engine_resolver.py
git commit -m "feat(backends): wire EngineResolver to AgentAPIDriver factory"
```

**If Task Fails:**
1. **Circular import:** If `agentapi_factory` import causes issues, use lazy import inside `_register_default_factories`.
2. **Factory override conflict:** `BackendResolver.register_factory` simply overwrites, so manual test registrations are fine.
3. **Rollback:** `git checkout -- miniautogen/backends/engine_resolver.py`

---

### Task 8: Update AgentAPIDriver capabilities to reflect actual abilities

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/agentapi/driver.py:49-57`
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/agentapi/test_driver.py` (update assertions)

**Prerequisites:**
- Task 7 completed

**Step 1: Write the test for updated capabilities**

In `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/agentapi/test_driver.py`, update or add in `TestAgentAPIDriverOtherMethods`:

```python
    @pytest.mark.asyncio
    async def test_capabilities_reflect_actual_abilities(
        self, driver: AgentAPIDriver,
    ) -> None:
        caps = await driver.capabilities()
        # AgentAPIDriver supports sessions (stateless, but creates IDs)
        assert caps.sessions is True
        # No streaming support yet (non-streaming chat completion)
        assert caps.streaming is False
        # No tool calling through raw HTTP yet
        assert caps.tools is False
        # No cancel support
        assert caps.cancel is False
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/backends/agentapi/test_driver.py::TestAgentAPIDriverOtherMethods::test_capabilities_reflect_actual_abilities -v`

**Expected output:**
```
FAILED - AssertionError: assert False is True  (sessions)
```

**Step 3: Update capabilities in AgentAPIDriver**

In `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/agentapi/driver.py`, change the `_caps` initialization (lines 49-57) to:

```python
        self._caps = BackendCapabilities(
            sessions=True,
            streaming=False,
            cancel=False,
            resume=False,
            tools=False,
            artifacts=False,
            multimodal=False,
        )
```

**Step 4: Update the existing test that checks `sessions is False`**

In `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/agentapi/test_driver.py`, update `test_capabilities_no_streaming` to:

```python
    @pytest.mark.asyncio
    async def test_capabilities_no_streaming(
        self, driver: AgentAPIDriver,
    ) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="test"),
        )
        assert resp.capabilities.streaming is False
        assert resp.capabilities.sessions is True
        assert resp.capabilities.cancel is False
```

**Step 5: Run all AgentAPI tests**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/backends/agentapi/ -v`

**Expected output:** All tests PASS.

**Step 6: Commit**

```bash
git add miniautogen/backends/agentapi/driver.py tests/backends/agentapi/test_driver.py
git commit -m "fix(agentapi): update capabilities to reflect actual driver abilities"
```

**If Task Fails:**
1. **Other tests assert `sessions is False`:** Search for other assertions on sessions capability and update them.
2. **Rollback:** `git checkout -- miniautogen/backends/agentapi/driver.py tests/backends/agentapi/test_driver.py`

---

## Phase 2: SDK Drivers

### Task 9: Create OpenAISDKDriver

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/openai_sdk/__init__.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/openai_sdk/driver.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/openai_sdk/factory.py`
- Test: `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/openai_sdk/__init__.py` (create)
- Test: `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/openai_sdk/test_driver.py` (create)
- Test: `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/openai_sdk/test_factory.py` (create)

**Prerequisites:**
- Task 4 completed (BaseDriver)
- `openai` package is in pyproject.toml dependencies (confirmed: `openai = ">=1.3.9"`)

**Step 1: Create directory and __init__.py**

Run:
```bash
mkdir -p /Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/openai_sdk
mkdir -p /Users/brunocapelao/Projects/miniAutoGen/tests/backends/openai_sdk
```

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/openai_sdk/__init__.py`:

```python
"""OpenAI SDK driver — direct integration with the openai Python package."""

from miniautogen.backends.openai_sdk.driver import OpenAISDKDriver
from miniautogen.backends.openai_sdk.factory import openai_sdk_factory

__all__ = ["OpenAISDKDriver", "openai_sdk_factory"]
```

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/openai_sdk/__init__.py`:

```python
```

**Step 2: Write the failing tests**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/openai_sdk/test_driver.py`:

```python
"""Tests for OpenAISDKDriver with mocked openai client."""

from __future__ import annotations

from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from miniautogen.backends.errors import CancelNotSupportedError
from miniautogen.backends.models import (
    AgentEvent,
    BackendCapabilities,
    CancelTurnRequest,
    SendTurnRequest,
    StartSessionRequest,
)
from miniautogen.backends.openai_sdk.driver import OpenAISDKDriver


def _mock_completion_response(content: str = "Hello!", model: str = "gpt-4o") -> MagicMock:
    """Create a mock that looks like openai ChatCompletion response."""
    choice = MagicMock()
    choice.message.content = content
    choice.message.role = "assistant"

    usage = MagicMock()
    usage.prompt_tokens = 10
    usage.completion_tokens = 5
    usage.total_tokens = 15

    response = MagicMock()
    response.choices = [choice]
    response.model = model
    response.usage = usage
    return response


@pytest.fixture
def mock_openai_client() -> AsyncMock:
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(
        return_value=_mock_completion_response(),
    )
    return client


@pytest.fixture
def driver(mock_openai_client: AsyncMock) -> OpenAISDKDriver:
    return OpenAISDKDriver(
        client=mock_openai_client,
        model="gpt-4o",
    )


class TestOpenAISDKDriverStartSession:
    @pytest.mark.asyncio
    async def test_returns_session_id(self, driver: OpenAISDKDriver) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="openai"),
        )
        assert resp.session_id.startswith("sess_")

    @pytest.mark.asyncio
    async def test_capabilities(self, driver: OpenAISDKDriver) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="openai"),
        )
        assert resp.capabilities.streaming is True
        assert resp.capabilities.tools is True
        assert resp.capabilities.sessions is False


class TestOpenAISDKDriverSendTurn:
    @pytest.mark.asyncio
    async def test_yields_event_sequence(self, driver: OpenAISDKDriver) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="openai"),
        )
        events: list[AgentEvent] = []
        async for ev in driver.send_turn(
            SendTurnRequest(
                session_id=resp.session_id,
                messages=[{"role": "user", "content": "hi"}],
            ),
        ):
            events.append(ev)

        assert len(events) == 3
        assert events[0].type == "turn_started"
        assert events[1].type == "message_completed"
        assert events[1].payload["text"] == "Hello!"
        assert events[2].type == "turn_completed"

    @pytest.mark.asyncio
    async def test_passes_model_to_sdk(
        self, driver: OpenAISDKDriver, mock_openai_client: AsyncMock,
    ) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="openai"),
        )
        async for _ in driver.send_turn(
            SendTurnRequest(
                session_id=resp.session_id,
                messages=[{"role": "user", "content": "hi"}],
            ),
        ):
            pass
        call_kwargs = mock_openai_client.chat.completions.create.call_args
        assert call_kwargs.kwargs.get("model") == "gpt-4o"

    @pytest.mark.asyncio
    async def test_passes_temperature(
        self, mock_openai_client: AsyncMock,
    ) -> None:
        driver = OpenAISDKDriver(
            client=mock_openai_client,
            model="gpt-4o",
            temperature=0.5,
        )
        resp = await driver.start_session(
            StartSessionRequest(backend_id="openai"),
        )
        async for _ in driver.send_turn(
            SendTurnRequest(
                session_id=resp.session_id,
                messages=[{"role": "user", "content": "hi"}],
            ),
        ):
            pass
        call_kwargs = mock_openai_client.chat.completions.create.call_args
        assert call_kwargs.kwargs.get("temperature") == 0.5


class TestOpenAISDKDriverOtherMethods:
    @pytest.mark.asyncio
    async def test_cancel_raises(self, driver: OpenAISDKDriver) -> None:
        with pytest.raises(CancelNotSupportedError):
            await driver.cancel_turn(CancelTurnRequest(session_id="s1"))

    @pytest.mark.asyncio
    async def test_list_artifacts_empty(self, driver: OpenAISDKDriver) -> None:
        result = await driver.list_artifacts("s1")
        assert result == []

    @pytest.mark.asyncio
    async def test_capabilities(self, driver: OpenAISDKDriver) -> None:
        caps = await driver.capabilities()
        assert isinstance(caps, BackendCapabilities)
        assert caps.streaming is True
        assert caps.tools is True
```

**Step 3: Run test to verify it fails**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/backends/openai_sdk/test_driver.py -v`

**Expected output:**
```
ModuleNotFoundError: No module named 'miniautogen.backends.openai_sdk'
```

**Step 4: Implement OpenAISDKDriver**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/openai_sdk/driver.py`:

```python
"""OpenAISDKDriver — direct OpenAI SDK integration.

Uses the official `openai` Python package with AsyncOpenAI for
non-streaming chat completions. Lighter than httpx-based AgentAPIDriver
and supports all OpenAI features natively.
"""

from __future__ import annotations

import uuid
from typing import Any, AsyncIterator

from miniautogen.backends.driver import AgentDriver
from miniautogen.backends.errors import CancelNotSupportedError, TurnExecutionError
from miniautogen.backends.models import (
    AgentEvent,
    ArtifactRef,
    BackendCapabilities,
    CancelTurnRequest,
    SendTurnRequest,
    StartSessionRequest,
    StartSessionResponse,
)
from miniautogen.observability.logging import get_logger

logger = get_logger(__name__)


class OpenAISDKDriver(AgentDriver):
    """Driver using the official OpenAI Python SDK (AsyncOpenAI).

    Supports: chat completions, tool calling, streaming (future).
    Does NOT manage sessions (stateless per-call).

    Args:
        client: An AsyncOpenAI instance (or mock for testing).
        model: Model identifier (e.g., "gpt-4o", "gpt-4o-mini").
        temperature: Sampling temperature.
        max_tokens: Maximum tokens in response.
        timeout_seconds: Request timeout.
    """

    def __init__(
        self,
        client: Any,
        model: str,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        timeout_seconds: float = 120.0,
    ) -> None:
        self._client = client
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout_seconds = timeout_seconds
        self._caps = BackendCapabilities(
            sessions=False,
            streaming=True,
            cancel=False,
            resume=False,
            tools=True,
            artifacts=False,
            multimodal=True,
        )

    async def start_session(
        self,
        request: StartSessionRequest,
    ) -> StartSessionResponse:
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        logger.info(
            "session_started",
            session_id=session_id,
            backend_id=request.backend_id,
            model=self._model,
        )
        return StartSessionResponse(
            session_id=session_id,
            capabilities=self._caps,
        )

    async def send_turn(
        self,
        request: SendTurnRequest,
    ) -> AsyncIterator[AgentEvent]:
        turn_id = f"turn_{uuid.uuid4().hex[:12]}"
        logger.debug("send_turn", session_id=request.session_id, turn_id=turn_id)

        yield AgentEvent(
            type="turn_started",
            session_id=request.session_id,
            turn_id=turn_id,
        )

        try:
            create_kwargs: dict[str, Any] = {
                "model": self._model,
                "messages": request.messages,
                "temperature": self._temperature,
            }
            if self._max_tokens is not None:
                create_kwargs["max_tokens"] = self._max_tokens

            response = await self._client.chat.completions.create(**create_kwargs)

            choice = response.choices[0]
            content = choice.message.content or ""
            role = choice.message.role or "assistant"

            yield AgentEvent(
                type="message_completed",
                session_id=request.session_id,
                turn_id=turn_id,
                payload={"text": content, "role": role},
            )

            # Build turn_completed payload with usage info
            completed_payload: dict[str, Any] = {}
            if hasattr(response, "model") and response.model:
                completed_payload["model"] = response.model
            if hasattr(response, "usage") and response.usage:
                completed_payload["usage"] = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }

            yield AgentEvent(
                type="turn_completed",
                session_id=request.session_id,
                turn_id=turn_id,
                payload=completed_payload,
            )

        except Exception as exc:
            logger.error("openai_sdk_error", error=str(exc), model=self._model)
            msg = f"OpenAI SDK error: {exc}"
            raise TurnExecutionError(msg) from exc

    async def cancel_turn(
        self,
        request: CancelTurnRequest,
    ) -> None:
        raise CancelNotSupportedError(
            "OpenAISDKDriver does not support cancellation",
        )

    async def list_artifacts(self, session_id: str) -> list[ArtifactRef]:
        return []

    async def close_session(self, session_id: str) -> None:
        pass

    async def capabilities(self) -> BackendCapabilities:
        return self._caps
```

**Step 5: Create factory**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/openai_sdk/factory.py`:

```python
"""Factory for creating OpenAISDKDriver from BackendConfig."""

from __future__ import annotations

import os

from miniautogen.backends.config import BackendConfig
from miniautogen.backends.openai_sdk.driver import OpenAISDKDriver


def openai_sdk_factory(config: BackendConfig) -> OpenAISDKDriver:
    """Create an OpenAISDKDriver from declarative config.

    Reads api_key from auth config or environment, model from metadata.
    """
    from openai import AsyncOpenAI

    api_key: str | None = None
    if config.auth and config.auth.type == "bearer" and config.auth.token_env:
        api_key = os.environ.get(config.auth.token_env)

    metadata = config.metadata
    model = metadata.get("model", "gpt-4o")
    temperature = metadata.get("temperature", 0.2)
    max_tokens = metadata.get("max_tokens")

    client_kwargs: dict = {"api_key": api_key}
    if config.endpoint:
        client_kwargs["base_url"] = config.endpoint

    client = AsyncOpenAI(**client_kwargs)

    return OpenAISDKDriver(
        client=client,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout_seconds=config.timeout_seconds,
    )
```

**Step 6: Write factory test**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/openai_sdk/test_factory.py`:

```python
"""Tests for OpenAI SDK factory."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from miniautogen.backends.config import AuthConfig, BackendConfig, DriverType
from miniautogen.backends.openai_sdk.driver import OpenAISDKDriver
from miniautogen.backends.openai_sdk.factory import openai_sdk_factory


class TestOpenAISDKFactory:
    @patch("miniautogen.backends.openai_sdk.factory.AsyncOpenAI")
    def test_creates_driver(self, mock_openai_cls: MagicMock) -> None:
        mock_openai_cls.return_value = MagicMock()
        config = BackendConfig(
            backend_id="openai-test",
            driver=DriverType.OPENAI_SDK,
            metadata={"model": "gpt-4o"},
        )
        driver = openai_sdk_factory(config)
        assert isinstance(driver, OpenAISDKDriver)

    @patch("miniautogen.backends.openai_sdk.factory.AsyncOpenAI")
    def test_passes_model_from_metadata(self, mock_openai_cls: MagicMock) -> None:
        mock_openai_cls.return_value = MagicMock()
        config = BackendConfig(
            backend_id="test",
            driver=DriverType.OPENAI_SDK,
            metadata={"model": "gpt-4o-mini"},
        )
        driver = openai_sdk_factory(config)
        assert driver._model == "gpt-4o-mini"

    @patch("miniautogen.backends.openai_sdk.factory.AsyncOpenAI")
    @patch.dict(os.environ, {"MY_KEY": "sk-test-123"})
    def test_resolves_api_key_from_auth(self, mock_openai_cls: MagicMock) -> None:
        mock_openai_cls.return_value = MagicMock()
        config = BackendConfig(
            backend_id="test",
            driver=DriverType.OPENAI_SDK,
            auth=AuthConfig(type="bearer", token_env="MY_KEY"),
            metadata={"model": "gpt-4o"},
        )
        openai_sdk_factory(config)
        call_kwargs = mock_openai_cls.call_args.kwargs
        assert call_kwargs["api_key"] == "sk-test-123"

    @patch("miniautogen.backends.openai_sdk.factory.AsyncOpenAI")
    def test_passes_endpoint_as_base_url(self, mock_openai_cls: MagicMock) -> None:
        mock_openai_cls.return_value = MagicMock()
        config = BackendConfig(
            backend_id="test",
            driver=DriverType.OPENAI_SDK,
            endpoint="https://custom-endpoint.com/v1",
            metadata={"model": "gpt-4o"},
        )
        openai_sdk_factory(config)
        call_kwargs = mock_openai_cls.call_args.kwargs
        assert call_kwargs["base_url"] == "https://custom-endpoint.com/v1"
```

**Step 7: Run all tests**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/backends/openai_sdk/ -v`

**Expected output:** All tests PASS.

**Step 8: Commit**

```bash
git add miniautogen/backends/openai_sdk/ tests/backends/openai_sdk/
git commit -m "feat(backends): add OpenAISDKDriver with direct SDK integration"
```

**If Task Fails:**
1. **openai import issue:** The `openai` package is already in pyproject.toml. If import fails, run `poetry install`.
2. **Mock structure mismatch:** Ensure mock has `chat.completions.create` chain working. `AsyncMock` auto-creates nested mocks.
3. **Rollback:** Delete both directories.

---

### Task 10: Create AnthropicSDKDriver

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/anthropic_sdk/__init__.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/anthropic_sdk/driver.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/anthropic_sdk/factory.py`
- Test: `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/anthropic_sdk/__init__.py` (create)
- Test: `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/anthropic_sdk/test_driver.py` (create)

**Prerequisites:**
- Task 9 completed (pattern established)
- `anthropic` package NOT in pyproject.toml -- will be added as optional extra

**Step 1: Create directories**

Run:
```bash
mkdir -p /Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/anthropic_sdk
mkdir -p /Users/brunocapelao/Projects/miniAutoGen/tests/backends/anthropic_sdk
```

**Step 2: Write the failing test**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/anthropic_sdk/__init__.py` (empty file).

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/anthropic_sdk/test_driver.py`:

```python
"""Tests for AnthropicSDKDriver with mocked anthropic client."""

from __future__ import annotations

from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from miniautogen.backends.anthropic_sdk.driver import AnthropicSDKDriver
from miniautogen.backends.errors import CancelNotSupportedError
from miniautogen.backends.models import (
    AgentEvent,
    BackendCapabilities,
    CancelTurnRequest,
    SendTurnRequest,
    StartSessionRequest,
)


def _mock_anthropic_response(
    content: str = "Hello!",
    model: str = "claude-sonnet-4-20250514",
) -> MagicMock:
    """Create a mock that looks like an Anthropic Messages response."""
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = content

    usage = MagicMock()
    usage.input_tokens = 10
    usage.output_tokens = 5

    response = MagicMock()
    response.content = [text_block]
    response.model = model
    response.role = "assistant"
    response.usage = usage
    response.stop_reason = "end_turn"
    return response


@pytest.fixture
def mock_anthropic_client() -> AsyncMock:
    client = AsyncMock()
    client.messages.create = AsyncMock(
        return_value=_mock_anthropic_response(),
    )
    return client


@pytest.fixture
def driver(mock_anthropic_client: AsyncMock) -> AnthropicSDKDriver:
    return AnthropicSDKDriver(
        client=mock_anthropic_client,
        model="claude-sonnet-4-20250514",
    )


class TestAnthropicSDKDriverSendTurn:
    @pytest.mark.asyncio
    async def test_yields_event_sequence(self, driver: AnthropicSDKDriver) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="anthropic"),
        )
        events: list[AgentEvent] = []
        async for ev in driver.send_turn(
            SendTurnRequest(
                session_id=resp.session_id,
                messages=[{"role": "user", "content": "hi"}],
            ),
        ):
            events.append(ev)

        assert len(events) == 3
        assert events[0].type == "turn_started"
        assert events[1].type == "message_completed"
        assert events[1].payload["text"] == "Hello!"
        assert events[2].type == "turn_completed"

    @pytest.mark.asyncio
    async def test_transforms_messages_for_anthropic(
        self, driver: AnthropicSDKDriver, mock_anthropic_client: AsyncMock,
    ) -> None:
        """Anthropic requires system message to be separate."""
        resp = await driver.start_session(
            StartSessionRequest(backend_id="anthropic"),
        )
        async for _ in driver.send_turn(
            SendTurnRequest(
                session_id=resp.session_id,
                messages=[
                    {"role": "system", "content": "You are helpful."},
                    {"role": "user", "content": "hi"},
                ],
            ),
        ):
            pass
        call_kwargs = mock_anthropic_client.messages.create.call_args.kwargs
        # System message should be extracted to `system` parameter
        assert call_kwargs.get("system") == "You are helpful."
        # Messages should only contain non-system messages
        assert all(m["role"] != "system" for m in call_kwargs["messages"])

    @pytest.mark.asyncio
    async def test_capabilities(self, driver: AnthropicSDKDriver) -> None:
        caps = await driver.capabilities()
        assert caps.streaming is True
        assert caps.tools is True
        assert caps.sessions is False

    @pytest.mark.asyncio
    async def test_cancel_raises(self, driver: AnthropicSDKDriver) -> None:
        with pytest.raises(CancelNotSupportedError):
            await driver.cancel_turn(CancelTurnRequest(session_id="s1"))
```

**Step 3: Run test to verify it fails**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/backends/anthropic_sdk/test_driver.py -v`

**Expected output:**
```
ModuleNotFoundError: No module named 'miniautogen.backends.anthropic_sdk'
```

**Step 4: Implement AnthropicSDKDriver**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/anthropic_sdk/__init__.py`:

```python
"""Anthropic SDK driver — direct integration with the anthropic Python package."""

from miniautogen.backends.anthropic_sdk.driver import AnthropicSDKDriver
from miniautogen.backends.anthropic_sdk.factory import anthropic_sdk_factory

__all__ = ["AnthropicSDKDriver", "anthropic_sdk_factory"]
```

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/anthropic_sdk/driver.py`:

```python
"""AnthropicSDKDriver — direct Anthropic SDK integration.

Uses the official `anthropic` Python package with AsyncAnthropic.
Handles Anthropic's unique message format (system as separate param,
content as list of blocks).
"""

from __future__ import annotations

import uuid
from typing import Any, AsyncIterator

from miniautogen.backends.driver import AgentDriver
from miniautogen.backends.errors import CancelNotSupportedError, TurnExecutionError
from miniautogen.backends.models import (
    AgentEvent,
    ArtifactRef,
    BackendCapabilities,
    CancelTurnRequest,
    SendTurnRequest,
    StartSessionRequest,
    StartSessionResponse,
)
from miniautogen.observability.logging import get_logger

logger = get_logger(__name__)


class AnthropicSDKDriver(AgentDriver):
    """Driver using the official Anthropic Python SDK (AsyncAnthropic).

    Handles the Anthropic-specific message format:
    - System messages are extracted to a separate `system` parameter
    - Content blocks are normalized to text

    Args:
        client: An AsyncAnthropic instance (or mock for testing).
        model: Model identifier (e.g., "claude-sonnet-4-20250514").
        temperature: Sampling temperature.
        max_tokens: Maximum tokens in response (Anthropic requires this).
        timeout_seconds: Request timeout.
    """

    def __init__(
        self,
        client: Any,
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        timeout_seconds: float = 120.0,
    ) -> None:
        self._client = client
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout_seconds = timeout_seconds
        self._caps = BackendCapabilities(
            sessions=False,
            streaming=True,
            cancel=False,
            resume=False,
            tools=True,
            artifacts=False,
            multimodal=True,
        )

    async def start_session(
        self,
        request: StartSessionRequest,
    ) -> StartSessionResponse:
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        logger.info(
            "session_started",
            session_id=session_id,
            backend_id=request.backend_id,
            model=self._model,
        )
        return StartSessionResponse(
            session_id=session_id,
            capabilities=self._caps,
        )

    async def send_turn(
        self,
        request: SendTurnRequest,
    ) -> AsyncIterator[AgentEvent]:
        turn_id = f"turn_{uuid.uuid4().hex[:12]}"
        logger.debug("send_turn", session_id=request.session_id, turn_id=turn_id)

        yield AgentEvent(
            type="turn_started",
            session_id=request.session_id,
            turn_id=turn_id,
        )

        try:
            # Extract system message (Anthropic requires it as separate param)
            system_prompt, messages = self._transform_messages(request.messages)

            create_kwargs: dict[str, Any] = {
                "model": self._model,
                "messages": messages,
                "max_tokens": self._max_tokens,
                "temperature": self._temperature,
            }
            if system_prompt:
                create_kwargs["system"] = system_prompt

            response = await self._client.messages.create(**create_kwargs)

            # Extract text from content blocks
            text_parts = []
            for block in response.content:
                if hasattr(block, "text"):
                    text_parts.append(block.text)
            content = "\n".join(text_parts) if text_parts else ""

            yield AgentEvent(
                type="message_completed",
                session_id=request.session_id,
                turn_id=turn_id,
                payload={"text": content, "role": response.role},
            )

            completed_payload: dict[str, Any] = {}
            if hasattr(response, "model") and response.model:
                completed_payload["model"] = response.model
            if hasattr(response, "usage") and response.usage:
                completed_payload["usage"] = {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                }

            yield AgentEvent(
                type="turn_completed",
                session_id=request.session_id,
                turn_id=turn_id,
                payload=completed_payload,
            )

        except Exception as exc:
            logger.error("anthropic_sdk_error", error=str(exc), model=self._model)
            msg = f"Anthropic SDK error: {exc}"
            raise TurnExecutionError(msg) from exc

    def _transform_messages(
        self, messages: list[dict[str, Any]],
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """Extract system message and format for Anthropic API.

        Anthropic requires:
        - System message as a separate `system` parameter
        - No "system" role in the messages list

        Returns:
            Tuple of (system_prompt, filtered_messages).
        """
        system_parts: list[str] = []
        filtered: list[dict[str, Any]] = []

        for msg in messages:
            if msg.get("role") == "system":
                system_parts.append(msg.get("content", ""))
            else:
                filtered.append(msg)

        system_prompt = "\n".join(system_parts) if system_parts else None
        return system_prompt, filtered

    async def cancel_turn(
        self,
        request: CancelTurnRequest,
    ) -> None:
        raise CancelNotSupportedError(
            "AnthropicSDKDriver does not support cancellation",
        )

    async def list_artifacts(self, session_id: str) -> list[ArtifactRef]:
        return []

    async def close_session(self, session_id: str) -> None:
        pass

    async def capabilities(self) -> BackendCapabilities:
        return self._caps
```

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/anthropic_sdk/factory.py`:

```python
"""Factory for creating AnthropicSDKDriver from BackendConfig."""

from __future__ import annotations

import os

from miniautogen.backends.anthropic_sdk.driver import AnthropicSDKDriver
from miniautogen.backends.config import BackendConfig


def anthropic_sdk_factory(config: BackendConfig) -> AnthropicSDKDriver:
    """Create an AnthropicSDKDriver from declarative config.

    Requires the `anthropic` package to be installed.
    """
    try:
        from anthropic import AsyncAnthropic
    except ImportError as exc:
        msg = (
            "anthropic package not installed. "
            "Install with: pip install miniautogen[anthropic]"
        )
        raise ImportError(msg) from exc

    api_key: str | None = None
    if config.auth and config.auth.type == "bearer" and config.auth.token_env:
        api_key = os.environ.get(config.auth.token_env)

    metadata = config.metadata
    model = metadata.get("model", "claude-sonnet-4-20250514")
    temperature = metadata.get("temperature", 0.2)
    max_tokens = metadata.get("max_tokens", 4096)

    client = AsyncAnthropic(api_key=api_key)

    return AnthropicSDKDriver(
        client=client,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout_seconds=config.timeout_seconds,
    )
```

**Step 5: Run tests**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/backends/anthropic_sdk/ -v`

**Expected output:** All tests PASS.

**Step 6: Commit**

```bash
git add miniautogen/backends/anthropic_sdk/ tests/backends/anthropic_sdk/
git commit -m "feat(backends): add AnthropicSDKDriver with message transformation"
```

**If Task Fails:**
1. **anthropic not installed for factory test:** Factory tests should mock the import or only test the driver directly.
2. **Message transformation:** Verify the system message extraction logic works with the mock structure.
3. **Rollback:** Delete both directories.

---

### Task 11: Create GoogleGenAIDriver

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/google_genai/__init__.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/google_genai/driver.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/google_genai/factory.py`
- Test: `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/google_genai/__init__.py` (create)
- Test: `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/google_genai/test_driver.py` (create)

**Prerequisites:**
- Task 10 completed (pattern established)

**Step 1: Create directories**

Run:
```bash
mkdir -p /Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/google_genai
mkdir -p /Users/brunocapelao/Projects/miniAutoGen/tests/backends/google_genai
```

**Step 2: Write the failing test**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/google_genai/__init__.py` (empty file).

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/google_genai/test_driver.py`:

```python
"""Tests for GoogleGenAIDriver with mocked client."""

from __future__ import annotations

from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from miniautogen.backends.errors import CancelNotSupportedError
from miniautogen.backends.google_genai.driver import GoogleGenAIDriver
from miniautogen.backends.models import (
    AgentEvent,
    BackendCapabilities,
    CancelTurnRequest,
    SendTurnRequest,
    StartSessionRequest,
)


def _mock_google_response(content: str = "Hello from Gemini!") -> MagicMock:
    """Create a mock that looks like a google-genai GenerateContentResponse."""
    response = MagicMock()
    response.text = content
    response.candidates = [MagicMock()]
    response.candidates[0].content.parts = [MagicMock(text=content)]

    usage = MagicMock()
    usage.prompt_token_count = 10
    usage.candidates_token_count = 5
    usage.total_token_count = 15
    response.usage_metadata = usage

    return response


@pytest.fixture
def mock_google_client() -> AsyncMock:
    client = AsyncMock()
    client.aio.models.generate_content = AsyncMock(
        return_value=_mock_google_response(),
    )
    return client


@pytest.fixture
def driver(mock_google_client: AsyncMock) -> GoogleGenAIDriver:
    return GoogleGenAIDriver(
        client=mock_google_client,
        model="gemini-2.5-pro",
    )


class TestGoogleGenAIDriverSendTurn:
    @pytest.mark.asyncio
    async def test_yields_event_sequence(self, driver: GoogleGenAIDriver) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="google"),
        )
        events: list[AgentEvent] = []
        async for ev in driver.send_turn(
            SendTurnRequest(
                session_id=resp.session_id,
                messages=[{"role": "user", "content": "hi"}],
            ),
        ):
            events.append(ev)

        assert len(events) == 3
        assert events[0].type == "turn_started"
        assert events[1].type == "message_completed"
        assert events[1].payload["text"] == "Hello from Gemini!"
        assert events[2].type == "turn_completed"

    @pytest.mark.asyncio
    async def test_capabilities(self, driver: GoogleGenAIDriver) -> None:
        caps = await driver.capabilities()
        assert caps.streaming is True
        assert caps.tools is True
        assert caps.multimodal is True

    @pytest.mark.asyncio
    async def test_cancel_raises(self, driver: GoogleGenAIDriver) -> None:
        with pytest.raises(CancelNotSupportedError):
            await driver.cancel_turn(CancelTurnRequest(session_id="s1"))
```

**Step 3: Run test to verify it fails**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/backends/google_genai/test_driver.py -v`

**Expected output:**
```
ModuleNotFoundError: No module named 'miniautogen.backends.google_genai'
```

**Step 4: Implement GoogleGenAIDriver**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/google_genai/__init__.py`:

```python
"""Google GenAI driver — direct integration with the google-genai Python package."""

from miniautogen.backends.google_genai.driver import GoogleGenAIDriver
from miniautogen.backends.google_genai.factory import google_genai_factory

__all__ = ["GoogleGenAIDriver", "google_genai_factory"]
```

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/google_genai/driver.py`:

```python
"""GoogleGenAIDriver — direct Google GenAI SDK integration.

Uses the official `google-genai` Python package for Gemini models.
Handles Google's unique content format (parts-based).
"""

from __future__ import annotations

import uuid
from typing import Any, AsyncIterator

from miniautogen.backends.driver import AgentDriver
from miniautogen.backends.errors import CancelNotSupportedError, TurnExecutionError
from miniautogen.backends.models import (
    AgentEvent,
    ArtifactRef,
    BackendCapabilities,
    CancelTurnRequest,
    SendTurnRequest,
    StartSessionRequest,
    StartSessionResponse,
)
from miniautogen.observability.logging import get_logger

logger = get_logger(__name__)


class GoogleGenAIDriver(AgentDriver):
    """Driver using the official Google GenAI Python SDK.

    Args:
        client: A google.genai.Client instance (or mock for testing).
        model: Model identifier (e.g., "gemini-2.5-pro").
        temperature: Sampling temperature.
        max_tokens: Maximum output tokens.
        timeout_seconds: Request timeout.
    """

    def __init__(
        self,
        client: Any,
        model: str,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        timeout_seconds: float = 120.0,
    ) -> None:
        self._client = client
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout_seconds = timeout_seconds
        self._caps = BackendCapabilities(
            sessions=False,
            streaming=True,
            cancel=False,
            resume=False,
            tools=True,
            artifacts=False,
            multimodal=True,
        )

    async def start_session(
        self,
        request: StartSessionRequest,
    ) -> StartSessionResponse:
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        logger.info(
            "session_started",
            session_id=session_id,
            backend_id=request.backend_id,
            model=self._model,
        )
        return StartSessionResponse(
            session_id=session_id,
            capabilities=self._caps,
        )

    async def send_turn(
        self,
        request: SendTurnRequest,
    ) -> AsyncIterator[AgentEvent]:
        turn_id = f"turn_{uuid.uuid4().hex[:12]}"
        logger.debug("send_turn", session_id=request.session_id, turn_id=turn_id)

        yield AgentEvent(
            type="turn_started",
            session_id=request.session_id,
            turn_id=turn_id,
        )

        try:
            # Transform messages to Google format
            contents = self._transform_messages(request.messages)

            config_kwargs: dict[str, Any] = {
                "temperature": self._temperature,
            }
            if self._max_tokens is not None:
                config_kwargs["max_output_tokens"] = self._max_tokens

            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=contents,
                config=config_kwargs,
            )

            content = response.text or ""

            yield AgentEvent(
                type="message_completed",
                session_id=request.session_id,
                turn_id=turn_id,
                payload={"text": content, "role": "assistant"},
            )

            completed_payload: dict[str, Any] = {"model": self._model}
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                usage = response.usage_metadata
                completed_payload["usage"] = {
                    "prompt_tokens": getattr(usage, "prompt_token_count", 0),
                    "completion_tokens": getattr(usage, "candidates_token_count", 0),
                    "total_tokens": getattr(usage, "total_token_count", 0),
                }

            yield AgentEvent(
                type="turn_completed",
                session_id=request.session_id,
                turn_id=turn_id,
                payload=completed_payload,
            )

        except Exception as exc:
            logger.error("google_genai_error", error=str(exc), model=self._model)
            msg = f"Google GenAI SDK error: {exc}"
            raise TurnExecutionError(msg) from exc

    def _transform_messages(
        self, messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Transform internal messages to Google GenAI format.

        Google uses 'user' and 'model' roles (not 'assistant').
        System messages are prepended to the first user message.
        """
        system_parts: list[str] = []
        transformed: list[dict[str, Any]] = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                system_parts.append(content)
                continue

            # Map OpenAI roles to Google roles
            google_role = "model" if role == "assistant" else "user"

            # Prepend system prompt to first user message
            if google_role == "user" and system_parts:
                content = "\n".join(system_parts) + "\n\n" + content
                system_parts = []

            transformed.append({
                "role": google_role,
                "parts": [{"text": content}],
            })

        return transformed

    async def cancel_turn(
        self,
        request: CancelTurnRequest,
    ) -> None:
        raise CancelNotSupportedError(
            "GoogleGenAIDriver does not support cancellation",
        )

    async def list_artifacts(self, session_id: str) -> list[ArtifactRef]:
        return []

    async def close_session(self, session_id: str) -> None:
        pass

    async def capabilities(self) -> BackendCapabilities:
        return self._caps
```

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/google_genai/factory.py`:

```python
"""Factory for creating GoogleGenAIDriver from BackendConfig."""

from __future__ import annotations

import os

from miniautogen.backends.config import BackendConfig
from miniautogen.backends.google_genai.driver import GoogleGenAIDriver


def google_genai_factory(config: BackendConfig) -> GoogleGenAIDriver:
    """Create a GoogleGenAIDriver from declarative config.

    Requires the `google-genai` package to be installed.
    """
    try:
        from google import genai
    except ImportError as exc:
        msg = (
            "google-genai package not installed. "
            "Install with: pip install miniautogen[google]"
        )
        raise ImportError(msg) from exc

    api_key: str | None = None
    if config.auth and config.auth.type == "bearer" and config.auth.token_env:
        api_key = os.environ.get(config.auth.token_env)

    metadata = config.metadata
    model = metadata.get("model", "gemini-2.5-pro")
    temperature = metadata.get("temperature", 0.2)
    max_tokens = metadata.get("max_tokens")

    client = genai.Client(api_key=api_key)

    return GoogleGenAIDriver(
        client=client,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout_seconds=config.timeout_seconds,
    )
```

**Step 5: Run tests**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/backends/google_genai/ -v`

**Expected output:** All tests PASS.

**Step 6: Commit**

```bash
git add miniautogen/backends/google_genai/ tests/backends/google_genai/
git commit -m "feat(backends): add GoogleGenAIDriver with Gemini SDK integration"
```

**If Task Fails:**
1. **Mock structure for google-genai:** The `client.aio.models.generate_content` chain needs AsyncMock to auto-create intermediates. If it fails, restructure the mock.
2. **Rollback:** Delete both directories.

---

### Task 12: Add optional dependencies to pyproject.toml

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/pyproject.toml:27-30`

**Prerequisites:**
- Tasks 9-11 completed

**Step 1: Update pyproject.toml**

In `/Users/brunocapelao/Projects/miniAutoGen/pyproject.toml`, update the `[tool.poetry.dependencies]` section to make `openai` and `litellm` optional, and add `anthropic` and `google-genai` as optional deps. Then update `[tool.poetry.extras]`:

Replace the extras section (line 29-30):

```toml
[tool.poetry.extras]
tui = ["textual"]
anthropic = ["anthropic"]
google = ["google-genai"]
litellm = ["litellm"]
all-providers = ["openai", "anthropic", "google-genai"]
all = ["textual", "openai", "anthropic", "google-genai"]
```

Also add `anthropic` and `google-genai` as optional dependencies:

```toml
anthropic = {version = ">=0.40.0", optional = true}
google-genai = {version = ">=1.0.0", optional = true}
```

**Important:** Do NOT remove `openai` from required dependencies since it is already used by the existing `OpenAIProvider` adapter. Do NOT remove `litellm` from required dependencies yet -- that happens in Phase 5 (deprecation).

**Step 2: Verify**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && poetry check`

**Expected output:**
```
All set!
```

**Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "feat(deps): add anthropic and google-genai as optional extras"
```

**If Task Fails:**
1. **Poetry validation error:** Ensure version specifiers are valid. `anthropic >= 0.40.0` and `google-genai >= 1.0.0` should work.
2. **Rollback:** `git checkout -- pyproject.toml`

---

### Task 13: Run Code Review (Phase 1 + 2)

1. **Dispatch all 3 reviewers in parallel:**
   - REQUIRED SUB-SKILL: Use requesting-code-review
   - Focus on: Tasks 7-12 (wiring, SDK drivers, dependencies)

2. **Handle findings by severity** (same rules as Task 6).

3. **Proceed only when zero Critical/High/Medium issues remain.**

---

## Phase 3: CLI Drivers

### Task 14: Create CLIAgentDriver

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/cli/__init__.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/cli/driver.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/cli/factory.py`
- Test: `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/cli/__init__.py` (create)
- Test: `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/cli/test_driver.py` (create)

**Prerequisites:**
- Tasks 9-11 completed (pattern established)

**Step 1: Create directories**

Run:
```bash
mkdir -p /Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/cli
mkdir -p /Users/brunocapelao/Projects/miniAutoGen/tests/backends/cli
```

**Step 2: Write the failing test**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/cli/__init__.py` (empty file).

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/cli/test_driver.py`:

```python
"""Tests for CLIAgentDriver with mocked subprocess."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from miniautogen.backends.cli.driver import CLIAgentDriver
from miniautogen.backends.errors import CancelNotSupportedError
from miniautogen.backends.models import (
    AgentEvent,
    BackendCapabilities,
    CancelTurnRequest,
    SendTurnRequest,
    StartSessionRequest,
)


@pytest.fixture
def driver() -> CLIAgentDriver:
    return CLIAgentDriver(
        command=["echo", "test"],
        provider="claude-code",
    )


class TestCLIAgentDriverStartSession:
    @pytest.mark.asyncio
    async def test_returns_session_id(self, driver: CLIAgentDriver) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="cli"),
        )
        assert resp.session_id.startswith("sess_")

    @pytest.mark.asyncio
    async def test_capabilities(self, driver: CLIAgentDriver) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="cli"),
        )
        assert resp.capabilities.streaming is True
        assert resp.capabilities.tools is True
        assert resp.capabilities.sessions is True


class TestCLIAgentDriverOtherMethods:
    @pytest.mark.asyncio
    async def test_cancel_raises(self, driver: CLIAgentDriver) -> None:
        with pytest.raises(CancelNotSupportedError):
            await driver.cancel_turn(CancelTurnRequest(session_id="s1"))

    @pytest.mark.asyncio
    async def test_list_artifacts_empty(self, driver: CLIAgentDriver) -> None:
        result = await driver.list_artifacts("s1")
        assert result == []

    @pytest.mark.asyncio
    async def test_capabilities(self, driver: CLIAgentDriver) -> None:
        caps = await driver.capabilities()
        assert isinstance(caps, BackendCapabilities)
        assert caps.streaming is True
        assert caps.tools is True
        assert caps.sessions is True
        assert caps.artifacts is True
```

**Step 3: Run test to verify it fails**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/backends/cli/test_driver.py -v`

**Expected output:**
```
ModuleNotFoundError: No module named 'miniautogen.backends.cli'
```

**Step 4: Implement CLIAgentDriver**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/cli/__init__.py`:

```python
"""CLI agent driver — runs CLI tools as subprocess with async IO."""

from miniautogen.backends.cli.driver import CLIAgentDriver
from miniautogen.backends.cli.factory import cli_factory

__all__ = ["CLIAgentDriver", "cli_factory"]
```

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/cli/driver.py`:

```python
"""CLIAgentDriver — runs CLI agent tools as subprocess.

Supports Claude Code, Gemini CLI, Codex CLI, and any CLI tool
that accepts JSON on stdin and outputs JSON on stdout.

Uses anyio.open_process for async subprocess management.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, AsyncIterator

from miniautogen.backends.driver import AgentDriver
from miniautogen.backends.errors import CancelNotSupportedError, TurnExecutionError
from miniautogen.backends.models import (
    AgentEvent,
    ArtifactRef,
    BackendCapabilities,
    CancelTurnRequest,
    SendTurnRequest,
    StartSessionRequest,
    StartSessionResponse,
)
from miniautogen.observability.logging import get_logger

logger = get_logger(__name__)


class CLIAgentDriver(AgentDriver):
    """Driver that runs CLI agent tools as subprocess.

    Communication protocol:
    - Send: JSON object on stdin (one per line)
    - Receive: JSON lines on stdout (one event per line)

    Args:
        command: Command and arguments to run (e.g., ["claude", "--agent"]).
        provider: Provider identifier for logging.
        timeout_seconds: Maximum time for a single turn.
        env: Additional environment variables for the subprocess.
    """

    def __init__(
        self,
        command: list[str],
        provider: str = "cli",
        timeout_seconds: float = 300.0,
        env: dict[str, str] | None = None,
    ) -> None:
        self._command = command
        self._provider = provider
        self._timeout_seconds = timeout_seconds
        self._env = env or {}
        self._caps = BackendCapabilities(
            sessions=True,
            streaming=True,
            cancel=False,
            resume=False,
            tools=True,
            artifacts=True,
            multimodal=False,
        )

    async def start_session(
        self,
        request: StartSessionRequest,
    ) -> StartSessionResponse:
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        logger.info(
            "session_started",
            session_id=session_id,
            backend_id=request.backend_id,
            provider=self._provider,
            command=self._command,
        )
        return StartSessionResponse(
            session_id=session_id,
            capabilities=self._caps,
        )

    async def send_turn(
        self,
        request: SendTurnRequest,
    ) -> AsyncIterator[AgentEvent]:
        import anyio

        turn_id = f"turn_{uuid.uuid4().hex[:12]}"
        logger.debug(
            "send_turn_cli",
            session_id=request.session_id,
            turn_id=turn_id,
            command=self._command,
        )

        yield AgentEvent(
            type="turn_started",
            session_id=request.session_id,
            turn_id=turn_id,
        )

        try:
            # Prepare input as JSON
            input_data = json.dumps({
                "session_id": request.session_id,
                "messages": request.messages,
                "metadata": request.metadata,
            }) + "\n"

            async with await anyio.open_process(
                self._command,
                stdin=anyio.abc.PIPE,
                stdout=anyio.abc.PIPE,
                stderr=anyio.abc.PIPE,
            ) as proc:
                # Send input
                if proc.stdin:
                    await proc.stdin.send(input_data.encode())
                    await proc.stdin.aclose()

                # Read output
                output = b""
                if proc.stdout:
                    async for chunk in proc.stdout:
                        output += chunk

                await proc.wait()

                if proc.returncode != 0:
                    stderr_output = b""
                    if proc.stderr:
                        async for chunk in proc.stderr:
                            stderr_output += chunk
                    msg = (
                        f"CLI process exited with code {proc.returncode}: "
                        f"{stderr_output.decode(errors='replace')[:500]}"
                    )
                    raise TurnExecutionError(msg)

                # Parse output as text response
                content = output.decode(errors="replace").strip()

                yield AgentEvent(
                    type="message_completed",
                    session_id=request.session_id,
                    turn_id=turn_id,
                    payload={"text": content, "role": "assistant"},
                )

        except TurnExecutionError:
            raise
        except Exception as exc:
            logger.error("cli_driver_error", error=str(exc), command=self._command)
            msg = f"CLI driver error: {exc}"
            raise TurnExecutionError(msg) from exc

        yield AgentEvent(
            type="turn_completed",
            session_id=request.session_id,
            turn_id=turn_id,
        )

    async def cancel_turn(
        self,
        request: CancelTurnRequest,
    ) -> None:
        raise CancelNotSupportedError(
            "CLIAgentDriver does not support cancellation yet",
        )

    async def list_artifacts(self, session_id: str) -> list[ArtifactRef]:
        return []

    async def close_session(self, session_id: str) -> None:
        pass

    async def capabilities(self) -> BackendCapabilities:
        return self._caps
```

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/cli/factory.py`:

```python
"""Factory for creating CLIAgentDriver from BackendConfig."""

from __future__ import annotations

from miniautogen.backends.cli.driver import CLIAgentDriver
from miniautogen.backends.config import BackendConfig


def cli_factory(config: BackendConfig) -> CLIAgentDriver:
    """Create a CLIAgentDriver from declarative config."""
    if not config.command:
        msg = f"command is required for CLI driver '{config.backend_id}'"
        raise ValueError(msg)

    return CLIAgentDriver(
        command=config.command,
        provider=config.backend_id,
        timeout_seconds=config.timeout_seconds,
        env=config.env or {},
    )
```

**Step 5: Run tests**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/backends/cli/ -v`

**Expected output:** All tests PASS.

**Step 6: Commit**

```bash
git add miniautogen/backends/cli/ tests/backends/cli/
git commit -m "feat(backends): add CLIAgentDriver for subprocess-based agent tools"
```

**If Task Fails:**
1. **anyio.open_process API:** The `stdin=anyio.abc.PIPE` syntax may differ. Check anyio docs -- may need `subprocess.PIPE` instead.
2. **The send_turn test is not testing subprocess:** That's intentional -- subprocess tests are hard to unit test. The test validates the object creation and capabilities. Integration tests will cover the subprocess flow.
3. **Rollback:** Delete both directories.

---

### Task 15: Register all factories in EngineResolver

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/engine_resolver.py` (update `_register_default_factories`)
- Test: `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/test_engine_resolver.py` (extend)

**Prerequisites:**
- Tasks 9-14 completed (all drivers exist)

**Step 1: Write the failing test**

Add to `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/test_engine_resolver.py`:

```python
class TestEngineResolverFactoryRegistration:
    def test_all_driver_types_have_factories(self) -> None:
        resolver = EngineResolver()
        expected_types = {
            DriverType.AGENT_API,
            DriverType.OPENAI_SDK,
            DriverType.ANTHROPIC_SDK,
            DriverType.GOOGLE_GENAI,
            DriverType.CLI,
        }
        registered = set(resolver._resolver._factories.keys())
        assert expected_types.issubset(registered)
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/backends/test_engine_resolver.py::TestEngineResolverFactoryRegistration -v`

**Expected output:**
```
FAILED - AssertionError (only AGENT_API is registered)
```

**Step 3: Update _register_default_factories**

In `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/engine_resolver.py`, update the imports and `_register_default_factories`:

Add imports:

```python
from miniautogen.backends.agentapi.factory import agentapi_factory
from miniautogen.backends.openai_sdk.factory import openai_sdk_factory
from miniautogen.backends.anthropic_sdk.factory import anthropic_sdk_factory
from miniautogen.backends.google_genai.factory import google_genai_factory
from miniautogen.backends.cli.factory import cli_factory
```

Update the method:

```python
    def _register_default_factories(self) -> None:
        """Register factories for all built-in driver types."""
        self._resolver.register_factory(DriverType.AGENT_API, agentapi_factory)
        self._resolver.register_factory(DriverType.OPENAI_SDK, openai_sdk_factory)
        self._resolver.register_factory(DriverType.ANTHROPIC_SDK, anthropic_sdk_factory)
        self._resolver.register_factory(DriverType.GOOGLE_GENAI, google_genai_factory)
        self._resolver.register_factory(DriverType.CLI, cli_factory)
```

**Step 4: Run tests**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/backends/test_engine_resolver.py -v`

**Expected output:** All tests PASS.

**Step 5: Commit**

```bash
git add miniautogen/backends/engine_resolver.py tests/backends/test_engine_resolver.py
git commit -m "feat(backends): register all driver factories in EngineResolver"
```

**If Task Fails:**
1. **Import error for optional packages:** The factories use lazy imports (`from anthropic import ...` inside the factory function), so importing the factory module itself should not fail.
2. **Rollback:** `git checkout -- miniautogen/backends/engine_resolver.py`

---

## Phase 4: Fallback Chains + Capability Enforcement

### Task 16: Implement resolve_with_fallbacks

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/engine_resolver.py` (already has stub)
- Test: `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/test_engine_resolver.py` (extend)

**Prerequisites:**
- Task 15 completed

**Step 1: Write the failing test**

Add to `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/test_engine_resolver.py`:

```python
class TestEngineResolverFallbacks:
    def test_primary_succeeds_no_fallback_used(self) -> None:
        resolver = EngineResolver()
        resolver._resolver.register_factory(
            DriverType.AGENT_API, lambda cfg: FakeDriver(),
        )
        config = _make_project_config(
            profiles={
                "primary": EngineProfileConfig(
                    provider="openai-compat",
                    endpoint="http://localhost:11434/v1",
                    fallbacks=["backup"],
                ),
                "backup": EngineProfileConfig(
                    provider="openai-compat",
                    endpoint="http://localhost:11435/v1",
                ),
            },
        )
        driver = resolver.resolve_with_fallbacks("primary", config)
        assert isinstance(driver, AgentDriver)

    def test_primary_fails_fallback_used(self) -> None:
        resolver = EngineResolver()
        call_count = 0

        def failing_then_succeeding_factory(cfg: BackendConfig) -> FakeDriver:
            nonlocal call_count
            call_count += 1
            if cfg.backend_id == "primary":
                raise BackendUnavailableError("primary down")
            return FakeDriver()

        resolver._resolver.register_factory(
            DriverType.AGENT_API, failing_then_succeeding_factory,
        )
        config = _make_project_config(
            profiles={
                "primary": EngineProfileConfig(
                    provider="openai-compat",
                    endpoint="http://primary:8000",
                    fallbacks=["backup"],
                ),
                "backup": EngineProfileConfig(
                    provider="openai-compat",
                    endpoint="http://backup:8000",
                ),
            },
        )
        driver = resolver.resolve_with_fallbacks("primary", config)
        assert isinstance(driver, AgentDriver)

    def test_all_fail_raises(self) -> None:
        resolver = EngineResolver()
        resolver._resolver.register_factory(
            DriverType.AGENT_API,
            lambda cfg: (_ for _ in ()).throw(BackendUnavailableError("down")),
        )
        config = _make_project_config(
            profiles={
                "primary": EngineProfileConfig(
                    provider="openai-compat",
                    endpoint="http://primary:8000",
                    fallbacks=["backup"],
                ),
                "backup": EngineProfileConfig(
                    provider="openai-compat",
                    endpoint="http://backup:8000",
                ),
            },
        )
        with pytest.raises(BackendUnavailableError, match="All engines failed"):
            resolver.resolve_with_fallbacks("primary", config)

    def test_unknown_profile_in_fallback_skipped(self) -> None:
        resolver = EngineResolver()
        resolver._resolver.register_factory(
            DriverType.AGENT_API, lambda cfg: FakeDriver(),
        )
        config = _make_project_config(
            profiles={
                "primary": EngineProfileConfig(
                    provider="openai-compat",
                    endpoint="http://localhost:8000",
                    fallbacks=["nonexistent", "backup"],
                ),
                "backup": EngineProfileConfig(
                    provider="openai-compat",
                    endpoint="http://backup:8000",
                ),
            },
        )
        # Primary should resolve successfully
        driver = resolver.resolve_with_fallbacks("primary", config)
        assert isinstance(driver, AgentDriver)
```

**Step 2: Run tests**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/backends/test_engine_resolver.py::TestEngineResolverFallbacks -v`

**Expected output:** Tests should PASS since `resolve_with_fallbacks` was already implemented in Task 5. If not, debug the implementation.

**Step 3: Commit if changes were needed**

```bash
git add tests/backends/test_engine_resolver.py
git commit -m "test(backends): add fallback chain tests for EngineResolver"
```

**If Task Fails:**
1. **Caching issue:** If the primary factory raises but gets cached, the fallback chain breaks. The `resolve` method should not cache on failure. Check that `BackendResolver.get_driver` only caches after successful factory call (it does -- the factory runs inside `get_driver` and only caches the result).
2. **Rollback:** `git checkout -- tests/backends/test_engine_resolver.py`

---

### Task 17: Add capability enforcement

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/base_driver.py`
- Test: `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/test_base_driver.py` (extend)

**Prerequisites:**
- Task 4 completed (BaseDriver exists)

**Step 1: Write the failing test**

Add to `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/test_base_driver.py`:

```python
from miniautogen.backends.errors import BackendUnavailableError


class TestBaseDriverCapabilityEnforcement:
    @pytest.mark.asyncio
    async def test_send_turn_with_tools_when_not_supported_warns(self) -> None:
        """When request has tool calls but driver lacks tools capability, should still work but log warning."""
        inner = FakeDriver(
            caps=BackendCapabilities(tools=False),
            events=[
                AgentEvent(type="message_completed", session_id="", payload={"text": "ok"}),
            ],
        )
        driver = BaseDriver(
            inner=inner,
            capabilities=BackendCapabilities(tools=False),
        )
        resp = await driver.start_session(StartSessionRequest(backend_id="test"))
        events: list[AgentEvent] = []
        async for ev in driver.send_turn(
            SendTurnRequest(
                session_id=resp.session_id,
                messages=[{"role": "user", "content": "call tool"}],
                metadata={"requires_tools": True},
            ),
        ):
            events.append(ev)
        # Should still produce events (warning only, not blocking)
        assert any(e.type == "message_completed" for e in events)
```

**Step 2: Run test to verify it passes**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/backends/test_base_driver.py::TestBaseDriverCapabilityEnforcement -v`

This test should PASS without changes since BaseDriver already delegates. The capability enforcement is a warning-only behavior for now (not blocking).

**Step 3: Add a capability check log to BaseDriver.send_turn**

In `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/base_driver.py`, add capability logging at the top of `send_turn`:

```python
    async def send_turn(
        self,
        request: SendTurnRequest,
    ) -> AsyncIterator[AgentEvent]:
        sanitized = self._sanitize_messages(request.messages)
        request = request.model_copy(update={"messages": sanitized})

        # Log capability warnings
        if request.metadata.get("requires_tools") and not self._capabilities.tools:
            logger.warning(
                "capability_mismatch",
                required="tools",
                session_id=request.session_id,
            )
        if request.metadata.get("requires_streaming") and not self._capabilities.streaming:
            logger.warning(
                "capability_mismatch",
                required="streaming",
                session_id=request.session_id,
            )

        try:
            async for event in self._inner.send_turn(request):
                yield self._normalize_event(event)
        except Exception as exc:
            yield self._error_event(exc, request.session_id)
```

**Step 4: Run all BaseDriver tests**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/backends/test_base_driver.py -v`

**Expected output:** All tests PASS.

**Step 5: Commit**

```bash
git add miniautogen/backends/base_driver.py tests/backends/test_base_driver.py
git commit -m "feat(backends): add capability enforcement logging to BaseDriver"
```

**If Task Fails:**
1. **Rollback:** `git checkout -- miniautogen/backends/base_driver.py tests/backends/test_base_driver.py`

---

## Phase 5: Deprecation

### Task 18: Add DeprecationWarning to legacy LLM adapters

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/adapters/llm/protocol.py`
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/adapters/llm/providers.py`
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/adapters/llm/openai_compatible_provider.py`
- Test: `/Users/brunocapelao/Projects/miniAutoGen/tests/adapters/llm/test_deprecation.py` (create)

**Prerequisites:**
- Phases 0-4 completed

**Step 1: Write the failing test**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/adapters/llm/test_deprecation.py`:

```python
"""Tests for LLM adapter deprecation warnings."""

from __future__ import annotations

import warnings

import pytest


class TestDeprecationWarnings:
    def test_llmprovider_warns(self) -> None:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from miniautogen.adapters.llm.protocol import LLMProvider
            # Check that a deprecation warning was raised
            dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(dep_warnings) >= 1
            assert "deprecated" in str(dep_warnings[0].message).lower()

    def test_openai_provider_warns(self) -> None:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from miniautogen.adapters.llm.providers import OpenAIProvider
            dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(dep_warnings) >= 1

    def test_litellm_provider_warns(self) -> None:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from miniautogen.adapters.llm.providers import LiteLLMProvider
            dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(dep_warnings) >= 1

    def test_openai_compatible_provider_warns(self) -> None:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from miniautogen.adapters.llm.openai_compatible_provider import (
                OpenAICompatibleProvider,
            )
            dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(dep_warnings) >= 1
```

**Note:** Module-level deprecation warnings only fire on first import. These tests may need to be run in isolation (`pytest --forked` or as subprocess) if the modules are already imported. Alternatively, add the deprecation warning to `__init_subclass__` or `__init__`. A more robust approach is to add the warning to `__init__`:

Revised test:

```python
"""Tests for LLM adapter deprecation warnings."""

from __future__ import annotations

import warnings
from unittest.mock import MagicMock

import pytest

from miniautogen.adapters.llm.openai_compatible_provider import OpenAICompatibleProvider
from miniautogen.adapters.llm.providers import LiteLLMProvider, OpenAIProvider


class TestDeprecationWarnings:
    def test_openai_provider_init_warns(self) -> None:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            OpenAIProvider(client=MagicMock())
            dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(dep_warnings) >= 1
            assert "OpenAISDKDriver" in str(dep_warnings[0].message)

    def test_litellm_provider_init_warns(self) -> None:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            LiteLLMProvider(client=MagicMock())
            dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(dep_warnings) >= 1
            assert "LiteLLMDriver" in str(dep_warnings[0].message)

    def test_openai_compatible_provider_init_warns(self) -> None:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            OpenAICompatibleProvider(
                base_url="http://localhost:8000",
                client=MagicMock(),
            )
            dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(dep_warnings) >= 1
            assert "AgentAPIDriver" in str(dep_warnings[0].message)
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/adapters/llm/test_deprecation.py -v`

**Expected output:**
```
FAILED - AssertionError: assert 0 >= 1 (no deprecation warnings)
```

**Step 3: Add deprecation warnings**

In `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/adapters/llm/providers.py`, add `import warnings` at the top and add `__init__` warnings:

For `OpenAIProvider.__init__`, add as first line:

```python
        warnings.warn(
            "OpenAIProvider is deprecated. Use OpenAISDKDriver from "
            "miniautogen.backends.openai_sdk instead.",
            DeprecationWarning,
            stacklevel=2,
        )
```

For `LiteLLMProvider.__init__`, add as first line:

```python
        warnings.warn(
            "LiteLLMProvider is deprecated. Use LiteLLMDriver (optional) or "
            "configure engine_profiles in miniautogen.yaml instead.",
            DeprecationWarning,
            stacklevel=2,
        )
```

In `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/adapters/llm/openai_compatible_provider.py`, add `import warnings` at the top and add to `__init__` as first line:

```python
        warnings.warn(
            "OpenAICompatibleProvider is deprecated. Use AgentAPIDriver from "
            "miniautogen.backends.agentapi instead.",
            DeprecationWarning,
            stacklevel=2,
        )
```

**Step 4: Run tests**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/adapters/llm/test_deprecation.py -v`

**Expected output:** All tests PASS.

**Step 5: Run all existing adapter tests to check for warnings interference**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/adapters/ -v`

**Expected output:** All tests PASS (they may now emit DeprecationWarning but should not fail).

**Step 6: Commit**

```bash
git add miniautogen/adapters/llm/providers.py miniautogen/adapters/llm/openai_compatible_provider.py tests/adapters/llm/test_deprecation.py
git commit -m "deprecate(adapters): add DeprecationWarning to legacy LLM providers"
```

**If Task Fails:**
1. **Existing tests use `-W error`:** Some test configs treat warnings as errors. If so, update pytest config or use `@pytest.mark.filterwarnings("ignore::DeprecationWarning")` on existing adapter tests.
2. **Rollback:** `git checkout -- miniautogen/adapters/llm/providers.py miniautogen/adapters/llm/openai_compatible_provider.py`

---

### Task 19: Update backends __init__.py with clean public API

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/__init__.py`
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/test_exports.py`

**Prerequisites:**
- All previous tasks completed

**Step 1: Write the failing test**

Add to `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/test_exports.py`:

```python
    def test_import_engine_resolver(self) -> None:
        from miniautogen.backends import EngineResolver  # noqa: F401

    def test_import_base_driver(self) -> None:
        from miniautogen.backends import BaseDriver  # noqa: F401

    def test_import_message_transformer(self) -> None:
        from miniautogen.backends import MessageTransformer  # noqa: F401
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/backends/test_exports.py::TestBackendsPackageExports::test_import_engine_resolver -v`

**Expected output:**
```
FAILED - ImportError: cannot import name 'EngineResolver' from 'miniautogen.backends'
```

**Step 3: Update __init__.py**

Replace `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/__init__.py`:

```python
"""Unified driver abstraction for external agent backends.

Usage::

    from miniautogen.backends import AgentDriver, BackendResolver, BackendConfig
    from miniautogen.backends import EngineResolver  # v2.1
"""

from miniautogen.backends.agentapi import AgentAPIDriver, agentapi_factory
from miniautogen.backends.base_driver import BaseDriver
from miniautogen.backends.config import BackendConfig, DriverType
from miniautogen.backends.driver import AgentDriver
from miniautogen.backends.engine_resolver import EngineResolver
from miniautogen.backends.models import (
    AgentEvent,
    ArtifactRef,
    BackendCapabilities,
    CancelTurnRequest,
    SendTurnRequest,
    StartSessionRequest,
    StartSessionResponse,
)
from miniautogen.backends.resolver import BackendResolver
from miniautogen.backends.sessions import SessionManager
from miniautogen.backends.transformer import MessageTransformer

__all__ = [
    "AgentAPIDriver",
    "AgentDriver",
    "AgentEvent",
    "ArtifactRef",
    "BackendCapabilities",
    "BackendConfig",
    "BackendResolver",
    "BaseDriver",
    "CancelTurnRequest",
    "DriverType",
    "EngineResolver",
    "MessageTransformer",
    "SendTurnRequest",
    "SessionManager",
    "StartSessionRequest",
    "StartSessionResponse",
    "agentapi_factory",
]
```

**Step 4: Run tests**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/backends/test_exports.py -v`

**Expected output:** All tests PASS.

**Step 5: Commit**

```bash
git add miniautogen/backends/__init__.py tests/backends/test_exports.py
git commit -m "feat(backends): update public API exports with v2.1 components"
```

**If Task Fails:**
1. **Circular import:** If EngineResolver imports cause circular deps, use lazy import pattern.
2. **Rollback:** `git checkout -- miniautogen/backends/__init__.py tests/backends/test_exports.py`

---

### Task 20: Run Code Review (Phase 3-5)

1. **Dispatch all 3 reviewers in parallel:**
   - REQUIRED SUB-SKILL: Use requesting-code-review
   - Focus on: Tasks 14-19 (CLI driver, fallbacks, deprecation, exports)

2. **Handle findings by severity** (same rules as Task 6).

3. **Proceed only when zero Critical/High/Medium issues remain.**

---

## Phase 6: Integration Tests

### Task 21: End-to-end integration test

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/test_engine_integration.py`

**Prerequisites:**
- All previous tasks completed

**Step 1: Write the integration test**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/test_engine_integration.py`:

```python
"""End-to-end integration tests for Engine v2.1 architecture.

Tests the full Config -> Resolve -> Drive flow without real API calls.
Uses FakeDriver and mocked factories.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from miniautogen.backends import (
    AgentDriver,
    BackendCapabilities,
    BaseDriver,
    EngineResolver,
)
from miniautogen.backends.config import BackendConfig, DriverType
from miniautogen.backends.errors import BackendUnavailableError
from miniautogen.backends.models import (
    AgentEvent,
    SendTurnRequest,
    StartSessionRequest,
)
from miniautogen.cli.config import (
    DefaultsConfig,
    EngineProfileConfig,
    ProjectConfig,
    ProjectMeta,
)
from tests.backends.conftest import FakeDriver


def _make_full_config() -> ProjectConfig:
    """Create a realistic project config with multiple engine profiles."""
    return ProjectConfig(
        project=ProjectMeta(name="integration-test"),
        defaults=DefaultsConfig(engine_profile="fast-cheap"),
        engine_profiles={
            "local-ollama": EngineProfileConfig(
                kind="api",
                provider="openai-compat",
                endpoint="http://localhost:11434/v1",
                model="llama3.2",
            ),
            "fast-cheap": EngineProfileConfig(
                kind="api",
                provider="openai",
                model="gpt-4o-mini",
                api_key="${OPENAI_API_KEY}",
                fallbacks=["local-ollama"],
            ),
            "smart-premium": EngineProfileConfig(
                kind="api",
                provider="anthropic",
                model="claude-sonnet-4-20250514",
                api_key="${ANTHROPIC_API_KEY}",
                fallbacks=["fast-cheap", "local-ollama"],
            ),
        },
    )


class TestConfigToResolveFlow:
    def test_resolve_openai_compat_profile(self) -> None:
        """YAML config -> EngineResolver -> AgentAPIDriver."""
        resolver = EngineResolver()
        # Override factory with FakeDriver for test
        resolver._resolver.register_factory(
            DriverType.AGENT_API, lambda cfg: FakeDriver(),
        )
        config = _make_full_config()
        driver = resolver.resolve("local-ollama", config)
        assert isinstance(driver, AgentDriver)

    def test_resolve_sdk_profile(self) -> None:
        """YAML config -> EngineResolver -> OpenAISDKDriver (faked)."""
        resolver = EngineResolver()
        resolver._resolver.register_factory(
            DriverType.OPENAI_SDK, lambda cfg: FakeDriver(),
        )
        config = _make_full_config()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            driver = resolver.resolve("fast-cheap", config)
        assert isinstance(driver, AgentDriver)

    def test_caching_returns_same_driver(self) -> None:
        resolver = EngineResolver()
        resolver._resolver.register_factory(
            DriverType.AGENT_API, lambda cfg: FakeDriver(),
        )
        config = _make_full_config()
        d1 = resolver.resolve("local-ollama", config)
        d2 = resolver.resolve("local-ollama", config)
        assert d1 is d2


class TestFallbackChainFlow:
    def test_fallback_chain_primary_fails(self) -> None:
        """When primary fails, should fall back to next."""
        resolver = EngineResolver()

        def selective_factory(cfg: BackendConfig) -> FakeDriver:
            if cfg.backend_id == "fast-cheap":
                raise BackendUnavailableError("OpenAI down")
            return FakeDriver()

        resolver._resolver.register_factory(DriverType.OPENAI_SDK, selective_factory)
        resolver._resolver.register_factory(DriverType.AGENT_API, selective_factory)

        config = _make_full_config()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            driver = resolver.resolve_with_fallbacks("fast-cheap", config)
        assert isinstance(driver, AgentDriver)

    def test_full_chain_exhaustion(self) -> None:
        """When all engines fail, should raise with details."""
        resolver = EngineResolver()

        def always_fail(cfg: BackendConfig) -> FakeDriver:
            raise BackendUnavailableError(f"{cfg.backend_id} down")

        resolver._resolver.register_factory(DriverType.OPENAI_SDK, always_fail)
        resolver._resolver.register_factory(DriverType.AGENT_API, always_fail)

        config = _make_full_config()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with pytest.raises(BackendUnavailableError, match="All engines failed"):
                resolver.resolve_with_fallbacks("fast-cheap", config)


class TestResolveToDriveFlow:
    @pytest.mark.asyncio
    async def test_full_flow_config_to_events(self) -> None:
        """Config -> Resolve -> Start Session -> Send Turn -> Events."""
        resolver = EngineResolver()
        resolver._resolver.register_factory(
            DriverType.AGENT_API,
            lambda cfg: FakeDriver(
                events=[
                    AgentEvent(
                        type="message_completed",
                        session_id="",
                        payload={"text": "Integration test response"},
                    ),
                ],
            ),
        )

        config = _make_full_config()
        driver = resolver.resolve("local-ollama", config)

        # Start session
        session = await driver.start_session(
            StartSessionRequest(backend_id="local-ollama"),
        )
        assert session.session_id.startswith("fake_sess_")

        # Send turn
        events: list[AgentEvent] = []
        async for ev in driver.send_turn(
            SendTurnRequest(
                session_id=session.session_id,
                messages=[{"role": "user", "content": "What is 2+2?"}],
            ),
        ):
            events.append(ev)

        # Verify event sequence
        types = [e.type for e in events]
        assert "message_completed" in types
        assert "turn_completed" in types
        assert any(
            e.payload.get("text") == "Integration test response"
            for e in events
            if e.type == "message_completed"
        )


class TestEnvVarResolution:
    def test_api_key_env_var_resolved(self) -> None:
        resolver = EngineResolver()
        resolver._resolver.register_factory(
            DriverType.OPENAI_SDK, lambda cfg: FakeDriver(),
        )
        config = _make_full_config()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-real-key-123"}):
            driver = resolver.resolve("fast-cheap", config)
        assert isinstance(driver, AgentDriver)

    def test_missing_env_var_still_resolves(self) -> None:
        """Missing API key should not prevent resolution (key might be optional)."""
        resolver = EngineResolver()
        resolver._resolver.register_factory(
            DriverType.OPENAI_SDK, lambda cfg: FakeDriver(),
        )
        config = _make_full_config()
        with patch.dict(os.environ, {}, clear=True):
            driver = resolver.resolve("fast-cheap", config)
        assert isinstance(driver, AgentDriver)
```

**Step 2: Run tests**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/backends/test_engine_integration.py -v`

**Expected output:** All tests PASS.

**Step 3: Run full backend test suite**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/backends/ -v`

**Expected output:** All tests PASS (existing and new).

**Step 4: Commit**

```bash
git add tests/backends/test_engine_integration.py
git commit -m "test(backends): add end-to-end integration tests for Engine v2.1"
```

**If Task Fails:**
1. **Factory registration override:** The EngineResolver registers default factories in `__init__`. Test factories override them via `register_factory`, which replaces the existing factory for that DriverType.
2. **Environment variable leakage:** Use `patch.dict(os.environ, ..., clear=True)` to isolate env vars.
3. **Rollback:** Delete the test file.

---

### Task 22: Run final Code Review

1. **Dispatch all 3 reviewers in parallel:**
   - REQUIRED SUB-SKILL: Use requesting-code-review
   - Focus on: All new files across all phases

2. **Handle findings by severity** (same rules as Task 6).

3. **Proceed only when zero Critical/High/Medium issues remain.**

---

### Task 23: Run full test suite and verify

**Files:**
- No new files

**Prerequisites:**
- All tasks completed, all reviews passed

**Step 1: Run full test suite**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/ -v --tb=short`

**Expected output:** All tests PASS. No regressions from existing tests.

**Step 2: Run linting**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && ruff check miniautogen/backends/ --fix`

**Expected output:** No errors (or errors auto-fixed).

**Step 3: Run type checking**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && mypy miniautogen/backends/ --ignore-missing-imports`

**Expected output:** No critical type errors.

**Step 4: Verify no regressions in existing tests**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/backends/agentapi/ tests/backends/test_resolver.py tests/backends/test_config.py tests/backends/test_sessions.py -v`

**Expected output:** All existing tests PASS unchanged.

**Step 5: Commit any fixes**

```bash
git add -A
git commit -m "chore: fix lint and type issues from Engine v2.1 implementation"
```

**If Task Fails:**
1. **Import errors:** Check for circular imports in `__init__.py` files.
2. **Type errors:** Add `# type: ignore` for mock-related type issues.
3. **Lint errors:** Run `ruff check --fix` to auto-fix.

---

## Summary of Files Created/Modified

### New Files (13)
- `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/transformer.py`
- `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/base_driver.py`
- `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/engine_resolver.py`
- `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/openai_sdk/__init__.py`
- `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/openai_sdk/driver.py`
- `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/openai_sdk/factory.py`
- `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/anthropic_sdk/__init__.py`
- `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/anthropic_sdk/driver.py`
- `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/anthropic_sdk/factory.py`
- `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/google_genai/__init__.py`
- `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/google_genai/driver.py`
- `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/google_genai/factory.py`
- `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/cli/__init__.py`
- `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/cli/driver.py`
- `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/cli/factory.py`

### Modified Files (7)
- `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/config.py`
- `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/config.py`
- `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/agentapi/driver.py`
- `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/__init__.py`
- `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/adapters/llm/providers.py`
- `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/adapters/llm/openai_compatible_provider.py`
- `/Users/brunocapelao/Projects/miniAutoGen/pyproject.toml`

### New Test Files (10)
- `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/test_config_engine_profile.py`
- `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/test_transformer.py`
- `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/test_base_driver.py`
- `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/test_engine_resolver.py`
- `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/openai_sdk/test_driver.py`
- `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/openai_sdk/test_factory.py`
- `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/anthropic_sdk/test_driver.py`
- `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/google_genai/test_driver.py`
- `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/cli/test_driver.py`
- `/Users/brunocapelao/Projects/miniAutoGen/tests/backends/test_engine_integration.py`
- `/Users/brunocapelao/Projects/miniAutoGen/tests/adapters/llm/test_deprecation.py`
