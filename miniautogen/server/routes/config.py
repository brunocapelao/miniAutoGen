"""Config detail endpoint for settings editor."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from miniautogen.server.provider_protocol import ConsoleDataProvider


def config_router(provider: ConsoleDataProvider) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["config"])

    @router.get("/config/detail")
    async def get_config_detail() -> dict[str, Any]:
        return provider.get_config_detail()

    return router
