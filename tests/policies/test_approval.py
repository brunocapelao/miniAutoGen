"""Tests for ApprovalPolicy, ApprovalGate, and AutoApproveGate."""

import pytest

from miniautogen.policies.approval import (
    ApprovalGate,
    ApprovalPolicy,
    ApprovalRequest,
    ApprovalResponse,
    AutoApproveGate,
)


def test_approval_request_creation() -> None:
    req = ApprovalRequest(
        request_id="req-1",
        action="delete_file",
        description="Delete /tmp/data.csv",
    )
    assert req.request_id == "req-1"
    assert req.context == {}


def test_approval_response_approved() -> None:
    resp = ApprovalResponse(
        request_id="req-1", decision="approved",
    )
    assert resp.decision == "approved"


def test_approval_response_denied_with_reason() -> None:
    resp = ApprovalResponse(
        request_id="req-1",
        decision="denied",
        reason="Too dangerous",
    )
    assert resp.reason == "Too dangerous"


def test_approval_response_modified() -> None:
    resp = ApprovalResponse(
        request_id="req-1",
        decision="modified",
        modifications={"path": "/tmp/safe.csv"},
    )
    assert resp.modifications == {"path": "/tmp/safe.csv"}


def test_approval_policy_default_empty() -> None:
    policy = ApprovalPolicy()
    assert len(policy.require_approval_for) == 0


def test_approval_policy_with_actions() -> None:
    policy = ApprovalPolicy(
        require_approval_for=frozenset({"delete", "execute"}),
    )
    assert "delete" in policy.require_approval_for
    assert "read" not in policy.require_approval_for


def test_auto_approve_gate_satisfies_protocol() -> None:
    gate = AutoApproveGate()
    assert isinstance(gate, ApprovalGate)


@pytest.mark.anyio
async def test_auto_approve_gate_approves() -> None:
    gate = AutoApproveGate()
    req = ApprovalRequest(
        request_id="req-1",
        action="delete",
        description="test",
    )
    resp = await gate.request_approval(req)
    assert resp.decision == "approved"
    assert resp.request_id == "req-1"
