"""Agent endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from miniautogen.server.models import ErrorResponse
from miniautogen.server.provider_protocol import ConsoleDataProvider


class CreateAgentRequest(BaseModel):
    name: str = Field(..., min_length=1)
    role: str = Field(..., min_length=1)
    goal: str = Field(..., min_length=1)
    engine_profile: str = Field(..., min_length=1)
    temperature: float | None = None


class UpdateAgentRequest(BaseModel):
    role: str | None = None
    goal: str | None = None
    engine_profile: str | None = None
    temperature: float | None = None


def agents_router(provider: ConsoleDataProvider) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["agents"])

    @router.get("/agents")
    async def list_agents() -> list[dict[str, Any]]:
        agents = [dict(a) for a in provider.get_agents()]
        for a in agents:
            a.setdefault("engine_type", a.get("engine_profile", "unknown"))
        return agents

    @router.get("/agents/{name}", responses={404: {"model": ErrorResponse}})
    async def get_agent(name: str) -> dict[str, Any]:
        try:
            agent = dict(provider.get_agent(name))
            agent.setdefault("engine_type", agent.get("engine_profile", "unknown"))
            return agent
        except KeyError:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    error=f"Agent '{name}' not found",
                    code="agent_not_found",
                ).model_dump(),
            )

    @router.post("/agents", status_code=201)
    async def create_agent(body: CreateAgentRequest) -> dict[str, Any]:
        try:
            return provider.create_agent(
                body.name,
                role=body.role,
                goal=body.goal,
                engine_profile=body.engine_profile,
                temperature=body.temperature,
            )
        except (ValueError, FileExistsError) as exc:
            raise HTTPException(
                status_code=409,
                detail=ErrorResponse(
                    error=str(exc),
                    code="agent_exists",
                ).model_dump(),
            )

    @router.put("/agents/{name}", responses={404: {"model": ErrorResponse}})
    async def update_agent(name: str, body: UpdateAgentRequest) -> dict[str, Any]:
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
            return provider.update_agent(name, **updates)
        except KeyError:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    error=f"Agent '{name}' not found",
                    code="agent_not_found",
                ).model_dump(),
            )

    @router.delete("/agents/{name}", responses={404: {"model": ErrorResponse}})
    async def delete_agent(name: str) -> dict[str, Any]:
        try:
            return provider.delete_agent(name)
        except KeyError:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    error=f"Agent '{name}' not found",
                    code="agent_not_found",
                ).model_dump(),
            )

    return router
