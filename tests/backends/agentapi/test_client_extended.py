"""Extended tests for AgentAPIClient — covering uncovered lines.

Targets:
  - Lines 80-82: health_check ConnectError
  - Lines 84-86: health_check TimeoutException
  - Lines 134-136: chat_completion ConnectError
  - Lines 138-144: chat_completion TimeoutException + unreachable fallback
  - Lines 150-151: _try_parse_json fallback (non-JSON body)
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from miniautogen.backends.agentapi.client import AgentAPIClient
from miniautogen.backends.errors import BackendUnavailableError, TurnExecutionError


def _make_transport(handler: Any) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


# ---------------------------------------------------------------------------
# Health check — ConnectError and Timeout (lines 79-86)
# ---------------------------------------------------------------------------


class TestHealthCheckErrors:
    @pytest.mark.asyncio
    async def test_health_check_connect_error(self) -> None:
        """Covers lines 79-82: ConnectError during health check."""

        def raise_connect(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        client = AgentAPIClient(
            base_url="http://fake",
            transport=_make_transport(raise_connect),
            health_endpoint="/health",
        )
        with pytest.raises(BackendUnavailableError, match="unreachable"):
            await client.health_check()
        await client.close()

    @pytest.mark.asyncio
    async def test_health_check_timeout(self) -> None:
        """Covers lines 83-86: TimeoutException during health check."""

        def raise_timeout(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("read timed out")

        client = AgentAPIClient(
            base_url="http://fake",
            transport=_make_transport(raise_timeout),
            health_endpoint="/health",
        )
        with pytest.raises(BackendUnavailableError, match="timed out"):
            await client.health_check()
        await client.close()


# ---------------------------------------------------------------------------
# Chat completion — ConnectError and Timeout (lines 133-144)
# ---------------------------------------------------------------------------


class TestChatCompletionNetworkErrors:
    @pytest.mark.asyncio
    async def test_connect_error_raises_backend_unavailable(self) -> None:
        """Covers lines 133-136: ConnectError during chat_completion."""

        def raise_connect(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        client = AgentAPIClient(
            base_url="http://fake",
            transport=_make_transport(raise_connect),
            max_retry_attempts=1,
        )
        with pytest.raises(BackendUnavailableError, match="unreachable"):
            await client.chat_completion(
                messages=[{"role": "user", "content": "hi"}],
            )
        await client.close()

    @pytest.mark.asyncio
    async def test_timeout_raises_turn_execution_error(self) -> None:
        """Covers lines 137-140: TimeoutException during chat_completion."""

        def raise_timeout(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("read timed out")

        client = AgentAPIClient(
            base_url="http://fake",
            transport=_make_transport(raise_timeout),
            max_retry_attempts=1,
        )
        with pytest.raises(TurnExecutionError, match="timed out"):
            await client.chat_completion(
                messages=[{"role": "user", "content": "hi"}],
            )
        await client.close()


# ---------------------------------------------------------------------------
# _try_parse_json fallback (lines 148-151)
# ---------------------------------------------------------------------------


class TestTryParseJsonFallback:
    @pytest.mark.asyncio
    async def test_non_json_error_body_uses_text(self) -> None:
        """Covers lines 150-151: response body is not valid JSON."""

        def non_json_error(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/health":
                return httpx.Response(200, json={"status": "ok"})
            return httpx.Response(
                400,
                content=b"<html>Bad Request</html>",
                headers={"content-type": "text/html"},
            )

        client = AgentAPIClient(
            base_url="http://fake",
            transport=_make_transport(non_json_error),
            max_retry_attempts=1,
        )
        with pytest.raises(TurnExecutionError, match="Bad Request"):
            await client.chat_completion(
                messages=[{"role": "user", "content": "hi"}],
            )
        await client.close()

    @pytest.mark.asyncio
    async def test_non_json_500_body_retries_then_fails(self) -> None:
        """Covers _try_parse_json on 500 with non-JSON body, plus retry exhaustion."""

        def non_json_server_error(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/health":
                return httpx.Response(200, json={"status": "ok"})
            return httpx.Response(
                500,
                content=b"Internal Server Error",
                headers={"content-type": "text/plain"},
            )

        client = AgentAPIClient(
            base_url="http://fake",
            transport=_make_transport(non_json_server_error),
            max_retry_attempts=2,
            retry_delay=0.01,
        )
        with pytest.raises(TurnExecutionError, match="Server error after 2 attempts"):
            await client.chat_completion(
                messages=[{"role": "user", "content": "hi"}],
            )
        await client.close()


# ---------------------------------------------------------------------------
# Server error retry exhaustion (lines 125-132)
# ---------------------------------------------------------------------------


class TestRetryExhaustion:
    @pytest.mark.asyncio
    async def test_all_retries_exhausted_raises_turn_execution(self) -> None:
        """Covers lines 125-132: all retry attempts fail with 500."""
        call_count = 0

        def always_500(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if request.url.path == "/health":
                return httpx.Response(200, json={"status": "ok"})
            return httpx.Response(500, json={"error": {"message": "boom"}})

        client = AgentAPIClient(
            base_url="http://fake",
            transport=_make_transport(always_500),
            max_retry_attempts=3,
            retry_delay=0.01,
        )
        with pytest.raises(TurnExecutionError, match="Server error after 3 attempts"):
            await client.chat_completion(
                messages=[{"role": "user", "content": "hi"}],
            )
        assert call_count == 3
        await client.close()
