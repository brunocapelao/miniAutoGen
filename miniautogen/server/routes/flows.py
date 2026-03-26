"""Flow endpoints.

Note: "flow" is the user-facing term for what the codebase calls "pipeline".
The translation occurs in this router layer.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from miniautogen.server.models import ErrorResponse
from miniautogen.server.provider_protocol import ConsoleDataProvider


class CreateFlowRequest(BaseModel):
    name: str = Field(..., min_length=1)
    mode: str = Field(default="workflow")
    participants: list[str] | None = None
    leader: str | None = None
    target: str | None = None


class UpdateFlowRequest(BaseModel):
    mode: str | None = None
    participants: list[str] | None = None
    leader: str | None = None
    target: str | None = None


def flows_router(provider: ConsoleDataProvider) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["flows"])

    @router.get("/flows")
    async def list_flows() -> list[dict[str, Any]]:
        return provider.get_pipelines()

    @router.get("/flows/{name}", responses={404: {"model": ErrorResponse}})
    async def get_flow(name: str) -> dict[str, Any]:
        try:
            return provider.get_pipeline(name)
        except KeyError:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    error=f"Flow '{name}' not found",
                    code="flow_not_found",
                ).model_dump(),
            )

    @router.post("/flows", status_code=201)
    async def create_flow(body: CreateFlowRequest) -> dict[str, Any]:
        try:
            return provider.create_pipeline(
                body.name,
                mode=body.mode,
                participants=body.participants,
                leader=body.leader,
                target=body.target,
            )
        except (ValueError, FileExistsError) as exc:
            raise HTTPException(
                status_code=409,
                detail=ErrorResponse(
                    error=str(exc),
                    code="flow_exists",
                ).model_dump(),
            )

    @router.put("/flows/{name}", responses={404: {"model": ErrorResponse}})
    async def update_flow(name: str, body: UpdateFlowRequest) -> dict[str, Any]:
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    error="No fields to update",
                    code="empty_update",
                ).model_dump(),
            )
        try:
            return provider.update_pipeline(name, **updates)
        except KeyError:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    error=f"Flow '{name}' not found",
                    code="flow_not_found",
                ).model_dump(),
            )

    @router.delete("/flows/{name}", responses={404: {"model": ErrorResponse}})
    async def delete_flow(name: str) -> dict[str, Any]:
        try:
            return provider.delete_pipeline(name)
        except KeyError:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    error=f"Flow '{name}' not found",
                    code="flow_not_found",
                ).model_dump(),
            )

    return router
