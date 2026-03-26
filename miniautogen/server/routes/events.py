"""Events endpoint: list recent events from the global broadcaster buffer."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request


def events_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["events"])

    @router.get("/events")
    async def list_events(
        request: Request,
        limit: int = Query(100, ge=1, le=1000),
        type: str | None = Query(None, description="Filter by event type"),
    ) -> list[dict[str, Any]]:
        """Return recent events from the global broadcaster buffer."""
        broadcaster = request.app.state.event_broadcaster
        events = broadcaster.get_recent(limit=limit if type is None else 1000)
        if type is not None:
            events = [e for e in events if e.get("type") == type]
            events = events[-limit:] if limit < len(events) else events
        return events

    return router
