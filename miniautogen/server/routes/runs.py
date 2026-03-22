"""Runs route stub — to be implemented in Task 5."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter


def runs_router(provider: Any) -> APIRouter:
    return APIRouter(prefix="/api/v1", tags=["runs"])
