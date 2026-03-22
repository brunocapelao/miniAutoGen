"""WebSocket event streaming for the MiniAutoGen Console."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from miniautogen.core.contracts.events import ExecutionEvent

logger = logging.getLogger(__name__)


class WebSocketEventSink:
    """EventSink that stores events and broadcasts to WebSocket clients.

    Events with run_id=None are silently dropped from WebSocket broadcast.
    This is an explicit design decision — system-level events are persisted
    by store sinks via CompositeEventSink.
    """

    def __init__(self) -> None:
        self._events: dict[str, list[ExecutionEvent]] = defaultdict(list)
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)

    async def publish(self, event: ExecutionEvent) -> None:
        if event.run_id is None:
            return

        self._events[event.run_id].append(event)

        message = event.model_dump_json()
        dead_connections = []
        for ws in self._connections.get(event.run_id, []):
            try:
                await ws.send_text(message)
            except Exception:
                dead_connections.append(ws)

        for ws in dead_connections:
            try:
                self._connections[event.run_id].remove(ws)
            except ValueError:
                pass

    def get_events(self, run_id: str | None) -> list[ExecutionEvent]:
        if run_id is None:
            return []
        return list(self._events.get(run_id, []))

    def get_events_as_dicts(self, run_id: str) -> list[dict[str, Any]]:
        return [json.loads(e.model_dump_json()) for e in self._events.get(run_id, [])]

    async def connect(self, run_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[run_id].append(websocket)
        await websocket.send_json({"type": "connected", "run_id": run_id})

    def disconnect(self, run_id: str, websocket: WebSocket) -> None:
        try:
            self._connections[run_id].remove(websocket)
        except ValueError:
            pass


def ws_router(event_sink: WebSocketEventSink) -> APIRouter:
    router = APIRouter(tags=["websocket"])

    @router.websocket("/ws/runs/{run_id}")
    async def ws_run_events(websocket: WebSocket, run_id: str) -> None:
        await event_sink.connect(run_id, websocket)
        try:
            while True:
                data = await websocket.receive_json()
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            event_sink.disconnect(run_id, websocket)
        except Exception:
            event_sink.disconnect(run_id, websocket)

    return router
