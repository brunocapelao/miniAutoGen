"""Engine profile endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from miniautogen.server.models import ErrorResponse
from miniautogen.server.provider_protocol import ConsoleDataProvider


class CreateEngineRequest(BaseModel):
    name: str = Field(..., min_length=1)
    provider: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    kind: str = "api"
    temperature: float = 0.2
    api_key_env: str | None = None
    endpoint: str | None = None


class UpdateEngineRequest(BaseModel):
    provider: str | None = None
    model: str | None = None
    kind: str | None = None
    temperature: float | None = None
    api_key_env: str | None = None
    endpoint: str | None = None


def engines_router(provider: ConsoleDataProvider) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["engines"])

    @router.get("/engines")
    async def list_engines() -> list[dict[str, Any]]:
        return provider.get_engines()

    @router.get("/engines/{name}", responses={404: {"model": ErrorResponse}})
    async def get_engine(name: str) -> dict[str, Any]:
        try:
            return provider.get_engine(name)
        except KeyError:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    error=f"Engine '{name}' not found",
                    code="engine_not_found",
                ).model_dump(),
            )

    @router.post("/engines", status_code=201)
    async def create_engine(body: CreateEngineRequest) -> dict[str, Any]:
        try:
            return provider.create_engine(
                body.name,
                provider=body.provider,
                model=body.model,
                kind=body.kind,
                temperature=body.temperature,
                api_key_env=body.api_key_env,
                endpoint=body.endpoint,
            )
        except (ValueError, FileExistsError) as exc:
            raise HTTPException(
                status_code=409,
                detail=ErrorResponse(
                    error=str(exc),
                    code="engine_exists",
                ).model_dump(),
            )

    @router.put("/engines/{name}", responses={404: {"model": ErrorResponse}})
    async def update_engine(name: str, body: UpdateEngineRequest) -> dict[str, Any]:
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
            return provider.update_engine(name, **updates)
        except KeyError:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    error=f"Engine '{name}' not found",
                    code="engine_not_found",
                ).model_dump(),
            )

    @router.delete("/engines/{name}", responses={404: {"model": ErrorResponse}})
    async def delete_engine(name: str) -> dict[str, Any]:
        try:
            return provider.delete_engine(name)
        except KeyError:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    error=f"Engine '{name}' not found",
                    code="engine_not_found",
                ).model_dump(),
            )

    return router
