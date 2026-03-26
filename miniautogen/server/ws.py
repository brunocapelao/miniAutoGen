"""WebSocket event streaming for the MiniAutoGen Console."""

from __future__ import annotations

import json
import logging
from collections import defaultdict, deque
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.event_sink import EventSink
from miniautogen.server.event_broadcaster import GlobalEventBroadcaster

logger = logging.getLogger(__name__)

MAX_EVENTS_PER_RUN = 10_000
MAX_CONNECTIONS_PER_RUN = 10


class WebSocketEventSink(EventSink):
    """EventSink implementation that stores events and broadcasts to WebSocket clients.

    Explicitly conforms to the EventSink protocol
    (miniautogen.core.events.event_sink.EventSink).

    Events with run_id=None are silently dropped from WebSocket broadcast.
    This is an explicit design decision — system-level events are persisted
    by store sinks via CompositeEventSink.
    """

    def __init__(self) -> None:
        self._events: dict[str, deque[ExecutionEvent]] = defaultdict(
            lambda: deque(maxlen=MAX_EVENTS_PER_RUN)
        )
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
        return list(self._events.get(run_id, deque()))

    def get_events_as_dicts(self, run_id: str) -> list[dict[str, Any]]:
        return [json.loads(e.model_dump_json()) for e in self._events.get(run_id, [])]

    async def connect(self, run_id: str, websocket: WebSocket) -> None:
        if len(self._connections[run_id]) >= MAX_CONNECTIONS_PER_RUN:
            await websocket.close(code=1013, reason="Too many connections")
            return
        await websocket.accept()
        self._connections[run_id].append(websocket)
        try:
            await websocket.send_json({"type": "connected", "run_id": run_id})
        except Exception:
            self._connections[run_id].remove(websocket)

    def disconnect(self, run_id: str, websocket: WebSocket) -> None:
        try:
            self._connections[run_id].remove(websocket)
        except ValueError:
            pass


def ws_router(event_sink: WebSocketEventSink) -> APIRouter:
    router = APIRouter(tags=["websocket"])

    @router.websocket("/ws/runs/{run_id}")
    async def ws_run_events(websocket: WebSocket, run_id: str) -> None:
        try:
            from uuid import UUID
            UUID(run_id)
        except ValueError:
            await websocket.close(code=1008, reason="Invalid run_id format")
            return
        await event_sink.connect(run_id, websocket)
        try:
            while True:
                data = await websocket.receive_json()
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            event_sink.disconnect(run_id, websocket)
        except Exception as exc:
            logger.warning("WebSocket error for run %s: %s", run_id, exc)
            event_sink.disconnect(run_id, websocket)
            try:
                await websocket.close(code=1011, reason="Internal error")
            except Exception:
                pass

    return router


def global_events_router(broadcaster: GlobalEventBroadcaster) -> APIRouter:
    """Create a router for global event WebSocket streaming."""
    router = APIRouter(tags=["websocket"])

    @router.websocket("/ws/events")
    async def global_events_ws(websocket: WebSocket) -> None:
        """WebSocket endpoint for global event streaming."""
        await websocket.accept()
        queue = broadcaster.subscribe()
        try:
            while True:
                event = await queue.get()
                await websocket.send_json(event)
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            logger.warning("Global events WebSocket error: %s", exc)
            try:
                await websocket.close(code=1011, reason="Internal error")
            except Exception:
                pass
        finally:
            broadcaster.unsubscribe(queue)

    return router
