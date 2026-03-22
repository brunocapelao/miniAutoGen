"""Flow endpoints.

Note: "flow" is the user-facing term for what the codebase calls "pipeline".
The translation occurs in this router layer.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from miniautogen.server.models import ErrorResponse


def flows_router(provider: Any) -> APIRouter:
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

    return router
