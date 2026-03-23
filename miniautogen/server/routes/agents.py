"""Agent endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from miniautogen.server.models import ErrorResponse
from miniautogen.server.provider_protocol import ConsoleDataProvider


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

    return router
