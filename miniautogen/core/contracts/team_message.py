"""MailMessage and PlanApprovalRequest contracts for team mailbox (Spec 017)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

MailKind = Literal[
    "chat",
    "plan_approval_request",
    "plan_approval_granted",
    "plan_approval_denied",
]


class MailMessage(BaseModel):
    id: str
    from_agent: str
    to_agent: str
    content: str
    kind: MailKind = "chat"
    correlation_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    sent_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PlanApprovalRequest(BaseModel):
    correlation_id: str
    from_agent: str
    to_agent: str
    plan: str | dict[str, Any]
    timeout_seconds: float = 300.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
