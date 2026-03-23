"""Run endpoints: list, detail, events, trigger, approvals."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request

from miniautogen.server.models import (
    ApprovalDecision,
    ErrorResponse,
    Page,
    RunRequest,
)
from miniautogen.server.provider_protocol import ConsoleDataProvider


def runs_router(provider: ConsoleDataProvider, event_sink: Any | None = None) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["runs"])

    # Shared state for approval channels per run
    _approval_channels: dict[str, Any] = {}

    @router.get("/runs")
    async def list_runs(
        offset: int = Query(0, ge=0),
        limit: int = Query(20, ge=1, le=100),
    ) -> Page:
        all_runs = provider.get_runs()
        return Page(
            items=all_runs[offset : offset + limit],
            total=len(all_runs),
            offset=offset,
            limit=limit,
        )

    @router.get("/runs/{run_id}", responses={404: {"model": ErrorResponse}})
    async def get_run(run_id: str) -> dict[str, Any]:
        runs = provider.get_runs()
        for run in runs:
            if run.get("run_id") == run_id:
                return run
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(error=f"Run '{run_id}' not found", code="run_not_found").model_dump(),
        )

    @router.get("/runs/{run_id}/events", responses={404: {"model": ErrorResponse}})
    async def get_run_events(
        run_id: str,
        offset: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=500),
    ) -> Page:
        runs = provider.get_runs()
        if not any(r.get("run_id") == run_id for r in runs):
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(error=f"Run '{run_id}' not found", code="run_not_found").model_dump(),
            )
        # Prefer event_sink (WebSocket store) over provider (which is disconnected)
        if event_sink is not None:
            run_events = event_sink.get_events_as_dicts(run_id)
        else:
            all_events = provider.get_events()
            run_events = [e for e in all_events if e.get("run_id") == run_id]
        return Page(
            items=run_events[offset : offset + limit],
            total=len(run_events),
            offset=offset,
            limit=limit,
        )

    @router.post("/runs", responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}})
    async def trigger_run(
        req: RunRequest,
        request: Request,
        background_tasks: BackgroundTasks,
    ) -> dict[str, str]:
        # Verify flow exists
        pipelines = provider.get_pipelines()
        pipeline_names = [p.get("name") for p in pipelines]
        if req.flow_name not in pipeline_names:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(error=f"Flow '{req.flow_name}' not found", code="flow_not_found").model_dump(),
            )

        # Get event_sink from app state (wired in create_app for embedded mode)
        sink = getattr(request.app.state, "event_sink", None)

        # Generate run_id upfront so we can return it immediately
        run_id = str(uuid4())

        # Pre-record the run as "running" before background task starts
        provider.record_run({
            "run_id": run_id,
            "pipeline": req.flow_name,
            "status": "running",
            "started": datetime.now(timezone.utc).isoformat(),
            "events": 0,
        })

        # Run pipeline in background; update the pre-recorded entry on completion
        async def _run():
            result = await provider.run_pipeline(
                req.flow_name,
                event_sink=sink,
                pipeline_input=req.input,
                timeout=req.timeout,
                run_id=run_id,
            )
            is_dict = isinstance(result, dict)
            updates = {
                "status": result.get("status", "unknown") if is_dict else "completed",
                "events": result.get("events", 0) if is_dict else 0,
            }
            provider.update_run(run_id, updates)

        background_tasks.add_task(_run)
        return {"run_id": run_id}

    # ── Approval endpoints ──────────────────────────────────

    @router.get("/runs/{run_id}/approvals")
    async def list_approvals(run_id: str) -> list[dict[str, Any]]:
        channel = _approval_channels.get(run_id)
        if channel is None:
            return []
        pending = await channel.list_pending()
        return [
            {
                "request_id": h.request.request_id,
                "agent_name": getattr(h.request, "agent_name", "unknown"),
                "action": getattr(h.request, "action", "unknown"),
                "requested_at": h.created_at.isoformat(),
            }
            for h in pending
        ]

    @router.post(
        "/runs/{run_id}/approvals/{request_id}",
        responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
    )
    async def resolve_approval(
        run_id: str,
        request_id: str,
        body: ApprovalDecision,
    ) -> dict[str, str]:
        channel = _approval_channels.get(run_id)
        if channel is None:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(error="No approval channel for this run", code="run_not_found").model_dump(),
            )
        pending = await channel.list_pending()
        handle = None
        for h in pending:
            if h.request.request_id == request_id:
                handle = h
                break
        if handle is None:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    error=f"Approval '{request_id}' not found",
                    code="approval_not_found",
                ).model_dump(),
            )
        try:
            handle.resolve(body.decision, body.reason)
        except ValueError:
            raise HTTPException(
                status_code=409,
                detail=ErrorResponse(error="Approval already resolved", code="approval_already_resolved").model_dump(),
            )
        return {"status": "resolved", "decision": body.decision}

    # Expose for WebSocket/CLI integration
    router.approval_channels = _approval_channels  # type: ignore[attr-defined]

    return router
