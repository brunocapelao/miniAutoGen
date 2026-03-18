"""Tests for the EventBridgeWorker that reads from TuiEventSink."""

from __future__ import annotations

import pytest

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.types import EventType
from miniautogen.tui.event_sink import TuiEventSink
from miniautogen.tui.workers import EventBridgeWorker


def test_event_bridge_worker_exists() -> None:
    """EventBridgeWorker must be importable."""
    assert EventBridgeWorker is not None


def test_event_bridge_worker_accepts_sink() -> None:
    """EventBridgeWorker must accept a TuiEventSink."""
    sink = TuiEventSink()
    worker = EventBridgeWorker(sink)
    assert worker._sink is sink
