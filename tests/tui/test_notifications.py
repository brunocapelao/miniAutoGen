"""Tests for desktop notification support via OSC 9/99."""

from __future__ import annotations

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.types import EventType
from miniautogen.tui.notifications import (
    NotificationLevel,
    TerminalNotifier,
    should_notify,
)


def test_approval_requested_triggers_notification() -> None:
    event = ExecutionEvent(
        type=EventType.APPROVAL_REQUESTED.value,
        run_id="r1",
        payload={"agent_id": "planner"},
    )
    assert should_notify(event) is True


def test_run_finished_triggers_notification() -> None:
    event = ExecutionEvent(type=EventType.RUN_FINISHED.value, run_id="r1")
    assert should_notify(event) is True


def test_run_failed_triggers_notification() -> None:
    event = ExecutionEvent(type=EventType.RUN_FAILED.value, run_id="r1")
    assert should_notify(event) is True


def test_component_started_does_not_trigger() -> None:
    event = ExecutionEvent(type=EventType.COMPONENT_STARTED.value, run_id="r1")
    assert should_notify(event) is False


def test_notification_level_all() -> None:
    event = ExecutionEvent(type=EventType.RUN_FINISHED.value, run_id="r1")
    assert should_notify(event, level=NotificationLevel.ALL) is True


def test_notification_level_failures_only_blocks_success() -> None:
    event = ExecutionEvent(type=EventType.RUN_FINISHED.value, run_id="r1")
    assert should_notify(event, level=NotificationLevel.FAILURES_ONLY) is False


def test_notification_level_failures_only_allows_failure() -> None:
    event = ExecutionEvent(type=EventType.RUN_FAILED.value, run_id="r1")
    assert should_notify(event, level=NotificationLevel.FAILURES_ONLY) is True


def test_notification_level_none_blocks_all() -> None:
    event = ExecutionEvent(type=EventType.RUN_FAILED.value, run_id="r1")
    assert should_notify(event, level=NotificationLevel.NONE) is False


def test_notifier_builds_osc9_sequence() -> None:
    notifier = TerminalNotifier()
    seq = notifier.build_osc9("Test title", "Test body")
    assert "\x1b]9;" in seq or "\x1b]99;" in seq


def test_notifier_format_approval_event() -> None:
    event = ExecutionEvent(
        type=EventType.APPROVAL_REQUESTED.value,
        run_id="r1",
        payload={"agent_id": "planner"},
    )
    title, body = TerminalNotifier.format_event(event)
    assert "planner" in body.lower() or "approval" in title.lower()
