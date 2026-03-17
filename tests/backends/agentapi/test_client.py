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
