# AgentAPIDriver Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the `AgentAPIDriver` — a thin HTTP client that implements `AgentDriver` and connects to any OpenAI-compatible endpoint (like the existing `gemini_cli_gateway`).

**Architecture:** Three-layer design: `AgentAPIClient` (httpx wrapper with retry, auth, health check), `ResponseMapper` (JSON → AgentEvent conversion), and `AgentAPIDriver` (orchestrates both, implements the ABC). The driver is backend-agnostic — it works with any `/v1/chat/completions` endpoint.

**Tech Stack:** Python 3.11+, httpx, tenacity, anyio, Pydantic v2, pytest + pytest-asyncio

**Design reference:** `docs/plans/2026-03-16-agentapi-driver-design.md`

---

## File Structure

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `miniautogen/backends/agentapi/__init__.py` | Package exports |
| Create | `miniautogen/backends/agentapi/mapper.py` | JSON response → AgentEvent conversion |
| Create | `miniautogen/backends/agentapi/client.py` | HTTP client wrapper (httpx + tenacity) |
| Create | `miniautogen/backends/agentapi/driver.py` | AgentAPIDriver implementation |
| Create | `miniautogen/backends/agentapi/factory.py` | Factory function for BackendResolver |
| Modify | `miniautogen/backends/__init__.py` | Add AgentAPIDriver export |
| Create | `tests/backends/agentapi/__init__.py` | Test package |
| Create | `tests/backends/agentapi/test_mapper.py` | Mapper unit tests |
| Create | `tests/backends/agentapi/test_client.py` | Client unit tests |
| Create | `tests/backends/agentapi/test_driver.py` | Driver tests with mocked client |
| Create | `tests/backends/agentapi/test_driver_contract.py` | Contract test suite for AgentAPIDriver |
| Create | `tests/backends/agentapi/test_factory.py` | Factory + resolver integration tests |

---

## Chunk 1: ResponseMapper

### Task 1: Response Mapper

**Files:**
- Create: `miniautogen/backends/agentapi/mapper.py`
- Create: `tests/backends/agentapi/__init__.py`
- Create: `tests/backends/agentapi/test_mapper.py`

**Context:** The mapper converts OpenAI-compatible JSON responses into canonical `AgentEvent` sequences. It does not touch HTTP — purely data transformation. This makes it independently testable.

- [ ] **Step 1: Write failing tests for mapper**

```python
# tests/backends/agentapi/__init__.py
# (empty)
```

```python
# tests/backends/agentapi/test_mapper.py
"""Tests for OpenAI response → AgentEvent mapper."""

from __future__ import annotations

import pytest

from miniautogen.backends.agentapi.mapper import (
    map_completion_response,
    extract_error_message,
)
from miniautogen.backends.errors import EventMappingError
from miniautogen.backends.models import AgentEvent


class TestMapCompletionResponse:
    def test_standard_response(self) -> None:
        data = {
            "choices": [
                {"message": {"role": "assistant", "content": "Hello world"}}
            ],
        }
        events = map_completion_response(data, session_id="s1", turn_id="t1")
        assert len(events) == 3
        assert events[0].type == "turn_started"
        assert events[0].session_id == "s1"
        assert events[0].turn_id == "t1"
        assert events[1].type == "message_completed"
        assert events[1].payload["text"] == "Hello world"
        assert events[1].payload["role"] == "assistant"
        assert events[2].type == "turn_completed"

    def test_response_with_model_and_usage(self) -> None:
        data = {
            "choices": [
                {"message": {"role": "assistant", "content": "Hi"}}
            ],
            "model": "gemini-2.5-pro",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        events = map_completion_response(data, session_id="s1", turn_id="t1")
        completed = events[2]  # turn_completed
        assert completed.payload.get("model") == "gemini-2.5-pro"
        assert completed.payload.get("usage") == {
            "prompt_tokens": 10, "completion_tokens": 5,
        }

    def test_missing_choices_raises(self) -> None:
        with pytest.raises(EventMappingError, match="choices"):
            map_completion_response({}, session_id="s1", turn_id="t1")

    def test_empty_choices_raises(self) -> None:
        with pytest.raises(EventMappingError, match="choices"):
            map_completion_response(
                {"choices": []}, session_id="s1", turn_id="t1",
            )

    def test_missing_message_content_raises(self) -> None:
        data = {"choices": [{"message": {"role": "assistant"}}]}
        with pytest.raises(EventMappingError, match="content"):
            map_completion_response(data, session_id="s1", turn_id="t1")

    def test_all_events_have_timestamps(self) -> None:
        data = {
            "choices": [
                {"message": {"role": "assistant", "content": "ok"}}
            ],
        }
        events = map_completion_response(data, session_id="s1", turn_id="t1")
        for ev in events:
            assert ev.timestamp is not None


class TestExtractErrorMessage:
    def test_openai_error_format(self) -> None:
        body = {"error": {"message": "Rate limit exceeded"}}
        assert extract_error_message(body) == "Rate limit exceeded"

    def test_detail_format(self) -> None:
        body = {"detail": "Not found"}
        assert extract_error_message(body) == "Not found"

    def test_message_format(self) -> None:
        body = {"message": "Internal error"}
        assert extract_error_message(body) == "Internal error"

    def test_fallback_to_str(self) -> None:
        body = {"unknown": "format"}
        result = extract_error_message(body)
        assert "unknown" in result

    def test_non_dict_body(self) -> None:
        result = extract_error_message("plain text error")
        assert result == "plain text error"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/backends/agentapi/test_mapper.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement mapper**

```python
# miniautogen/backends/agentapi/__init__.py
"""AgentAPI driver — HTTP bridge for OpenAI-compatible endpoints."""
```

```python
# miniautogen/backends/agentapi/mapper.py
"""Convert OpenAI-compatible JSON responses to canonical AgentEvent sequences.

This module handles data transformation only — no HTTP logic.
Structured with separate functions to support future streaming (SSE).
"""

from __future__ import annotations

from typing import Any

from miniautogen.backends.errors import EventMappingError
from miniautogen.backends.models import AgentEvent


def map_completion_response(
    response_data: dict[str, Any],
    session_id: str,
    turn_id: str,
) -> list[AgentEvent]:
    """Convert a non-streaming chat completion response to canonical events.

    Returns: [turn_started, message_completed, turn_completed]

    Raises EventMappingError if the response is malformed.
    """
    choices = response_data.get("choices")
    if not choices:
        msg = "Response missing 'choices' or choices is empty"
        raise EventMappingError(msg)

    first_choice = choices[0]
    message = first_choice.get("message", {})
    content = message.get("content")
    if content is None:
        msg = "Response missing 'content' in first choice message"
        raise EventMappingError(msg)

    role = message.get("role", "assistant")
    model = response_data.get("model")
    usage = response_data.get("usage")

    turn_completed_payload: dict[str, Any] = {}
    if model:
        turn_completed_payload["model"] = model
    if usage:
        turn_completed_payload["usage"] = usage

    return [
        AgentEvent(
            type="turn_started",
            session_id=session_id,
            turn_id=turn_id,
        ),
        AgentEvent(
            type="message_completed",
            session_id=session_id,
            turn_id=turn_id,
            payload={"text": content, "role": role},
        ),
        AgentEvent(
            type="turn_completed",
            session_id=session_id,
            turn_id=turn_id,
            payload=turn_completed_payload,
        ),
    ]


def extract_error_message(body: Any) -> str:
    """Extract a human-readable error message from an HTTP error response body.

    Tries common formats: OpenAI (error.message), FastAPI (detail), generic (message).
    Falls back to str(body).
    """
    if not isinstance(body, dict):
        return str(body)

    error = body.get("error")
    if isinstance(error, dict) and "message" in error:
        return error["message"]

    if "detail" in body:
        return str(body["detail"])

    if "message" in body:
        return str(body["message"])

    return str(body)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/backends/agentapi/test_mapper.py -v`
Expected: PASS (12 tests)

- [ ] **Step 5: Commit**

```bash
git add miniautogen/backends/agentapi/__init__.py \
  miniautogen/backends/agentapi/mapper.py \
  tests/backends/agentapi/__init__.py \
  tests/backends/agentapi/test_mapper.py
git commit -m "feat(agentapi): add response mapper for OpenAI-compatible responses"
```

---

## Chunk 2: HTTP Client

### Task 2: AgentAPIClient

**Files:**
- Create: `miniautogen/backends/agentapi/client.py`
- Create: `tests/backends/agentapi/test_client.py`

**Context:** The client wraps `httpx.AsyncClient` with retry (via tenacity), auth, configurable health check, and structured error extraction. Uses `httpx.MockTransport` in tests for deterministic HTTP simulation.

- [ ] **Step 1: Write failing tests**

```python
# tests/backends/agentapi/test_client.py
"""Tests for AgentAPIClient — HTTP wrapper with retry, auth, health check."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from miniautogen.backends.agentapi.client import AgentAPIClient
from miniautogen.backends.errors import BackendUnavailableError, TurnExecutionError


def _make_transport(
    handler: Any,
) -> httpx.MockTransport:
    """Create a mock transport from a handler function."""
    return httpx.MockTransport(handler)


def _success_handler(request: httpx.Request) -> httpx.Response:
    """Simulate a successful chat completion."""
    if request.url.path == "/health":
        return httpx.Response(200, json={"status": "ok"})
    return httpx.Response(200, json={
        "choices": [{"message": {"role": "assistant", "content": "Hello"}}],
        "model": "test-model",
    })


def _error_handler_500(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/health":
        return httpx.Response(200, json={"status": "ok"})
    return httpx.Response(500, json={"error": {"message": "Internal error"}})


def _error_handler_401(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/health":
        return httpx.Response(200, json={"status": "ok"})
    return httpx.Response(401, json={"detail": "Unauthorized"})


def _health_fail_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(503, text="Service Unavailable")


class TestAgentAPIClient:
    @pytest.mark.asyncio
    async def test_chat_completion_success(self) -> None:
        client = AgentAPIClient(
            base_url="http://fake",
            transport=_make_transport(_success_handler),
            max_retry_attempts=1,
        )
        result = await client.chat_completion(
            messages=[{"role": "user", "content": "hi"}],
        )
        assert result["choices"][0]["message"]["content"] == "Hello"
        await client.close()

    @pytest.mark.asyncio
    async def test_chat_completion_with_model(self) -> None:
        client = AgentAPIClient(
            base_url="http://fake",
            transport=_make_transport(_success_handler),
            max_retry_attempts=1,
        )
        result = await client.chat_completion(
            messages=[{"role": "user", "content": "hi"}],
            model="gemini-2.5-pro",
        )
        assert result["model"] == "test-model"
        await client.close()

    @pytest.mark.asyncio
    async def test_auth_header_sent(self) -> None:
        received_headers: dict[str, str] = {}

        def capture_handler(request: httpx.Request) -> httpx.Response:
            received_headers.update(dict(request.headers))
            return httpx.Response(200, json={
                "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            })

        client = AgentAPIClient(
            base_url="http://fake",
            api_key="test-secret",
            transport=_make_transport(capture_handler),
            max_retry_attempts=1,
        )
        await client.chat_completion(messages=[{"role": "user", "content": "hi"}])
        assert received_headers.get("authorization") == "Bearer test-secret"
        await client.close()

    @pytest.mark.asyncio
    async def test_no_auth_header_when_no_key(self) -> None:
        received_headers: dict[str, str] = {}

        def capture_handler(request: httpx.Request) -> httpx.Response:
            received_headers.update(dict(request.headers))
            return httpx.Response(200, json={
                "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            })

        client = AgentAPIClient(
            base_url="http://fake",
            transport=_make_transport(capture_handler),
            max_retry_attempts=1,
        )
        await client.chat_completion(messages=[{"role": "user", "content": "hi"}])
        assert "authorization" not in received_headers
        await client.close()

    @pytest.mark.asyncio
    async def test_server_error_raises_turn_execution(self) -> None:
        client = AgentAPIClient(
            base_url="http://fake",
            transport=_make_transport(_error_handler_500),
            max_retry_attempts=1,
        )
        with pytest.raises(TurnExecutionError, match="Internal error"):
            await client.chat_completion(
                messages=[{"role": "user", "content": "hi"}],
            )
        await client.close()

    @pytest.mark.asyncio
    async def test_client_error_raises_turn_execution(self) -> None:
        client = AgentAPIClient(
            base_url="http://fake",
            transport=_make_transport(_error_handler_401),
            max_retry_attempts=1,
        )
        with pytest.raises(TurnExecutionError, match="Unauthorized"):
            await client.chat_completion(
                messages=[{"role": "user", "content": "hi"}],
            )
        await client.close()

    @pytest.mark.asyncio
    async def test_health_check_success(self) -> None:
        client = AgentAPIClient(
            base_url="http://fake",
            transport=_make_transport(_success_handler),
            health_endpoint="/health",
        )
        result = await client.health_check()
        assert result is True
        await client.close()

    @pytest.mark.asyncio
    async def test_health_check_failure(self) -> None:
        client = AgentAPIClient(
            base_url="http://fake",
            transport=_make_transport(_health_fail_handler),
            health_endpoint="/health",
        )
        with pytest.raises(BackendUnavailableError):
            await client.health_check()
        await client.close()

    @pytest.mark.asyncio
    async def test_health_check_disabled(self) -> None:
        client = AgentAPIClient(
            base_url="http://fake",
            transport=_make_transport(_success_handler),
            health_endpoint=None,
        )
        result = await client.health_check()
        assert result is True
        await client.close()

    @pytest.mark.asyncio
    async def test_retry_on_server_error(self) -> None:
        call_count = 0

        def flaky_handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return httpx.Response(500, json={"error": {"message": "retry"}})
            return httpx.Response(200, json={
                "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            })

        client = AgentAPIClient(
            base_url="http://fake",
            transport=_make_transport(flaky_handler),
            max_retry_attempts=3,
            retry_delay=0.01,
        )
        result = await client.chat_completion(
            messages=[{"role": "user", "content": "hi"}],
        )
        assert result["choices"][0]["message"]["content"] == "ok"
        assert call_count == 3
        await client.close()

    @pytest.mark.asyncio
    async def test_no_retry_on_client_error(self) -> None:
        call_count = 0

        def client_error_handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(400, json={"detail": "Bad request"})

        client = AgentAPIClient(
            base_url="http://fake",
            transport=_make_transport(client_error_handler),
            max_retry_attempts=3,
            retry_delay=0.01,
        )
        with pytest.raises(TurnExecutionError):
            await client.chat_completion(
                messages=[{"role": "user", "content": "hi"}],
            )
        assert call_count == 1
        await client.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/backends/agentapi/test_client.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement AgentAPIClient**

```python
# miniautogen/backends/agentapi/client.py
"""HTTP client wrapper for OpenAI-compatible endpoints.

Handles auth, retry, health check, timeout, and error extraction.
Uses httpx for async HTTP and tenacity for retry logic.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_fixed,
)

from miniautogen.backends.agentapi.mapper import extract_error_message
from miniautogen.backends.errors import BackendUnavailableError, TurnExecutionError


class _RetryableServerError(Exception):
    """Internal: raised on 5xx to trigger tenacity retry."""


class AgentAPIClient:
    """Async HTTP client for OpenAI-compatible chat completion endpoints."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout_seconds: float = 60.0,
        connect_timeout: float = 10.0,
        health_endpoint: str | None = "/health",
        max_retry_attempts: int = 3,
        retry_delay: float = 1.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._health_endpoint = health_endpoint
        self._max_retry_attempts = max_retry_attempts
        self._retry_delay = retry_delay

        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        client_kwargs: dict[str, Any] = {
            "base_url": self._base_url,
            "headers": headers,
            "timeout": httpx.Timeout(timeout_seconds, connect=connect_timeout),
        }
        if transport is not None:
            client_kwargs["transport"] = transport

        self._client = httpx.AsyncClient(**client_kwargs)

    async def health_check(self) -> bool:
        """Check backend availability.

        Returns True if healthy or health check is disabled.
        Raises BackendUnavailableError if unhealthy.
        """
        if self._health_endpoint is None:
            return True

        try:
            resp = await self._client.get(self._health_endpoint)
            if resp.status_code >= 400:
                msg = f"Health check failed: HTTP {resp.status_code}"
                raise BackendUnavailableError(msg)
            return True
        except httpx.ConnectError as exc:
            msg = f"Backend unreachable: {exc}"
            raise BackendUnavailableError(msg) from exc
        except httpx.TimeoutException as exc:
            msg = f"Health check timed out: {exc}"
            raise BackendUnavailableError(msg) from exc

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
    ) -> dict[str, Any]:
        """Send a chat completion request.

        Retries on 5xx errors. Raises TurnExecutionError on failure.
        """
        payload: dict[str, Any] = {"messages": messages}
        if model:
            payload["model"] = model

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self._max_retry_attempts),
                wait=wait_fixed(self._retry_delay),
                retry=retry_if_exception_type(_RetryableServerError),
                reraise=True,
            ):
                with attempt:
                    resp = await self._client.post(
                        "/v1/chat/completions",
                        json=payload,
                    )
                    if resp.status_code >= 500:
                        body = self._try_parse_json(resp)
                        err_msg = extract_error_message(body)
                        raise _RetryableServerError(err_msg)
                    if resp.status_code >= 400:
                        body = self._try_parse_json(resp)
                        err_msg = extract_error_message(body)
                        msg = f"HTTP {resp.status_code}: {err_msg}"
                        raise TurnExecutionError(msg)

                    return resp.json()

        except _RetryableServerError as exc:
            msg = f"Server error after {self._max_retry_attempts} attempts: {exc}"
            raise TurnExecutionError(msg) from exc
        except httpx.ConnectError as exc:
            msg = f"Backend unreachable: {exc}"
            raise BackendUnavailableError(msg) from exc
        except httpx.TimeoutException as exc:
            msg = f"Request timed out: {exc}"
            raise TurnExecutionError(msg) from exc

        # Unreachable, but satisfies type checker
        msg = "Unexpected state in chat_completion"
        raise TurnExecutionError(msg)

    @staticmethod
    def _try_parse_json(resp: httpx.Response) -> Any:
        try:
            return resp.json()
        except Exception:
            return resp.text[:500]

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/backends/agentapi/test_client.py -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Commit**

```bash
git add miniautogen/backends/agentapi/client.py \
  tests/backends/agentapi/test_client.py
git commit -m "feat(agentapi): add HTTP client with retry, auth, and health check"
```

---

## Chunk 3: Driver + Contract Tests

### Task 3: AgentAPIDriver

**Files:**
- Create: `miniautogen/backends/agentapi/driver.py`
- Create: `tests/backends/agentapi/test_driver.py`

**Context:** The driver orchestrates `AgentAPIClient` and `map_completion_response`. It implements the `AgentDriver` ABC. `send_turn` is declared `async def` + `yield` (async generator) per D1.

- [ ] **Step 1: Write failing tests**

```python
# tests/backends/agentapi/test_driver.py
"""Tests for AgentAPIDriver with mocked client."""

from __future__ import annotations

from typing import Any, AsyncIterator
from unittest.mock import AsyncMock

import pytest

from miniautogen.backends.agentapi.client import AgentAPIClient
from miniautogen.backends.agentapi.driver import AgentAPIDriver
from miniautogen.backends.errors import (
    BackendUnavailableError,
    CancelNotSupportedError,
    TurnExecutionError,
)
from miniautogen.backends.models import (
    AgentEvent,
    BackendCapabilities,
    SendTurnRequest,
    StartSessionRequest,
)


@pytest.fixture
def mock_client() -> AsyncMock:
    client = AsyncMock(spec=AgentAPIClient)
    client.health_check = AsyncMock(return_value=True)
    client.chat_completion = AsyncMock(return_value={
        "choices": [{"message": {"role": "assistant", "content": "Hello"}}],
        "model": "test-model",
    })
    client.close = AsyncMock()
    return client


@pytest.fixture
def driver(mock_client: AsyncMock) -> AgentAPIDriver:
    return AgentAPIDriver(client=mock_client)


class TestAgentAPIDriverStartSession:
    @pytest.mark.asyncio
    async def test_returns_session_id(self, driver: AgentAPIDriver) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="test"),
        )
        assert resp.session_id.startswith("sess_")

    @pytest.mark.asyncio
    async def test_capabilities_no_streaming(
        self, driver: AgentAPIDriver,
    ) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="test"),
        )
        assert resp.capabilities.streaming is False
        assert resp.capabilities.sessions is False
        assert resp.capabilities.cancel is False

    @pytest.mark.asyncio
    async def test_health_check_called(
        self, driver: AgentAPIDriver, mock_client: AsyncMock,
    ) -> None:
        await driver.start_session(StartSessionRequest(backend_id="test"))
        mock_client.health_check.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_health_check_failure_raises(
        self, mock_client: AsyncMock,
    ) -> None:
        mock_client.health_check = AsyncMock(
            side_effect=BackendUnavailableError("down"),
        )
        driver = AgentAPIDriver(client=mock_client)
        with pytest.raises(BackendUnavailableError):
            await driver.start_session(
                StartSessionRequest(backend_id="test"),
            )


class TestAgentAPIDriverSendTurn:
    @pytest.mark.asyncio
    async def test_yields_event_sequence(
        self, driver: AgentAPIDriver,
    ) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="test"),
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
        assert events[1].payload["text"] == "Hello"
        assert events[2].type == "turn_completed"

    @pytest.mark.asyncio
    async def test_events_have_session_and_turn_ids(
        self, driver: AgentAPIDriver,
    ) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="test"),
        )
        async for ev in driver.send_turn(
            SendTurnRequest(
                session_id=resp.session_id,
                messages=[{"role": "user", "content": "hi"}],
            ),
        ):
            assert ev.session_id == resp.session_id
            assert ev.turn_id is not None

    @pytest.mark.asyncio
    async def test_client_error_propagates(
        self, mock_client: AsyncMock,
    ) -> None:
        mock_client.chat_completion = AsyncMock(
            side_effect=TurnExecutionError("HTTP 500"),
        )
        driver = AgentAPIDriver(client=mock_client)
        resp = await driver.start_session(
            StartSessionRequest(backend_id="test"),
        )
        with pytest.raises(TurnExecutionError):
            async for _ in driver.send_turn(
                SendTurnRequest(
                    session_id=resp.session_id,
                    messages=[{"role": "user", "content": "hi"}],
                ),
            ):
                pass

    @pytest.mark.asyncio
    async def test_model_passed_to_client(
        self, driver: AgentAPIDriver, mock_client: AsyncMock,
    ) -> None:
        driver = AgentAPIDriver(client=mock_client, model="gemini-2.5-pro")
        resp = await driver.start_session(
            StartSessionRequest(backend_id="test"),
        )
        async for _ in driver.send_turn(
            SendTurnRequest(
                session_id=resp.session_id,
                messages=[{"role": "user", "content": "hi"}],
            ),
        ):
            pass
        _, kwargs = mock_client.chat_completion.call_args
        assert kwargs.get("model") == "gemini-2.5-pro"


class TestAgentAPIDriverOtherMethods:
    @pytest.mark.asyncio
    async def test_cancel_raises(self, driver: AgentAPIDriver) -> None:
        from miniautogen.backends.models import CancelTurnRequest

        with pytest.raises(CancelNotSupportedError):
            await driver.cancel_turn(CancelTurnRequest(session_id="s1"))

    @pytest.mark.asyncio
    async def test_list_artifacts_empty(self, driver: AgentAPIDriver) -> None:
        result = await driver.list_artifacts("s1")
        assert result == []

    @pytest.mark.asyncio
    async def test_close_session_noop(self, driver: AgentAPIDriver) -> None:
        await driver.close_session("s1")

    @pytest.mark.asyncio
    async def test_capabilities(self, driver: AgentAPIDriver) -> None:
        caps = await driver.capabilities()
        assert isinstance(caps, BackendCapabilities)
        assert caps.streaming is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/backends/agentapi/test_driver.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement AgentAPIDriver**

```python
# miniautogen/backends/agentapi/driver.py
"""AgentAPIDriver — HTTP bridge implementing the AgentDriver contract.

Connects to any OpenAI-compatible endpoint (/v1/chat/completions).
Uses AgentAPIClient for HTTP and ResponseMapper for event conversion.
"""

from __future__ import annotations

import uuid
from typing import AsyncIterator

from miniautogen.backends.agentapi.client import AgentAPIClient
from miniautogen.backends.agentapi.mapper import map_completion_response
from miniautogen.backends.driver import AgentDriver
from miniautogen.backends.errors import CancelNotSupportedError
from miniautogen.backends.models import (
    AgentEvent,
    ArtifactRef,
    BackendCapabilities,
    CancelTurnRequest,
    SendTurnRequest,
    StartSessionRequest,
    StartSessionResponse,
)


class AgentAPIDriver(AgentDriver):
    """Driver for OpenAI-compatible HTTP endpoints.

    Works with any /v1/chat/completions backend: gemini_cli_gateway,
    LiteLLM proxy, vLLM, Ollama, etc.

    send_turn uses ``async def`` + ``yield`` (async generator),
    satisfying the ABC's ``def -> AsyncIterator`` contract (D1).
    """

    def __init__(
        self,
        client: AgentAPIClient,
        model: str | None = None,
    ) -> None:
        self._client = client
        self._model = model
        self._caps = BackendCapabilities(
            sessions=False,
            streaming=False,
            cancel=False,
            resume=False,
            tools=False,
            artifacts=False,
            multimodal=False,
        )

    async def start_session(
        self,
        request: StartSessionRequest,
    ) -> StartSessionResponse:
        await self._client.health_check()
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        return StartSessionResponse(
            session_id=session_id,
            capabilities=self._caps,
        )

    async def send_turn(
        self,
        request: SendTurnRequest,
    ) -> AsyncIterator[AgentEvent]:
        turn_id = f"turn_{uuid.uuid4().hex[:12]}"
        response_data = await self._client.chat_completion(
            messages=request.messages,
            model=self._model,
        )
        events = map_completion_response(
            response_data,
            session_id=request.session_id,
            turn_id=turn_id,
        )
        for event in events:
            yield event

    async def cancel_turn(
        self,
        request: CancelTurnRequest,
    ) -> None:
        raise CancelNotSupportedError(
            "AgentAPIDriver does not support cancellation"
        )

    async def list_artifacts(self, session_id: str) -> list[ArtifactRef]:
        return []

    async def close_session(self, session_id: str) -> None:
        pass

    async def capabilities(self) -> BackendCapabilities:
        return self._caps
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/backends/agentapi/test_driver.py -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Commit**

```bash
git add miniautogen/backends/agentapi/driver.py \
  tests/backends/agentapi/test_driver.py
git commit -m "feat(agentapi): add AgentAPIDriver implementing AgentDriver ABC"
```

---

### Task 4: Contract Test Suite for AgentAPIDriver

**Files:**
- Create: `tests/backends/agentapi/test_driver_contract.py`

**Context:** Parametrize the existing contract test suite to also run against `AgentAPIDriver`. This proves it satisfies the same contract as `FakeDriver`. Uses `httpx.MockTransport` to simulate the HTTP backend.

- [ ] **Step 1: Write contract tests**

```python
# tests/backends/agentapi/test_driver_contract.py
"""Contract test suite for AgentAPIDriver.

Runs the same contract tests that FakeDriver passes, proving
AgentAPIDriver satisfies the AgentDriver contract.
"""

from __future__ import annotations

import httpx
import pytest

from miniautogen.backends.agentapi.client import AgentAPIClient
from miniautogen.backends.agentapi.driver import AgentAPIDriver
from miniautogen.backends.driver import AgentDriver
from miniautogen.backends.errors import CancelNotSupportedError
from miniautogen.backends.models import (
    AgentEvent,
    BackendCapabilities,
    CancelTurnRequest,
    SendTurnRequest,
    StartSessionRequest,
)


def _mock_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/health":
        return httpx.Response(200, json={"status": "ok"})
    return httpx.Response(200, json={
        "choices": [{"message": {"role": "assistant", "content": "contract test"}}],
        "model": "test",
    })


@pytest.fixture
def driver() -> AgentDriver:
    client = AgentAPIClient(
        base_url="http://fake",
        transport=httpx.MockTransport(_mock_handler),
        max_retry_attempts=1,
    )
    return AgentAPIDriver(client=client)


class TestAgentAPIDriverContract:
    """Same contract tests from test_driver_contract.py."""

    @pytest.mark.asyncio
    async def test_start_session_returns_valid_response(
        self, driver: AgentDriver,
    ) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="test"),
        )
        assert resp.session_id
        assert isinstance(resp.capabilities, BackendCapabilities)

    @pytest.mark.asyncio
    async def test_send_turn_yields_events(
        self, driver: AgentDriver,
    ) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="test"),
        )
        events: list[AgentEvent] = []
        async for ev in driver.send_turn(
            SendTurnRequest(
                session_id=resp.session_id,
                messages=[{"role": "user", "content": "hello"}],
            ),
        ):
            events.append(ev)
        assert len(events) >= 1
        assert all(isinstance(e, AgentEvent) for e in events)
        assert all(e.session_id == resp.session_id for e in events)

    @pytest.mark.asyncio
    async def test_send_turn_ends_with_turn_completed(
        self, driver: AgentDriver,
    ) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="test"),
        )
        events: list[AgentEvent] = []
        async for ev in driver.send_turn(
            SendTurnRequest(
                session_id=resp.session_id,
                messages=[{"role": "user", "content": "hello"}],
            ),
        ):
            events.append(ev)
        assert events[-1].type == "turn_completed"

    @pytest.mark.asyncio
    async def test_list_artifacts_returns_list(
        self, driver: AgentDriver,
    ) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="test"),
        )
        artifacts = await driver.list_artifacts(resp.session_id)
        assert isinstance(artifacts, list)

    @pytest.mark.asyncio
    async def test_close_session_completes(
        self, driver: AgentDriver,
    ) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="test"),
        )
        await driver.close_session(resp.session_id)

    @pytest.mark.asyncio
    async def test_capabilities_returns_valid_object(
        self, driver: AgentDriver,
    ) -> None:
        caps = await driver.capabilities()
        assert isinstance(caps, BackendCapabilities)

    @pytest.mark.asyncio
    async def test_cancel_raises_not_supported(
        self, driver: AgentDriver,
    ) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="test"),
        )
        with pytest.raises(CancelNotSupportedError):
            await driver.cancel_turn(
                CancelTurnRequest(session_id=resp.session_id),
            )

    @pytest.mark.asyncio
    async def test_events_have_timestamps(
        self, driver: AgentDriver,
    ) -> None:
        resp = await driver.start_session(
            StartSessionRequest(backend_id="test"),
        )
        async for ev in driver.send_turn(
            SendTurnRequest(
                session_id=resp.session_id,
                messages=[{"role": "user", "content": "ts"}],
            ),
        ):
            assert ev.timestamp is not None
```

- [ ] **Step 2: Run contract tests**

Run: `python -m pytest tests/backends/agentapi/test_driver_contract.py -v`
Expected: PASS (8 tests)

- [ ] **Step 3: Commit**

```bash
git add tests/backends/agentapi/test_driver_contract.py
git commit -m "test(agentapi): add contract test suite for AgentAPIDriver"
```

---

## Chunk 4: Factory + Exports

### Task 5: Factory + Resolver Integration

**Files:**
- Create: `miniautogen/backends/agentapi/factory.py`
- Create: `tests/backends/agentapi/test_factory.py`

**Context:** The factory function creates an `AgentAPIDriver` from a `BackendConfig`. It resolves auth (reading API key from env var), extracts metadata params, and constructs the client. Integrates with `BackendResolver`.

- [ ] **Step 1: Write failing tests**

```python
# tests/backends/agentapi/test_factory.py
"""Tests for AgentAPIDriver factory and resolver integration."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from miniautogen.backends.agentapi.driver import AgentAPIDriver
from miniautogen.backends.agentapi.factory import agentapi_factory
from miniautogen.backends.config import AuthConfig, BackendConfig, DriverType
from miniautogen.backends.resolver import BackendResolver


class TestAgentAPIFactory:
    def test_creates_driver_from_config(self) -> None:
        config = BackendConfig(
            backend_id="test",
            driver=DriverType.AGENT_API,
            endpoint="http://localhost:8000",
        )
        driver = agentapi_factory(config)
        assert isinstance(driver, AgentAPIDriver)

    def test_extracts_model_from_metadata(self) -> None:
        config = BackendConfig(
            backend_id="test",
            driver=DriverType.AGENT_API,
            endpoint="http://localhost:8000",
            metadata={"model": "gemini-2.5-pro"},
        )
        driver = agentapi_factory(config)
        assert driver._model == "gemini-2.5-pro"

    def test_disables_health_check_from_metadata(self) -> None:
        config = BackendConfig(
            backend_id="test",
            driver=DriverType.AGENT_API,
            endpoint="http://localhost:8000",
            metadata={"health_endpoint": None},
        )
        driver = agentapi_factory(config)
        assert driver._client._health_endpoint is None

    @patch.dict(os.environ, {"MY_TOKEN": "secret-123"})
    def test_resolves_api_key_from_env(self) -> None:
        config = BackendConfig(
            backend_id="test",
            driver=DriverType.AGENT_API,
            endpoint="http://localhost:8000",
            auth=AuthConfig(type="bearer", token_env="MY_TOKEN"),
        )
        driver = agentapi_factory(config)
        assert "authorization" in driver._client._client.headers
        assert driver._client._client.headers["authorization"] == "Bearer secret-123"

    def test_no_auth_when_type_none(self) -> None:
        config = BackendConfig(
            backend_id="test",
            driver=DriverType.AGENT_API,
            endpoint="http://localhost:8000",
            auth=AuthConfig(type="none"),
        )
        driver = agentapi_factory(config)
        assert "authorization" not in driver._client._client.headers

    def test_timeout_from_config(self) -> None:
        config = BackendConfig(
            backend_id="test",
            driver=DriverType.AGENT_API,
            endpoint="http://localhost:8000",
            timeout_seconds=30.0,
        )
        driver = agentapi_factory(config)
        # httpx stores timeout as Timeout object
        assert driver._client._client.timeout.read == 30.0


class TestResolverIntegration:
    def test_register_and_resolve(self) -> None:
        resolver = BackendResolver()
        resolver.register_factory(DriverType.AGENT_API, agentapi_factory)
        resolver.add_backend(
            BackendConfig(
                backend_id="gemini",
                driver=DriverType.AGENT_API,
                endpoint="http://localhost:8000",
            ),
        )
        driver = resolver.get_driver("gemini")
        assert isinstance(driver, AgentAPIDriver)

    def test_driver_is_cached(self) -> None:
        resolver = BackendResolver()
        resolver.register_factory(DriverType.AGENT_API, agentapi_factory)
        resolver.add_backend(
            BackendConfig(
                backend_id="gemini",
                driver=DriverType.AGENT_API,
                endpoint="http://localhost:8000",
            ),
        )
        d1 = resolver.get_driver("gemini")
        d2 = resolver.get_driver("gemini")
        assert d1 is d2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/backends/agentapi/test_factory.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement factory**

```python
# miniautogen/backends/agentapi/factory.py
"""Factory function for creating AgentAPIDriver from BackendConfig.

Resolves auth, extracts metadata params, and constructs the client.
Register with BackendResolver via:
    resolver.register_factory(DriverType.AGENT_API, agentapi_factory)
"""

from __future__ import annotations

import os

from miniautogen.backends.agentapi.client import AgentAPIClient
from miniautogen.backends.agentapi.driver import AgentAPIDriver
from miniautogen.backends.config import BackendConfig


def agentapi_factory(config: BackendConfig) -> AgentAPIDriver:
    """Create an AgentAPIDriver from declarative config."""
    api_key: str | None = None
    if config.auth and config.auth.type == "bearer" and config.auth.token_env:
        api_key = os.environ.get(config.auth.token_env)

    metadata = config.metadata
    health_ep = metadata.get("health_endpoint", "/health")

    client = AgentAPIClient(
        base_url=config.endpoint,  # type: ignore[arg-type]
        api_key=api_key,
        timeout_seconds=config.timeout_seconds,
        connect_timeout=metadata.get("connect_timeout", 10.0),
        health_endpoint=health_ep,
        max_retry_attempts=metadata.get("max_retry_attempts", 3),
        retry_delay=metadata.get("retry_delay", 1.0),
    )

    return AgentAPIDriver(
        client=client,
        model=metadata.get("model"),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/backends/agentapi/test_factory.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add miniautogen/backends/agentapi/factory.py \
  tests/backends/agentapi/test_factory.py
git commit -m "feat(agentapi): add factory for resolver integration"
```

---

### Task 6: Package Exports

**Files:**
- Modify: `miniautogen/backends/agentapi/__init__.py`
- Modify: `miniautogen/backends/__init__.py`

- [ ] **Step 1: Update agentapi package exports**

```python
# miniautogen/backends/agentapi/__init__.py
"""AgentAPI driver — HTTP bridge for OpenAI-compatible endpoints."""

from miniautogen.backends.agentapi.client import AgentAPIClient
from miniautogen.backends.agentapi.driver import AgentAPIDriver
from miniautogen.backends.agentapi.factory import agentapi_factory

__all__ = [
    "AgentAPIClient",
    "AgentAPIDriver",
    "agentapi_factory",
]
```

- [ ] **Step 2: Add AgentAPIDriver to backends package exports**

Add to `miniautogen/backends/__init__.py` — add import and `__all__` entry:

```python
from miniautogen.backends.agentapi import AgentAPIDriver, agentapi_factory
```

And add to `__all__`:

```python
    "AgentAPIDriver",
    "agentapi_factory",
```

- [ ] **Step 3: Verify imports work**

Run: `python -c "from miniautogen.backends import AgentAPIDriver, agentapi_factory; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Run full test suite**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All tests PASS (pre-existing + new)

- [ ] **Step 5: Commit**

```bash
git add miniautogen/backends/agentapi/__init__.py \
  miniautogen/backends/__init__.py
git commit -m "feat(agentapi): wire up package exports"
```

---

## Summary

| Task | What | Tests |
|------|------|-------|
| 1 | ResponseMapper (JSON → AgentEvent) | 12 |
| 2 | AgentAPIClient (httpx + retry + auth + health) | 11 |
| 3 | AgentAPIDriver (orchestrates client + mapper) | 11 |
| 4 | Contract test suite (proves ABC compliance) | 8 |
| 5 | Factory + resolver integration | 8 |
| 6 | Package exports | — |

**Total: 6 tasks, ~50 tests**
