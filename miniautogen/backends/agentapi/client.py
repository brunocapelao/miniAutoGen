"""HTTP client wrapper for OpenAI-compatible endpoints.

Handles auth, retry, health check, timeout, and error extraction.
Uses httpx for async HTTP and tenacity for retry logic.
"""

from __future__ import annotations

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
from miniautogen.observability.logging import get_logger

logger = get_logger(__name__)


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
            logger.info("health_check_passed", endpoint=self._health_endpoint)
            return True
        except httpx.ConnectError as exc:
            logger.warning("health_check_failed", endpoint=self._health_endpoint, error=str(exc))
            msg = f"Backend unreachable: {exc}"
            raise BackendUnavailableError(msg) from exc
        except httpx.TimeoutException as exc:
            logger.warning("health_check_timeout", endpoint=self._health_endpoint, error=str(exc))
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
            logger.error(
                "chat_completion_failed",
                attempts=self._max_retry_attempts,
                error=str(exc),
            )
            msg = f"Server error after {self._max_retry_attempts} attempts: {exc}"
            raise TurnExecutionError(msg) from exc
        except httpx.ConnectError as exc:
            logger.error("backend_unreachable", error=str(exc))
            msg = f"Backend unreachable: {exc}"
            raise BackendUnavailableError(msg) from exc
        except httpx.TimeoutException as exc:
            logger.error("request_timeout", error=str(exc))
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
