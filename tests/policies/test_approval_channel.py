"""Tests for ApprovalChannel, ApprovalHandle, and channel implementations."""

from __future__ import annotations

import asyncio

import pytest

from miniautogen.policies.approval import (
    ApprovalGate,
    ApprovalRequest,
    ApprovalResponse,
)
from miniautogen.policies.approval_channel import (
    ApprovalChannel,
    ApprovalHandle,
    CallbackApprovalChannel,
    ChannelApprovalGate,
    InMemoryApprovalChannel,
    WebhookApprovalChannel,
)


def _make_request(request_id: str = "req-1") -> ApprovalRequest:
    return ApprovalRequest(
        request_id=request_id,
        action="deploy",
        description="Deploy to production",
    )


class TestApprovalHandle:
    def test_initial_state(self) -> None:
        handle = ApprovalHandle(_make_request())
        assert not handle.is_resolved
        assert handle.response is None

    def test_resolve_approved(self) -> None:
        handle = ApprovalHandle(_make_request())
        handle.resolve("approved", reason="LGTM")
        assert handle.is_resolved
        assert handle.response is not None
        assert handle.response.decision == "approved"
        assert handle.response.reason == "LGTM"
        assert handle.response.request_id == "req-1"

    def test_resolve_denied(self) -> None:
        handle = ApprovalHandle(_make_request())
        handle.resolve("denied", reason="Not ready")
        assert handle.response is not None
        assert handle.response.decision == "denied"

    def test_resolve_twice_raises(self) -> None:
        handle = ApprovalHandle(_make_request())
        handle.resolve("approved")
        with pytest.raises(ValueError, match="already resolved"):
            handle.resolve("denied")

    def test_resolve_invalid_decision_raises(self) -> None:
        handle = ApprovalHandle(_make_request())
        with pytest.raises(ValueError, match="must be 'approved' or 'denied'"):
            handle.resolve("maybe")

    @pytest.mark.anyio
    async def test_wait_already_resolved(self) -> None:
        handle = ApprovalHandle(_make_request())
        handle.resolve("approved")
        response = await handle.wait()
        assert response.decision == "approved"

    @pytest.mark.anyio
    async def test_wait_resolved_externally(self) -> None:
        handle = ApprovalHandle(_make_request())

        async def resolve_later() -> None:
            await asyncio.sleep(0.01)
            handle.resolve("approved")

        asyncio.create_task(resolve_later())
        response = await handle.wait()
        assert response.decision == "approved"

    @pytest.mark.anyio
    async def test_wait_timeout_auto_denies(self) -> None:
        handle = ApprovalHandle(_make_request(), timeout_seconds=0.05)
        response = await handle.wait()
        assert response.decision == "denied"
        assert "timed out" in (response.reason or "")


class TestInMemoryApprovalChannel:
    @pytest.mark.anyio
    async def test_submit_returns_handle(self) -> None:
        channel = InMemoryApprovalChannel()
        handle = await channel.submit(_make_request())
        assert isinstance(handle, ApprovalHandle)
        assert not handle.is_resolved

    @pytest.mark.anyio
    async def test_list_pending(self) -> None:
        channel = InMemoryApprovalChannel()
        await channel.submit(_make_request("req-1"))
        await channel.submit(_make_request("req-2"))
        pending = await channel.list_pending()
        assert len(pending) == 2

    @pytest.mark.anyio
    async def test_list_pending_excludes_resolved(self) -> None:
        channel = InMemoryApprovalChannel()
        h1 = await channel.submit(_make_request("req-1"))
        await channel.submit(_make_request("req-2"))
        h1.resolve("approved")
        pending = await channel.list_pending()
        assert len(pending) == 1

    @pytest.mark.anyio
    async def test_auto_approve(self) -> None:
        channel = InMemoryApprovalChannel(auto_approve=True)
        handle = await channel.submit(_make_request())
        assert handle.is_resolved
        assert handle.response is not None
        assert handle.response.decision == "approved"

    @pytest.mark.anyio
    async def test_get_handle(self) -> None:
        channel = InMemoryApprovalChannel()
        await channel.submit(_make_request("req-1"))
        handle = channel.get_handle("req-1")
        assert handle is not None
        assert handle.request.request_id == "req-1"

    @pytest.mark.anyio
    async def test_get_handle_missing(self) -> None:
        channel = InMemoryApprovalChannel()
        assert channel.get_handle("nonexistent") is None

    @pytest.mark.anyio
    async def test_all_handles_property(self) -> None:
        channel = InMemoryApprovalChannel()
        await channel.submit(_make_request("req-1"))
        await channel.submit(_make_request("req-2"))
        assert len(channel.all_handles) == 2

    @pytest.mark.anyio
    async def test_satisfies_protocol(self) -> None:
        channel = InMemoryApprovalChannel()
        assert isinstance(channel, ApprovalChannel)


class TestCallbackApprovalChannel:
    @pytest.mark.anyio
    async def test_callback_approves(self) -> None:
        async def always_approve(req: ApprovalRequest) -> str:
            return "approved"

        channel = CallbackApprovalChannel(callback=always_approve)
        handle = await channel.submit(_make_request())
        response = await handle.wait()
        assert response.decision == "approved"

    @pytest.mark.anyio
    async def test_callback_denies(self) -> None:
        async def always_deny(req: ApprovalRequest) -> str:
            return "denied"

        channel = CallbackApprovalChannel(callback=always_deny)
        handle = await channel.submit(_make_request())
        response = await handle.wait()
        assert response.decision == "denied"

    @pytest.mark.anyio
    async def test_callback_error_denies(self) -> None:
        async def failing_callback(req: ApprovalRequest) -> str:
            raise RuntimeError("network error")

        channel = CallbackApprovalChannel(callback=failing_callback)
        handle = await channel.submit(_make_request())
        response = await handle.wait()
        assert response.decision == "denied"
        assert "Callback error" in (response.reason or "")

    @pytest.mark.anyio
    async def test_list_pending(self) -> None:
        resolved = asyncio.Event()

        async def slow_approve(req: ApprovalRequest) -> str:
            await resolved.wait()
            return "approved"

        channel = CallbackApprovalChannel(callback=slow_approve)
        await channel.submit(_make_request("req-1"))
        # Give callback task a moment to start
        await asyncio.sleep(0.01)
        pending = await channel.list_pending()
        assert len(pending) == 1
        resolved.set()

    @pytest.mark.anyio
    async def test_satisfies_protocol(self) -> None:
        async def noop(req: ApprovalRequest) -> str:
            return "approved"

        channel = CallbackApprovalChannel(callback=noop)
        assert isinstance(channel, ApprovalChannel)


class TestChannelApprovalGate:
    @pytest.mark.anyio
    async def test_bridges_channel_to_gate(self) -> None:
        channel = InMemoryApprovalChannel(auto_approve=True)
        gate = ChannelApprovalGate(channel)
        resp = await gate.request_approval(_make_request())
        assert resp.decision == "approved"

    @pytest.mark.anyio
    async def test_bridges_with_callback_channel(self) -> None:
        async def approve(req: ApprovalRequest) -> str:
            return "approved"

        channel = CallbackApprovalChannel(callback=approve)
        gate = ChannelApprovalGate(channel)
        resp = await gate.request_approval(_make_request())
        assert resp.decision == "approved"

    @pytest.mark.anyio
    async def test_satisfies_approval_gate_protocol(self) -> None:
        channel = InMemoryApprovalChannel()
        gate = ChannelApprovalGate(channel)
        assert isinstance(gate, ApprovalGate)

    @pytest.mark.anyio
    async def test_timeout_through_gate(self) -> None:
        channel = InMemoryApprovalChannel(default_timeout=0.05)
        gate = ChannelApprovalGate(channel)
        req = _make_request()
        resp = await gate.request_approval(req)
        assert resp.decision == "denied"
        assert "timed out" in (resp.reason or "")


class TestWebhookApprovalChannel:
    def test_init(self) -> None:
        channel = WebhookApprovalChannel(
            webhook_url="https://hooks.example.com/test",
            callback_base_url="https://my-app.com/api/approvals",
        )
        assert channel._webhook_url == "https://hooks.example.com/test"

    @pytest.mark.anyio
    async def test_submit_returns_pending_handle(self) -> None:
        channel = WebhookApprovalChannel(
            webhook_url="https://hooks.example.com/test",
        )
        # The webhook notification will fail (no real server), but
        # the handle should still be created
        handle = await channel.submit(_make_request())
        assert isinstance(handle, ApprovalHandle)
        assert not handle.is_resolved

    @pytest.mark.anyio
    async def test_get_handle(self) -> None:
        channel = WebhookApprovalChannel(
            webhook_url="https://hooks.example.com/test",
        )
        await channel.submit(_make_request("req-42"))
        handle = channel.get_handle("req-42")
        assert handle is not None

    @pytest.mark.anyio
    async def test_external_resolution(self) -> None:
        channel = WebhookApprovalChannel(
            webhook_url="https://hooks.example.com/test",
        )
        handle = await channel.submit(_make_request("req-42"))
        # Simulate external resolution (e.g., from Slack callback)
        handle.resolve("approved", reason="Approved via Slack")
        assert handle.is_resolved
        response = await handle.wait()
        assert response.decision == "approved"
