"""Decoupled approval channels for asynchronous human-in-the-loop.

Elevates the concept of ApprovalChannel to a first-class abstraction,
enabling approval flows beyond the terminal (Slack, Email, Web Dashboard,
HTTP webhooks, etc.).

The ApprovalChannel protocol decouples the approval mechanism from the
execution runtime. Instead of blocking on stdin, the runtime emits a
persistent APPROVAL_REQUESTED event and waits for resolution through
whichever channel is configured.

Architecture:
    1. Runtime encounters an action requiring approval
    2. ApprovalChannel.submit() is called with an ApprovalRequest
    3. Channel returns an ApprovalHandle (a future-like object)
    4. Runtime awaits handle.wait() which resolves when approval arrives
    5. External system (Slack, webhook, UI) calls handle.resolve()

.. stability:: experimental
"""

from __future__ import annotations

import ipaddress
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable, Protocol, runtime_checkable
from urllib.parse import urlparse

import anyio

from miniautogen.observability import get_logger
from miniautogen.policies.approval import (
    ApprovalGate,
    ApprovalRequest,
    ApprovalResponse,
)

logger = get_logger(__name__)


def _validate_webhook_url(url: str) -> None:
    """Validate a webhook URL for SSRF protection.

    Only allows http and https schemes. Requires https for non-localhost
    destinations. Blocks private/internal IP ranges.

    Raises:
        ValueError: If the URL is not safe.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"Webhook URL must use http or https scheme, got '{parsed.scheme}'"
        )
    hostname = parsed.hostname or ""

    # Allow http only for localhost
    is_localhost = hostname in ("localhost", "127.0.0.1", "::1")
    if parsed.scheme == "http" and not is_localhost:
        raise ValueError(
            "Webhook URL must use https for non-localhost destinations"
        )

    # Block private/internal IP ranges
    if not is_localhost:
        try:
            addr = ipaddress.ip_address(hostname)
            if addr.is_private or addr.is_loopback or addr.is_link_local:
                raise ValueError(
                    f"Webhook URL must not target private/internal IPs: {hostname}"
                )
        except ValueError as exc:
            if "must not target" in str(exc):
                raise
            # hostname is not an IP address (it's a domain name), which is fine


class ApprovalHandle:
    """Future-like handle for a pending approval request.

    Allows external systems to resolve an approval asynchronously.
    The runtime awaits ``wait()``; the external system calls ``resolve()``.
    """

    def __init__(
        self,
        request: ApprovalRequest,
        timeout_seconds: float | None = None,
    ) -> None:
        self.request = request
        self.timeout_seconds = timeout_seconds
        self._event = anyio.Event()
        self._response: ApprovalResponse | None = None
        self.created_at: datetime = datetime.now(timezone.utc)

    @property
    def is_resolved(self) -> bool:
        """Whether this handle has been resolved."""
        return self._response is not None

    @property
    def response(self) -> ApprovalResponse | None:
        """The approval response, if resolved."""
        return self._response

    def resolve(self, decision: str, reason: str | None = None) -> None:
        """Resolve this approval handle with a decision.

        Args:
            decision: "approved" or "denied".
            reason: Optional reason for the decision.

        Raises:
            ValueError: If already resolved or invalid decision.
        """
        if self._response is not None:
            raise ValueError(
                f"Approval {self.request.request_id} already resolved"
            )
        if decision not in ("approved", "denied"):
            raise ValueError(
                f"Decision must be 'approved' or 'denied', got '{decision}'"
            )
        self._response = ApprovalResponse(
            request_id=self.request.request_id,
            decision=decision,
            reason=reason,
        )
        self._event.set()

    async def wait(self) -> ApprovalResponse:
        """Wait for this approval to be resolved.

        Returns:
            The ApprovalResponse once resolved.

        Raises:
            TimeoutError: If timeout_seconds is set and exceeded.
        """
        if self._response is not None:
            return self._response

        if self.timeout_seconds is not None:
            with anyio.move_on_after(self.timeout_seconds):
                await self._event.wait()
            # After scope exits, check if resolved or timed out
            if self._response is not None:
                return self._response
            # Auto-deny on timeout
            logger.warning(
                "approval_timeout",
                request_id=self.request.request_id,
                timeout_seconds=self.timeout_seconds,
            )
            self._response = ApprovalResponse(
                request_id=self.request.request_id,
                decision="denied",
                reason=f"Approval timed out after {self.timeout_seconds}s",
            )
            self._event.set()
            return self._response
        else:
            await self._event.wait()

        assert self._response is not None
        return self._response


@runtime_checkable
class ApprovalChannel(Protocol):
    """Protocol for decoupled approval delivery.

    Implementations submit approval requests to external systems
    and return handles that resolve when the external system responds.

    This replaces the synchronous ApprovalGate for scenarios where
    approval comes from external systems (Slack, email, web UI, etc.).
    """

    async def submit(self, request: ApprovalRequest) -> ApprovalHandle:
        """Submit an approval request and return a handle.

        The handle can be awaited for the response, or the caller can
        poll ``handle.is_resolved`` periodically.
        """
        ...

    async def list_pending(self) -> list[ApprovalHandle]:
        """List all pending (unresolved) approval requests."""
        ...


class CallbackApprovalChannel:
    """Approval channel that delegates to an async callback.

    Useful for custom integrations -- pass any async function that
    receives an ApprovalRequest and returns a decision string.

    Example::

        async def my_approval_logic(request):
            # Custom logic (call Slack API, check database, etc.)
            return "approved"

        channel = CallbackApprovalChannel(callback=my_approval_logic)
    """

    def __init__(
        self,
        callback: Callable[[ApprovalRequest], Awaitable[str]],
        *,
        default_timeout: float | None = None,
    ) -> None:
        self._callback = callback
        self._default_timeout = default_timeout
        self._pending: dict[str, ApprovalHandle] = {}

    async def submit(self, request: ApprovalRequest) -> ApprovalHandle:
        timeout = request.timeout_seconds or self._default_timeout
        handle = ApprovalHandle(request, timeout_seconds=timeout)
        self._pending[request.request_id] = handle
        logger.info(
            "approval_submitted",
            channel="callback",
            request_id=request.request_id,
        )

        # Await callback inline (not fire-and-forget)
        await self._run_callback(handle)

        return handle

    async def list_pending(self) -> list[ApprovalHandle]:
        # Clean up resolved handles
        self._pending = {
            k: v for k, v in self._pending.items() if not v.is_resolved
        }
        return list(self._pending.values())

    async def _run_callback(self, handle: ApprovalHandle) -> None:
        try:
            decision = await self._callback(handle.request)
            if not handle.is_resolved:
                handle.resolve(decision)
                logger.info(
                    "approval_resolved",
                    channel="callback",
                    request_id=handle.request.request_id,
                    decision=decision,
                )
        except Exception:
            logger.error(
                "approval_callback_failed",
                request_id=handle.request.request_id,
            )
            if not handle.is_resolved:
                handle.resolve("denied", reason="Approval callback failed")


class InMemoryApprovalChannel:
    """In-memory approval channel for testing and programmatic use.

    Stores pending requests in memory. Approvals must be resolved
    externally by accessing the handles directly.

    Example::

        channel = InMemoryApprovalChannel()
        handle = await channel.submit(request)
        # ... later, from test or external code:
        handle.resolve("approved")
    """

    def __init__(
        self,
        *,
        default_timeout: float | None = None,
        auto_approve: bool = False,
    ) -> None:
        self._default_timeout = default_timeout
        self._auto_approve = auto_approve
        self._handles: dict[str, ApprovalHandle] = {}

    async def submit(self, request: ApprovalRequest) -> ApprovalHandle:
        timeout = request.timeout_seconds or self._default_timeout
        handle = ApprovalHandle(request, timeout_seconds=timeout)
        self._handles[request.request_id] = handle

        if self._auto_approve:
            handle.resolve("approved", reason="auto-approved (testing)")

        return handle

    async def list_pending(self) -> list[ApprovalHandle]:
        return [h for h in self._handles.values() if not h.is_resolved]

    def get_handle(self, request_id: str) -> ApprovalHandle | None:
        """Get a handle by request ID for external resolution."""
        return self._handles.get(request_id)

    @property
    def all_handles(self) -> dict[str, ApprovalHandle]:
        """Access all handles (resolved and pending)."""
        return dict(self._handles)


class WebhookApprovalChannel:
    """Approval channel that notifies an external webhook URL.

    Sends a POST request to the configured webhook URL when approval
    is needed. The external system must call back to resolve the handle
    (typically via the Gateway HTTP API).

    The webhook payload contains:
    - request_id: Unique ID for this approval
    - action: What action needs approval
    - description: Human-readable description
    - context: Additional context dict
    - callback_url: URL to POST the decision back to (if provided)

    Example::

        channel = WebhookApprovalChannel(
            webhook_url="https://hooks.slack.com/services/...",
            callback_base_url="https://my-app.com/api/approvals",
        )
    """

    def __init__(
        self,
        *,
        webhook_url: str,
        callback_base_url: str | None = None,
        default_timeout: float | None = 3600.0,
        headers: dict[str, str] | None = None,
    ) -> None:
        _validate_webhook_url(webhook_url)
        self._webhook_url = webhook_url
        self._callback_base_url = callback_base_url
        self._default_timeout = default_timeout
        self._headers = headers or {}
        self._pending: dict[str, ApprovalHandle] = {}

    async def submit(self, request: ApprovalRequest) -> ApprovalHandle:
        timeout = request.timeout_seconds or self._default_timeout
        handle = ApprovalHandle(request, timeout_seconds=timeout)
        self._pending[request.request_id] = handle
        logger.info(
            "approval_submitted",
            channel="webhook",
            request_id=request.request_id,
        )

        # Notify webhook inline with timeout
        with anyio.move_on_after(10):
            await self._notify_webhook(request)

        return handle

    async def list_pending(self) -> list[ApprovalHandle]:
        self._pending = {
            k: v for k, v in self._pending.items() if not v.is_resolved
        }
        return list(self._pending.values())

    def get_handle(self, request_id: str) -> ApprovalHandle | None:
        """Get a handle by request ID for external resolution."""
        return self._pending.get(request_id)

    async def _notify_webhook(self, request: ApprovalRequest) -> None:
        """Send approval notification to the webhook URL."""
        import json
        from urllib.request import Request, urlopen

        payload: dict[str, Any] = {
            "request_id": request.request_id,
            "action": request.action,
            "description": request.description,
            "context": request.context,
        }
        if self._callback_base_url:
            payload["callback_url"] = (
                f"{self._callback_base_url}/{request.request_id}"
            )

        try:
            data = json.dumps(payload).encode("utf-8")
            headers = {"Content-Type": "application/json", **self._headers}
            req = Request(
                self._webhook_url,
                data=data,
                headers=headers,
                method="POST",
            )
            # Run in thread to avoid blocking the event loop
            await anyio.to_thread.run_sync(lambda: urlopen(req, timeout=10))
        except Exception:
            # Webhook notification is best-effort; the handle remains pending
            logger.warning(
                "webhook_notification_failed",
                request_id=request.request_id,
                webhook_url=self._webhook_url,
            )


class ChannelApprovalGate:
    """Adapter that bridges ApprovalChannel to the ApprovalGate protocol.

    This allows using any ApprovalChannel implementation where an
    ApprovalGate is expected (e.g., in PipelineRunner).

    Example::

        channel = WebhookApprovalChannel(webhook_url="...")
        gate = ChannelApprovalGate(channel)
        runner = PipelineRunner(approval_gate=gate)
    """

    def __init__(self, channel: ApprovalChannel) -> None:
        self._channel = channel

    async def request_approval(
        self, request: ApprovalRequest,
    ) -> ApprovalResponse:
        """Submit to channel and wait for resolution."""
        handle = await self._channel.submit(request)
        return await handle.wait()
