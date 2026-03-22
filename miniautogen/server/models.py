"""Pydantic models for Console API request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class AgentSummary(BaseModel):
    name: str
    role: str
    engine_type: str
    status: str = "idle"  # "idle" | "running" | "error"


class AgentDetail(AgentSummary):
    """Simplified agent detail for Sprint 1.

    Note: The spec envisions 5-layer structure (identity, engine, runtime,
    skills, tools). This is a pragmatic simplification — the DashDataProvider
    returns flat dicts, not typed config objects. Full 5-layer detail is
    Sprint 2+ work requiring AgentSpec model integration.
    """

    goal: str | None = None
    engine_profile: str | None = None
    raw: dict[str, Any] = {}


class FlowSummary(BaseModel):
    name: str
    mode: str
    target: str | None = None


class FlowDetail(FlowSummary):
    participants: list[str] = []
    leader: str | None = None
    max_rounds: int | None = None
    raw: dict[str, Any] = {}


class RunSummary(BaseModel):
    run_id: str
    pipeline: str
    status: str
    started: str
    events: int = 0


class RunRequest(BaseModel):
    flow_name: str
    input: str | None = None
    timeout: float | None = None


class ApprovalDecision(BaseModel):
    decision: Literal["approved", "denied"]
    reason: str | None = None


class PendingApproval(BaseModel):
    request_id: str
    agent_name: str
    action: str
    requested_at: datetime


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
    code: str


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    offset: int
    limit: int
