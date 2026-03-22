"""Agents route stub — to be implemented in Task 3."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter


def agents_router(provider: Any) -> APIRouter:
    return APIRouter(prefix="/api/v1", tags=["agents"])
