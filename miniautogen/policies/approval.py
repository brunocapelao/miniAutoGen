"""Approval policy for human-in-the-loop execution control.

The ApprovalGate protocol allows external systems (Terminal Harness,
web UI) to intercept and approve/deny dangerous operations. The SDK
provides AutoApproveGate for headless/testing scenarios.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class ApprovalRequest(BaseModel):
    """Request for external approval before executing an action."""

    request_id: str
    action: str
    description: str
    context: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: float | None = None


class ApprovalResponse(BaseModel):
    """Response to an approval request."""

    request_id: str
    decision: Literal["approved", "denied", "modified"]
    reason: str | None = None
    modifications: dict[str, Any] | None = None


@runtime_checkable
class ApprovalGate(Protocol):
    """Protocol for external approval providers.

    Implementations receive an ApprovalRequest and must return
    an ApprovalResponse. The Terminal Harness will provide an
    interactive implementation; the SDK provides AutoApproveGate
    for headless scenarios.
    """

    async def request_approval(
        self, request: ApprovalRequest,
    ) -> ApprovalResponse: ...


@dataclass(frozen=True)
class ApprovalPolicy:
    """Defines which actions require approval.

    When ``require_approval_for`` is non-empty, the PipelineRunner
    checks against it before executing matching actions.
    """

    require_approval_for: frozenset[str] = field(
        default_factory=frozenset,
    )


class AutoApproveGate:
    """Default gate that approves all requests.

    Use in headless/testing scenarios where no human is available.
    """

    async def request_approval(
        self, request: ApprovalRequest,
    ) -> ApprovalResponse:
        return ApprovalResponse(
            request_id=request.request_id,
            decision="approved",
            reason="auto-approved (headless mode)",
        )
