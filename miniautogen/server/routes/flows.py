"""Flows route stub — to be implemented in Task 4."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter


def flows_router(provider: Any) -> APIRouter:
    return APIRouter(prefix="/api/v1", tags=["flows"])
