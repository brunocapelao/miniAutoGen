"""Tests for the inline HITL approval banner widget."""

from __future__ import annotations

import pytest

from textual.widget import Widget

from miniautogen.tui.widgets.approval_banner import ApprovalBanner, ApprovalDecision


def test_approval_banner_is_widget() -> None:
    assert issubclass(ApprovalBanner, Widget)


def test_approval_banner_stores_request() -> None:
    banner = ApprovalBanner(
        request_id="req-1",
        action="run_pipeline",
        description="Execute pipeline main",
    )
    assert banner.request_id == "req-1"
    assert banner.action == "run_pipeline"
    assert banner.description == "Execute pipeline main"


def test_approval_decision_message() -> None:
    """ApprovalDecision message carries the decision."""
    from textual.message import Message

    decision = ApprovalDecision(
        request_id="req-1",
        decision="approved",
    )
    assert isinstance(decision, Message)
    assert decision.request_id == "req-1"
    assert decision.decision == "approved"


def test_approval_decision_denied() -> None:
    decision = ApprovalDecision(
        request_id="req-2",
        decision="denied",
        reason="Unsafe operation",
    )
    assert decision.decision == "denied"
    assert decision.reason == "Unsafe operation"


def test_approval_banner_files_affected() -> None:
    banner = ApprovalBanner(
        request_id="req-1",
        action="file_delete",
        description="Delete temp files",
        files_affected=["temp.py", "cache.db"],
    )
    assert banner.files_affected == ["temp.py", "cache.db"]
