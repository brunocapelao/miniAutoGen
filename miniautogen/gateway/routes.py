"""API routes for run management."""

from __future__ import annotations

import re
import uuid

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, field_validator, Field

from miniautogen.gateway.rate_limit import limiter

router = APIRouter()

# Pattern: alphanumeric, hyphens, underscores only
_RUN_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")
_RUN_ID_MAX_LENGTH = 128


def _validate_run_id_format(value: str) -> str:
    """Validate run_id format: 1-128 chars, alphanumeric + hyphens/underscores."""
    if len(value) > _RUN_ID_MAX_LENGTH:
        raise ValueError(f"run_id must be at most {_RUN_ID_MAX_LENGTH} characters")
    if not _RUN_ID_PATTERN.match(value):
        raise ValueError(
            "run_id must contain only alphanumeric characters, hyphens, and underscores, "
            "and must start with an alphanumeric character"
        )
    return value


async def validate_path_run_id(
    run_id: Annotated[str, Path(min_length=1, max_length=128)],
) -> str:
    """Dependency to validate run_id path parameters."""
    if not _RUN_ID_PATTERN.match(run_id):
        raise HTTPException(
            status_code=422,
            detail="run_id must contain only alphanumeric characters, hyphens, and underscores",
        )
    return run_id


ValidRunId = Annotated[str, Depends(validate_path_run_id)]


class RunCreateRequest(BaseModel):
    """Request body to start a new run."""

    run_id: str | None = None
    input_payload: dict = {}
    timeout_seconds: float | None = None
    namespace: str = "default"

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v == "":
            raise ValueError("run_id must not be empty")
        return _validate_run_id_format(v)


class RunResponse(BaseModel):
    """Run status response."""

    run_id: str
    status: str
    output: dict | None = None
    error: str | None = None
    metadata: dict = {}


class EventResponse(BaseModel):
    """Event in a run."""

    type: str
    timestamp: str
    run_id: str
    payload: dict = {}


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    version: str


@router.get("/health")
async def health() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="ok", version="0.1.0")


@router.post("/api/v1/runs", status_code=201)
@limiter.limit("10/minute")
async def create_run(request: Request, body: RunCreateRequest) -> RunResponse:
    """Create and queue a new pipeline run."""
    run_id = body.run_id or str(uuid.uuid4())
    run_store = request.app.state.run_store
    if run_store:
        await run_store.save_run(
            run_id,
            {
                "run_id": run_id,
                "status": "pending",
                "input_payload": body.input_payload,
                "timeout_seconds": body.timeout_seconds,
                "namespace": body.namespace,
            },
        )
    return RunResponse(run_id=run_id, status="pending")


@router.get("/api/v1/runs")
@limiter.limit("60/minute")
async def list_runs(
    request: Request,
    status: str | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 50,
) -> list[RunResponse]:
    """List runs, optionally filtered by status."""
    run_store = request.app.state.run_store
    if not run_store:
        return []
    runs = await run_store.list_runs(status=status, limit=limit)
    return [
        RunResponse(
            run_id=r.get("run_id", ""),
            status=r.get("status", "unknown"),
            output=r.get("output"),
            error=r.get("error"),
            metadata=r.get("metadata", {}),
        )
        for r in runs
    ]


@router.get("/api/v1/runs/{run_id}")
@limiter.limit("60/minute")
async def get_run(request: Request, run_id: ValidRunId) -> RunResponse:
    """Get run status and result."""
    run_store = request.app.state.run_store
    if not run_store:
        raise HTTPException(status_code=404, detail="No run store configured")
    run = await run_store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunResponse(
        run_id=run_id,
        status=run.get("status", "unknown"),
        output=run.get("output"),
        error=run.get("error"),
        metadata=run.get("metadata", {}),
    )


@router.post("/api/v1/runs/{run_id}/cancel")
@limiter.limit("10/minute")
async def cancel_run(request: Request, run_id: ValidRunId) -> RunResponse:
    """Cancel a running pipeline."""
    run_store = request.app.state.run_store
    if not run_store:
        raise HTTPException(status_code=404, detail="No run store configured")
    run = await run_store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    run["status"] = "cancelled"
    await run_store.save_run(run_id, run)
    return RunResponse(run_id=run_id, status="cancelled")


@router.get("/api/v1/runs/{run_id}/events")
@limiter.limit("60/minute")
async def get_run_events(
    request: Request,
    run_id: ValidRunId,
    after_index: Annotated[int, Query(ge=0)] = 0,
) -> list[EventResponse]:
    """Get events for a run."""
    event_store = request.app.state.event_store
    if not event_store:
        return []
    events = await event_store.list_events(run_id, after_index=after_index)
    return [
        EventResponse(
            type=e.type,
            timestamp=e.timestamp.isoformat(),
            run_id=e.run_id or "",
            payload=e.payload_dict(),
        )
        for e in events
    ]
