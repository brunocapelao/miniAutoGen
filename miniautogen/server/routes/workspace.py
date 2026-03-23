"""Workspace endpoint."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from miniautogen.server.provider_protocol import ConsoleDataProvider


def workspace_router(provider: ConsoleDataProvider) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["workspace"])

    @router.get("/workspace")
    async def get_workspace() -> dict[str, Any]:
        return provider.get_config()

    return router
