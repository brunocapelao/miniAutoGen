"""Tests for Console API response/request models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError


def test_agent_summary_required_fields():
    from miniautogen.server.models import AgentSummary
    agent = AgentSummary(name="researcher", role="researcher", engine_type="litellm")
    assert agent.name == "researcher"
    assert agent.role == "researcher"
    assert agent.engine_type == "litellm"


def test_agent_summary_missing_field():
    from miniautogen.server.models import AgentSummary
    with pytest.raises(ValidationError):
        AgentSummary(name="researcher")  # missing role, engine_type


def test_run_request_defaults():
    from miniautogen.server.models import RunRequest
    req = RunRequest(flow_name="main")
    assert req.flow_name == "main"
    assert req.input is None
    assert req.timeout is None


def test_run_request_with_all_fields():
    from miniautogen.server.models import RunRequest
    req = RunRequest(flow_name="main", input="hello", timeout=30.0)
    assert req.input == "hello"
    assert req.timeout == 30.0


def test_error_response():
    from miniautogen.server.models import ErrorResponse
    err = ErrorResponse(error="Not found", code="flow_not_found")
    assert err.error == "Not found"
    assert err.code == "flow_not_found"
    assert err.detail is None


def test_approval_decision_valid():
    from miniautogen.server.models import ApprovalDecision
    dec = ApprovalDecision(decision="approved")
    assert dec.decision == "approved"
    assert dec.reason is None


def test_approval_decision_invalid():
    from miniautogen.server.models import ApprovalDecision
    with pytest.raises(ValidationError):
        ApprovalDecision(decision="maybe")


def test_page_model():
    from miniautogen.server.models import Page
    page = Page(items=["a", "b"], total=10, offset=0, limit=20)
    assert len(page.items) == 2
    assert page.total == 10


def test_pending_approval():
    from datetime import datetime, timezone
    from miniautogen.server.models import PendingApproval
    pa = PendingApproval(
        request_id="req-1",
        agent_name="agent-a",
        action="send_email",
        requested_at=datetime.now(timezone.utc),
    )
    assert pa.request_id == "req-1"
