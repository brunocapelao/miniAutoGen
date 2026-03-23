"""Tests for WebSocket event streaming and WebSocketEventSink."""

from __future__ import annotations

import json

import anyio
import pytest

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.server.ws import WebSocketEventSink


@pytest.mark.anyio
async def test_ws_event_sink_publish_stores_events():
    sink = WebSocketEventSink()
    event = ExecutionEvent(type="run_started", run_id="r1")
    await sink.publish(event)
    assert len(sink.get_events("r1")) == 1
    assert sink.get_events("r1")[0].type == "run_started"


@pytest.mark.anyio
async def test_ws_event_sink_ignores_none_run_id():
    sink = WebSocketEventSink()
    event = ExecutionEvent(type="system_event")
    await sink.publish(event)
    assert len(sink.get_events(None)) == 0


@pytest.mark.anyio
async def test_ws_event_sink_multiple_runs():
    sink = WebSocketEventSink()
    await sink.publish(ExecutionEvent(type="run_started", run_id="r1"))
    await sink.publish(ExecutionEvent(type="run_started", run_id="r2"))
    await sink.publish(ExecutionEvent(type="step", run_id="r1"))
    assert len(sink.get_events("r1")) == 2
    assert len(sink.get_events("r2")) == 1


@pytest.mark.anyio
async def test_ws_event_sink_as_dict():
    sink = WebSocketEventSink()
    await sink.publish(ExecutionEvent(type="run_started", run_id="r1"))
    dicts = sink.get_events_as_dicts("r1")
    assert len(dicts) == 1
    assert dicts[0]["type"] == "run_started"
