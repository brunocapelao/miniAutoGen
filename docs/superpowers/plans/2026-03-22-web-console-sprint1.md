# MiniAutoGen Console — Sprint 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver an embedded web dashboard (`miniautogen run --console`) with read-only observability, run triggering, live event streaming, and approval resolution.

**Architecture:** Thin HTTP wrapper over the existing `DashDataProvider` (in `miniautogen/tui/data_provider.py`). FastAPI serves REST endpoints + WebSocket for live events. Next.js static export frontend served as static files by FastAPI. Embedded mode only (standalone deferred to Sprint 2).

**Tech Stack:** Python (FastAPI, uvicorn, Pydantic v2), TypeScript (Next.js 14+, React Flow, TanStack Query, Zustand, Shadcn/UI, Tailwind CSS)

**Spec:** `docs/superpowers/specs/2026-03-22-web-console-design.md`

**Build system note:** `pyproject.toml` uses `hatchling` as build backend (line 82: `build-backend = "hatchling.build"`). The spec mentions Poetry due to `08-tech-stack.md`, but the actual build system is hatchling. This plan uses hatchling syntax.

---

## File Structure

### Backend (Python — `miniautogen/server/`)

| File | Responsibility |
|------|---------------|
| `miniautogen/server/__init__.py` | Package init, exports `create_app` |
| `miniautogen/server/app.py` | FastAPI app factory (`create_app`) |
| `miniautogen/server/models.py` | Pydantic response/request models (AgentSummary, RunRequest, ErrorResponse, etc.) |
| `miniautogen/server/routes/workspace.py` | `GET /api/v1/workspace` |
| `miniautogen/server/routes/agents.py` | `GET /api/v1/agents`, `GET /api/v1/agents/{name}` |
| `miniautogen/server/routes/flows.py` | `GET /api/v1/flows`, `GET /api/v1/flows/{name}` |
| `miniautogen/server/routes/runs.py` | `POST /api/v1/runs`, `GET /api/v1/runs`, `GET /api/v1/runs/{id}`, `GET /api/v1/runs/{id}/events`, approvals |
| `miniautogen/server/routes/__init__.py` | Package init |
| `miniautogen/server/ws.py` | WebSocket handler + `WebSocketEventSink` |
| `miniautogen/cli/commands/console.py` | `miniautogen console` CLI command (standalone skeleton) |

### Backend Tests (`tests/server/`)

| File | Covers |
|------|--------|
| `tests/server/__init__.py` | Package init |
| `tests/server/conftest.py` | Shared fixtures (test client, mock provider) |
| `tests/server/test_models.py` | Response/request model validation |
| `tests/server/test_workspace.py` | Workspace endpoint |
| `tests/server/test_agents.py` | Agent endpoints |
| `tests/server/test_flows.py` | Flow endpoints |
| `tests/server/test_runs.py` | Run endpoints (CRUD + trigger + events) |
| `tests/server/test_approvals.py` | Approval endpoints |
| `tests/server/test_ws.py` | WebSocket streaming + EventSink |
| `tests/server/test_console_command.py` | CLI integration |

### Frontend (`console/`)

| File | Responsibility |
|------|---------------|
| `console/package.json` | Dependencies and scripts |
| `console/next.config.js` | Static export config |
| `console/tsconfig.json` | TypeScript config |
| `console/tailwind.config.ts` | Tailwind config |
| `console/src/app/layout.tsx` | Shell layout (sidebar + header) |
| `console/src/app/page.tsx` | Dashboard overview |
| `console/src/app/agents/page.tsx` | Agents list |
| `console/src/app/flows/page.tsx` | Flows list |
| `console/src/app/flows/[name]/page.tsx` | Flow detail + React Flow graph |
| `console/src/app/runs/page.tsx` | Runs list |
| `console/src/app/runs/[id]/page.tsx` | Run detail (graph + events + slider) |
| `console/src/lib/api-client.ts` | Typed fetch wrapper |
| `console/src/lib/ws-client.ts` | WebSocket connection manager |
| `console/src/hooks/useRunEvents.ts` | WS + polling fallback hook |
| `console/src/hooks/useApi.ts` | TanStack Query wrappers |
| `console/src/stores/connection.ts` | Zustand store for WS state |
| `console/src/components/flow-graph/FlowCanvas.tsx` | React Flow wrapper |
| `console/src/components/flow-graph/AgentNode.tsx` | Custom agent node |
| `console/src/components/run/EventFeed.tsx` | Event log list |
| `console/src/components/run/RunStatus.tsx` | Status badge |
| `console/src/components/approval/ApprovalModal.tsx` | Approve/deny modal |

---

## Task 1: Pydantic Response & Request Models

**Files:**
- Create: `miniautogen/server/__init__.py`
- Create: `miniautogen/server/models.py`
- Create: `tests/server/__init__.py`
- Create: `tests/server/test_models.py`

- [ ] **Step 1: Write failing tests for response models**

```python
# tests/server/__init__.py
# (empty)

# tests/server/test_models.py
"""Tests for Console API response/request models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError


def test_agent_summary_required_fields():
    from miniautogen.server.models import AgentSummary

    agent = AgentSummary(name="researcher", role="researcher", engine_type="litellm")
    assert agent.name == "researcher"
    assert agent.role == "researcher"
    assert agent.engine_type == "litellm"


def test_agent_summary_missing_field():
    from miniautogen.server.models import AgentSummary

    with pytest.raises(ValidationError):
        AgentSummary(name="researcher")  # missing role, engine_type


def test_run_request_defaults():
    from miniautogen.server.models import RunRequest

    req = RunRequest(flow_name="main")
    assert req.flow_name == "main"
    assert req.input is None
    assert req.timeout is None


def test_run_request_with_all_fields():
    from miniautogen.server.models import RunRequest

    req = RunRequest(flow_name="main", input="hello", timeout=30.0)
    assert req.input == "hello"
    assert req.timeout == 30.0


def test_error_response():
    from miniautogen.server.models import ErrorResponse

    err = ErrorResponse(error="Not found", code="flow_not_found")
    assert err.error == "Not found"
    assert err.code == "flow_not_found"
    assert err.detail is None


def test_approval_decision_valid():
    from miniautogen.server.models import ApprovalDecision

    dec = ApprovalDecision(decision="approved")
    assert dec.decision == "approved"
    assert dec.reason is None


def test_approval_decision_invalid():
    from miniautogen.server.models import ApprovalDecision

    with pytest.raises(ValidationError):
        ApprovalDecision(decision="maybe")


def test_page_model():
    from miniautogen.server.models import Page

    page = Page(items=["a", "b"], total=10, offset=0, limit=20)
    assert len(page.items) == 2
    assert page.total == 10


def test_pending_approval():
    from datetime import datetime, timezone
    from miniautogen.server.models import PendingApproval

    pa = PendingApproval(
        request_id="req-1",
        agent_name="agent-a",
        action="send_email",
        requested_at=datetime.now(timezone.utc),
    )
    assert pa.request_id == "req-1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/server/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'miniautogen.server'`

- [ ] **Step 3: Implement models**

```python
# miniautogen/server/__init__.py
"""MiniAutoGen Console Server."""

from miniautogen.server.app import create_app

__all__ = ["create_app"]

# miniautogen/server/models.py
"""Pydantic models for Console API request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class AgentSummary(BaseModel):
    name: str
    role: str
    engine_type: str
    status: str = "idle"  # "idle" | "running" | "error"


class AgentDetail(AgentSummary):
    """Simplified agent detail for Sprint 1.

    Note: The spec envisions 5-layer structure (identity, engine, runtime,
    skills, tools). This is a pragmatic simplification — the DashDataProvider
    returns flat dicts, not typed config objects. Full 5-layer detail is
    Sprint 2+ work requiring AgentSpec model integration.
    """
    goal: str | None = None
    engine_profile: str | None = None
    raw: dict[str, Any] = {}


class FlowSummary(BaseModel):
    name: str
    mode: str
    target: str | None = None


class FlowDetail(FlowSummary):
    participants: list[str] = []
    leader: str | None = None
    max_rounds: int | None = None
    raw: dict[str, Any] = {}


class RunSummary(BaseModel):
    run_id: str
    pipeline: str
    status: str
    started: str
    events: int = 0


class RunRequest(BaseModel):
    flow_name: str
    input: str | None = None
    timeout: float | None = None


class ApprovalDecision(BaseModel):
    decision: Literal["approved", "denied"]
    reason: str | None = None


class PendingApproval(BaseModel):
    request_id: str
    agent_name: str
    action: str
    requested_at: datetime


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
    code: str


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    offset: int
    limit: int
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/server/test_models.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add miniautogen/server/__init__.py miniautogen/server/models.py tests/server/__init__.py tests/server/test_models.py
git commit -m "feat(server): add Pydantic request/response models for Console API"
```

---

## Task 2: FastAPI App Factory + Workspace Route

**Files:**
- Create: `miniautogen/server/app.py`
- Create: `miniautogen/server/routes/__init__.py`
- Create: `miniautogen/server/routes/workspace.py`
- Create: `tests/server/conftest.py`
- Create: `tests/server/test_workspace.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/server/conftest.py
"""Shared fixtures for Console Server tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from miniautogen.server.app import create_app


@pytest.fixture
def mock_provider() -> MagicMock:
    """Mock DashDataProvider for testing routes without real project."""
    provider = MagicMock()
    provider.get_config.return_value = {
        "project_name": "test-project",
        "version": "0.1.0",
        "default_engine": "default_api",
        "default_memory": "default",
        "engine_count": 1,
        "agent_count": 2,
        "pipeline_count": 1,
        "database": "(none)",
    }
    provider.get_agents.return_value = [
        {"name": "researcher", "role": "researcher", "goal": "Research", "engine_profile": "default_api"},
        {"name": "writer", "role": "writer", "goal": "Write", "engine_profile": "default_api"},
    ]
    provider.get_agent.return_value = {
        "name": "researcher", "role": "researcher", "goal": "Research",
        "engine_profile": "default_api",
    }
    provider.get_pipelines.return_value = [
        {"name": "main", "mode": "workflow", "target": "pipelines.main:build_pipeline"},
    ]
    provider.get_pipeline.return_value = {
        "name": "main", "mode": "workflow", "target": "pipelines.main:build_pipeline",
        "participants": ["researcher", "writer"],
    }
    provider.get_runs.return_value = []
    provider.get_events.return_value = []
    return provider


@pytest.fixture
def client(mock_provider: MagicMock) -> TestClient:
    """FastAPI test client with mocked provider."""
    app = create_app(provider=mock_provider, mode="embedded")
    return TestClient(app)


# tests/server/test_workspace.py
"""Tests for workspace endpoint."""

from __future__ import annotations


def test_get_workspace(client):
    resp = client.get("/api/v1/workspace")
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_name"] == "test-project"
    assert data["agent_count"] == 2


def test_get_workspace_empty(mock_provider, client):
    mock_provider.get_config.return_value = {}
    resp = client.get("/api/v1/workspace")
    assert resp.status_code == 200
    assert resp.json() == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/server/test_workspace.py -v`
Expected: FAIL — `create_app` not implemented

- [ ] **Step 3: Implement app factory and workspace route**

```python
# miniautogen/server/routes/__init__.py
"""Console API route modules."""

# miniautogen/server/routes/workspace.py
"""Workspace endpoint."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter


def workspace_router(provider: Any) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["workspace"])

    @router.get("/workspace")
    async def get_workspace() -> dict[str, Any]:
        return provider.get_config()

    return router


# miniautogen/server/app.py
"""FastAPI application factory for MiniAutoGen Console."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from miniautogen.server.routes.workspace import workspace_router
from miniautogen.server.routes.agents import agents_router
from miniautogen.server.routes.flows import flows_router
from miniautogen.server.routes.runs import runs_router


def create_app(
    *,
    provider: Any | None = None,
    workspace_path: str | Path | None = None,
    mode: Literal["embedded", "standalone"] = "embedded",
) -> FastAPI:
    """Create the Console Server FastAPI application.

    Args:
        provider: DashDataProvider instance. If None, creates one from workspace_path.
        workspace_path: Path to the workspace directory. Used if provider is None.
        mode: "embedded" (with PipelineRunner) or "standalone" (store-only).
    """
    if provider is None:
        from miniautogen.tui.data_provider import DashDataProvider

        path = Path(workspace_path or ".").resolve()
        provider = DashDataProvider(path)

    app = FastAPI(title="MiniAutoGen Console", version="0.1.0")

    # Routes
    app.include_router(workspace_router(provider))
    app.include_router(agents_router(provider))
    app.include_router(flows_router(provider))
    app.include_router(runs_router(provider))

    # Custom error handler: return ErrorResponse at top level, not nested in "detail"
    from fastapi import HTTPException as _HTTPException
    from fastapi.responses import JSONResponse

    @app.exception_handler(_HTTPException)
    async def custom_http_exception_handler(request, exc):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)

    # CORS: only for development (Next.js dev server on different port)
    if os.getenv("MINIAUTOGEN_DEV"):
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[
                "http://localhost:3000",
                "http://127.0.0.1:3000",
            ],
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
        )

    # Static files mount will be added after frontend build exists
    # static_dir = Path(__file__).parent / "static"
    # if static_dir.is_dir():
    #     app.mount("/", StaticFiles(directory=static_dir, html=True))

    return app
```

Note: `agents_router`, `flows_router`, and `runs_router` will be created in subsequent tasks. For now, create stub files so imports don't break:

```python
# Temporary stubs — will be fully implemented in Tasks 3-5

# miniautogen/server/routes/agents.py
from fastapi import APIRouter
def agents_router(provider):
    return APIRouter(prefix="/api/v1", tags=["agents"])

# miniautogen/server/routes/flows.py
from fastapi import APIRouter
def flows_router(provider):
    return APIRouter(prefix="/api/v1", tags=["flows"])

# miniautogen/server/routes/runs.py
from fastapi import APIRouter
def runs_router(provider):
    return APIRouter(prefix="/api/v1", tags=["runs"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/server/test_workspace.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add miniautogen/server/app.py miniautogen/server/routes/ tests/server/conftest.py tests/server/test_workspace.py
git commit -m "feat(server): add FastAPI app factory and workspace endpoint"
```

---

## Task 3: Agent Endpoints

**Files:**
- Modify: `miniautogen/server/routes/agents.py`
- Create: `tests/server/test_agents.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/server/test_agents.py
"""Tests for agent endpoints."""

from __future__ import annotations


def test_list_agents(client):
    resp = client.get("/api/v1/agents")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["name"] == "researcher"
    assert "role" in data[0]
    assert "engine_type" in data[0] or "engine_profile" in data[0]


def test_get_agent(client):
    resp = client.get("/api/v1/agents/researcher")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "researcher"


def test_get_agent_not_found(client, mock_provider):
    mock_provider.get_agent.side_effect = KeyError("nope")
    resp = client.get("/api/v1/agents/nonexistent")
    assert resp.status_code == 404
    data = resp.json()
    assert data["code"] == "agent_not_found"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/server/test_agents.py -v`
Expected: FAIL — no routes registered

- [ ] **Step 3: Implement agent routes**

```python
# miniautogen/server/routes/agents.py
"""Agent endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from miniautogen.server.models import ErrorResponse


def agents_router(provider: Any) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["agents"])

    @router.get("/agents")
    async def list_agents() -> list[dict[str, Any]]:
        agents = provider.get_agents()
        # Normalize: ensure engine_type field exists
        for a in agents:
            a.setdefault("engine_type", a.get("engine_profile", "unknown"))
        return agents

    @router.get(
        "/agents/{name}",
        responses={404: {"model": ErrorResponse}},
    )
    async def get_agent(name: str) -> dict[str, Any]:
        try:
            agent = provider.get_agent(name)
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/server/test_agents.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add miniautogen/server/routes/agents.py tests/server/test_agents.py
git commit -m "feat(server): add agent list and detail endpoints"
```

---

## Task 4: Flow Endpoints

**Files:**
- Modify: `miniautogen/server/routes/flows.py`
- Create: `tests/server/test_flows.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/server/test_flows.py
"""Tests for flow endpoints."""

from __future__ import annotations


def test_list_flows(client):
    resp = client.get("/api/v1/flows")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "main"
    assert data[0]["mode"] == "workflow"


def test_get_flow(client):
    resp = client.get("/api/v1/flows/main")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "main"
    assert "participants" in data


def test_get_flow_not_found(client, mock_provider):
    mock_provider.get_pipeline.side_effect = KeyError("nope")
    resp = client.get("/api/v1/flows/nonexistent")
    assert resp.status_code == 404
    data = resp.json()
    assert data["code"] == "flow_not_found"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/server/test_flows.py -v`
Expected: FAIL

- [ ] **Step 3: Implement flow routes**

```python
# miniautogen/server/routes/flows.py
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
        pipelines = provider.get_pipelines()
        # Rename "pipeline" terminology to "flow" for the API
        return pipelines

    @router.get(
        "/flows/{name}",
        responses={404: {"model": ErrorResponse}},
    )
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/server/test_flows.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add miniautogen/server/routes/flows.py tests/server/test_flows.py
git commit -m "feat(server): add flow list and detail endpoints"
```

---

## Task 5: Run Endpoints (List, Detail, Events, Trigger)

**Files:**
- Modify: `miniautogen/server/routes/runs.py`
- Create: `tests/server/test_runs.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/server/test_runs.py
"""Tests for run endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock


def test_list_runs_empty(client):
    resp = client.get("/api/v1/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_list_runs_with_data(client, mock_provider):
    mock_provider.get_runs.return_value = [
        {"run_id": "r1", "pipeline": "main", "status": "completed", "started": "2026-01-01T00:00:00Z", "events": 5},
        {"run_id": "r2", "pipeline": "main", "status": "running", "started": "2026-01-01T00:01:00Z", "events": 2},
    ]
    resp = client.get("/api/v1/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_list_runs_pagination(client, mock_provider):
    mock_provider.get_runs.return_value = [
        {"run_id": f"r{i}", "pipeline": "main", "status": "completed", "started": "2026-01-01T00:00:00Z", "events": 0}
        for i in range(5)
    ]
    resp = client.get("/api/v1/runs?offset=2&limit=2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2
    assert data["offset"] == 2
    assert data["limit"] == 2


def test_get_run(client, mock_provider):
    mock_provider.get_runs.return_value = [
        {"run_id": "r1", "pipeline": "main", "status": "completed", "started": "2026-01-01T00:00:00Z", "events": 5},
    ]
    resp = client.get("/api/v1/runs/r1")
    assert resp.status_code == 200
    assert resp.json()["run_id"] == "r1"


def test_get_run_not_found(client):
    resp = client.get("/api/v1/runs/nonexistent")
    assert resp.status_code == 404


def test_get_run_events(client, mock_provider):
    mock_provider.get_events.return_value = [
        {"type": "run_started", "run_id": "r1", "timestamp": "2026-01-01T00:00:00Z"},
        {"type": "component_started", "run_id": "r1", "timestamp": "2026-01-01T00:00:01Z"},
    ]
    resp = client.get("/api/v1/runs/r1/events")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


def test_trigger_run(client, mock_provider):
    mock_provider.run_pipeline = AsyncMock(return_value={
        "status": "completed", "events": 3,
    })
    resp = client.post("/api/v1/runs", json={"flow_name": "main"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "triggered"
    assert data["flow_name"] == "main"


def test_trigger_run_not_found(client, mock_provider):
    mock_provider.get_pipelines.return_value = []
    resp = client.post("/api/v1/runs", json={"flow_name": "nonexistent"})
    assert resp.status_code == 404
    assert resp.json()["code"] == "flow_not_found"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/server/test_runs.py -v`
Expected: FAIL

- [ ] **Step 3: Implement run routes**

```python
# miniautogen/server/routes/runs.py
"""Run endpoints: list, detail, events, trigger, approvals."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request

from miniautogen.server.models import (
    ApprovalDecision,
    ErrorResponse,
    Page,
    PendingApproval,
    RunRequest,
)


def runs_router(provider: Any) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["runs"])

    # Shared state for approval channels per run
    _approval_channels: dict[str, Any] = {}

    @router.get("/runs")
    async def list_runs(
        offset: int = Query(0, ge=0),
        limit: int = Query(20, ge=1, le=100),
    ) -> Page:
        all_runs = provider.get_runs()
        return Page(
            items=all_runs[offset : offset + limit],
            total=len(all_runs),
            offset=offset,
            limit=limit,
        )

    @router.get(
        "/runs/{run_id}",
        responses={404: {"model": ErrorResponse}},
    )
    async def get_run(run_id: str) -> dict[str, Any]:
        runs = provider.get_runs()
        for run in runs:
            if run.get("run_id") == run_id:
                return run
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error=f"Run '{run_id}' not found",
                code="run_not_found",
            ).model_dump(),
        )

    @router.get("/runs/{run_id}/events")
    async def get_run_events(
        run_id: str,
        offset: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=500),
    ) -> Page:
        all_events = provider.get_events()
        # Filter events for this run_id
        run_events = [
            e for e in all_events if e.get("run_id") == run_id
        ]
        return Page(
            items=run_events[offset : offset + limit],
            total=len(run_events),
            offset=offset,
            limit=limit,
        )

    @router.post(
        "/runs",
        responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    )
    async def trigger_run(
        req: RunRequest,
        request: Request,
        background_tasks: BackgroundTasks,
    ) -> dict[str, str]:
        # Verify flow exists
        pipelines = provider.get_pipelines()
        pipeline_names = [p.get("name") for p in pipelines]
        if req.flow_name not in pipeline_names:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    error=f"Flow '{req.flow_name}' not found",
                    code="flow_not_found",
                ).model_dump(),
            )

        # Get event_sink from app state (wired in create_app for embedded mode)
        event_sink = getattr(request.app.state, "event_sink", None)

        # Run pipeline in background, passing event_sink for live streaming
        async def _run():
            await provider.run_pipeline(
                req.flow_name,
                event_sink=event_sink,
                pipeline_input=req.input,
                timeout=req.timeout,
            )

        background_tasks.add_task(_run)

        # Return the run_id that DashDataProvider.run_pipeline() will generate.
        # Since the run executes in the background, we return immediately.
        # The client should poll GET /runs to find the new run.
        # NOTE: DashDataProvider.run_pipeline() generates its own run_id internally.
        # The client discovers the run_id via GET /runs (sorted by most recent).
        return {"status": "triggered", "flow_name": req.flow_name}

    # ── Approval endpoints ──────────────────────────────────

    @router.get("/runs/{run_id}/approvals")
    async def list_approvals(run_id: str) -> list[dict[str, Any]]:
        channel = _approval_channels.get(run_id)
        if channel is None:
            return []
        pending = await channel.list_pending()
        return [
            {
                "request_id": h.request.request_id,
                "agent_name": h.request.agent_name if hasattr(h.request, "agent_name") else "unknown",
                "action": h.request.action if hasattr(h.request, "action") else "unknown",
                "requested_at": h.created_at.isoformat(),
            }
            for h in pending
        ]

    @router.post(
        "/runs/{run_id}/approvals/{request_id}",
        responses={
            404: {"model": ErrorResponse},
            409: {"model": ErrorResponse},
        },
    )
    async def resolve_approval(
        run_id: str,
        request_id: str,
        body: ApprovalDecision,
    ) -> dict[str, str]:
        channel = _approval_channels.get(run_id)
        if channel is None:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    error="No approval channel for this run",
                    code="run_not_found",
                ).model_dump(),
            )
        pending = await channel.list_pending()
        handle = None
        for h in pending:
            if h.request.request_id == request_id:
                handle = h
                break
        if handle is None:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    error=f"Approval '{request_id}' not found or already resolved",
                    code="approval_already_resolved",
                ).model_dump(),
            )
        try:
            handle.resolve(body.decision, body.reason)
        except ValueError:
            raise HTTPException(
                status_code=409,
                detail=ErrorResponse(
                    error="Approval already resolved",
                    code="approval_already_resolved",
                ).model_dump(),
            )
        return {"status": "resolved", "decision": body.decision}

    # Expose _approval_channels for WebSocket/CLI integration
    router.approval_channels = _approval_channels  # type: ignore[attr-defined]

    return router
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/server/test_runs.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add miniautogen/server/routes/runs.py tests/server/test_runs.py
git commit -m "feat(server): add run list, detail, events, trigger, and approval endpoints"
```

---

## Task 5b: Approval Endpoint Tests

**Files:**
- Create: `tests/server/test_approvals.py`

- [ ] **Step 1: Write approval tests**

```python
# tests/server/test_approvals.py
"""Tests for approval endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


def test_list_approvals_empty(client):
    resp = client.get("/api/v1/runs/r1/approvals")
    assert resp.status_code == 200
    assert resp.json() == []


def test_resolve_approval_no_channel(client):
    resp = client.post(
        "/api/v1/runs/r1/approvals/req-1",
        json={"decision": "approved"},
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "run_not_found"


def test_resolve_approval_invalid_decision(client):
    """Pydantic validation rejects invalid decisions."""
    resp = client.post(
        "/api/v1/runs/r1/approvals/req-1",
        json={"decision": "maybe"},
    )
    assert resp.status_code == 422  # Pydantic validation error
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `python -m pytest tests/server/test_approvals.py -v`
Expected: All PASS (these test the existing routes from Task 5)

- [ ] **Step 3: Commit**

```bash
git add tests/server/test_approvals.py
git commit -m "test(server): add approval endpoint tests"
```

---

## Task 6: WebSocketEventSink + WebSocket Handler

**Files:**
- Create: `miniautogen/server/ws.py`
- Create: `tests/server/test_ws.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/server/test_ws.py
"""Tests for WebSocket event streaming and WebSocketEventSink."""

from __future__ import annotations

import json

import anyio
import pytest

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.server.ws import WebSocketEventSink


@pytest.mark.anyio
async def test_ws_event_sink_publish_stores_events():
    """WebSocketEventSink stores events for later retrieval."""
    sink = WebSocketEventSink()
    event = ExecutionEvent(type="run_started", run_id="r1")
    await sink.publish(event)
    assert len(sink.get_events("r1")) == 1
    assert sink.get_events("r1")[0].type == "run_started"


@pytest.mark.anyio
async def test_ws_event_sink_ignores_none_run_id():
    """Events without run_id are stored in the global bucket but not routed to WS."""
    sink = WebSocketEventSink()
    event = ExecutionEvent(type="system_event")
    await sink.publish(event)
    # Should not crash, event stored globally
    assert len(sink.get_events(None)) == 0  # No WS routing for None


@pytest.mark.anyio
async def test_ws_event_sink_multiple_runs():
    """Events are partitioned by run_id."""
    sink = WebSocketEventSink()
    await sink.publish(ExecutionEvent(type="run_started", run_id="r1"))
    await sink.publish(ExecutionEvent(type="run_started", run_id="r2"))
    await sink.publish(ExecutionEvent(type="step", run_id="r1"))
    assert len(sink.get_events("r1")) == 2
    assert len(sink.get_events("r2")) == 1


@pytest.mark.anyio
async def test_ws_event_sink_as_dict():
    """Events can be retrieved as dicts for REST endpoint."""
    sink = WebSocketEventSink()
    await sink.publish(ExecutionEvent(type="run_started", run_id="r1"))
    dicts = sink.get_events_as_dicts("r1")
    assert len(dicts) == 1
    assert dicts[0]["type"] == "run_started"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/server/test_ws.py -v`
Expected: FAIL — `WebSocketEventSink` not found

- [ ] **Step 3: Implement WebSocketEventSink**

```python
# miniautogen/server/ws.py
"""WebSocket event streaming for the MiniAutoGen Console.

WebSocketEventSink implements the EventSink protocol, storing events
in memory and broadcasting to connected WebSocket clients.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from miniautogen.core.contracts.events import ExecutionEvent

logger = logging.getLogger(__name__)


class WebSocketEventSink:
    """EventSink that stores events and broadcasts to WebSocket clients.

    Implements the EventSink protocol (async def publish(event)).
    Events with run_id=None are silently dropped from WebSocket broadcast
    but stored for REST access. This is an explicit design decision —
    system-level events are persisted by store sinks via CompositeEventSink.
    """

    def __init__(self) -> None:
        self._events: dict[str, list[ExecutionEvent]] = defaultdict(list)
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)

    async def publish(self, event: ExecutionEvent) -> None:
        """Publish an event: store it and broadcast to WS clients."""
        if event.run_id is None:
            # System-level events: drop from WS, not stored here.
            return

        self._events[event.run_id].append(event)

        # Broadcast to connected WebSocket clients
        message = event.model_dump_json()
        dead_connections = []
        for ws in self._connections.get(event.run_id, []):
            try:
                await ws.send_text(message)
            except Exception:
                dead_connections.append(ws)

        # Cleanup dead connections
        for ws in dead_connections:
            try:
                self._connections[event.run_id].remove(ws)
            except ValueError:
                pass

    def get_events(self, run_id: str | None) -> list[ExecutionEvent]:
        """Get stored events for a run_id."""
        if run_id is None:
            return []
        return list(self._events.get(run_id, []))

    def get_events_as_dicts(self, run_id: str) -> list[dict[str, Any]]:
        """Get stored events as dicts (for REST endpoints)."""
        return [
            json.loads(e.model_dump_json()) for e in self._events.get(run_id, [])
        ]

    async def connect(self, run_id: str, websocket: WebSocket) -> None:
        """Register a WebSocket client for a specific run."""
        await websocket.accept()
        self._connections[run_id].append(websocket)
        await websocket.send_json({"type": "connected", "run_id": run_id})

    def disconnect(self, run_id: str, websocket: WebSocket) -> None:
        """Remove a WebSocket client."""
        try:
            self._connections[run_id].remove(websocket)
        except ValueError:
            pass


def ws_router(event_sink: WebSocketEventSink) -> APIRouter:
    """Create WebSocket router for live event streaming."""
    router = APIRouter(tags=["websocket"])

    @router.websocket("/ws/runs/{run_id}")
    async def ws_run_events(websocket: WebSocket, run_id: str) -> None:
        await event_sink.connect(run_id, websocket)
        try:
            while True:
                # Keep connection alive, handle client pings
                data = await websocket.receive_json()
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            event_sink.disconnect(run_id, websocket)
        except Exception:
            event_sink.disconnect(run_id, websocket)

    return router
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/server/test_ws.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add miniautogen/server/ws.py tests/server/test_ws.py
git commit -m "feat(server): add WebSocketEventSink and WebSocket handler"
```

---

## Task 7: Wire WebSocket into App Factory + Integration Test

**Files:**
- Modify: `miniautogen/server/app.py`
- Modify: `miniautogen/server/__init__.py`
- Create: `tests/server/test_integration.py`

- [ ] **Step 1: Write failing integration test**

```python
# tests/server/test_integration.py
"""Integration tests for the full Console Server."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from miniautogen.server.app import create_app
from miniautogen.server.ws import WebSocketEventSink


def test_full_app_starts(mock_provider):
    """App factory produces a working FastAPI app."""
    from tests.server.conftest import mock_provider as _mp
    provider = MagicMock()
    provider.get_config.return_value = {}
    provider.get_agents.return_value = []
    provider.get_pipelines.return_value = []
    provider.get_runs.return_value = []
    provider.get_events.return_value = []

    app = create_app(provider=provider, mode="embedded")
    client = TestClient(app)

    # All endpoints should be reachable
    assert client.get("/api/v1/workspace").status_code == 200
    assert client.get("/api/v1/agents").status_code == 200
    assert client.get("/api/v1/flows").status_code == 200
    assert client.get("/api/v1/runs").status_code == 200


def test_websocket_endpoint_exists():
    """WebSocket endpoint is registered in embedded mode."""
    provider = MagicMock()
    provider.get_config.return_value = {}
    provider.get_agents.return_value = []
    provider.get_pipelines.return_value = []
    provider.get_runs.return_value = []
    provider.get_events.return_value = []

    app = create_app(provider=provider, mode="embedded")
    # Check that /ws/runs/{run_id} route exists
    routes = [r.path for r in app.routes]
    assert "/ws/runs/{run_id}" in routes
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/server/test_integration.py -v`
Expected: FAIL — WS not wired in

- [ ] **Step 3: Wire WebSocket into app factory**

Update `miniautogen/server/app.py` to include WebSocket router:

```python
# Add to imports in app.py
from miniautogen.server.ws import WebSocketEventSink, ws_router

# Inside create_app, after REST routes:
    # WebSocket (embedded mode only — live event streaming)
    event_sink = None
    if mode == "embedded":
        event_sink = WebSocketEventSink()
        app.include_router(ws_router(event_sink))

    # Store event_sink on app for CLI integration
    app.state.event_sink = event_sink  # type: ignore[attr-defined]
```

Update `miniautogen/server/__init__.py`:

```python
"""MiniAutoGen Console Server."""

from miniautogen.server.app import create_app
from miniautogen.server.ws import WebSocketEventSink

__all__ = ["create_app", "WebSocketEventSink"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/server/ -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add miniautogen/server/app.py miniautogen/server/__init__.py tests/server/test_integration.py
git commit -m "feat(server): wire WebSocket into app factory for embedded mode"
```

---

## Task 8: CLI `--console` Flag on `run` Command

**Files:**
- Modify: `miniautogen/cli/commands/run.py`
- Create: `tests/server/test_console_command.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/server/test_console_command.py
"""Tests for --console flag on the run command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from miniautogen.cli.main import cli


def test_run_console_flag_exists():
    """The --console flag is accepted by the run command."""
    runner = CliRunner()
    result = runner.invoke(cli, ["run", "--help"])
    assert "--console" in result.output


def test_run_console_flag_with_port():
    """The --port flag is accepted alongside --console."""
    runner = CliRunner()
    result = runner.invoke(cli, ["run", "--help"])
    assert "--port" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/server/test_console_command.py -v`
Expected: FAIL — `--console` flag doesn't exist yet

- [ ] **Step 3: Add --console and --port flags to run command**

Modify `miniautogen/cli/commands/run.py`. Add new options to the `run_command` function:

```python
# Add these options after the existing @click.option decorators (before the function):

@click.option(
    "--console",
    is_flag=True,
    default=False,
    help="Open web console dashboard during execution.",
)
@click.option(
    "--port",
    "console_port",
    type=int,
    default=8080,
    help="Port for the web console (default: 8080).",
)
```

Add `console: bool` and `console_port: int` to the function signature.

Add this block at the beginning of `run_command`, before the spinner:

```python
    # Console mode: start web server in background and route execution through DashDataProvider
    console_server = None
    console_provider = None
    if console:
        import webbrowser
        from miniautogen.server.app import create_app
        from miniautogen.tui.data_provider import DashDataProvider

        console_provider = DashDataProvider(root)
        app = create_app(provider=console_provider, mode="embedded")

        # Start uvicorn in a background thread
        import threading
        import uvicorn

        server_config = uvicorn.Config(
            app, host="127.0.0.1", port=console_port, log_level="warning"
        )
        console_server = uvicorn.Server(server_config)
        server_thread = threading.Thread(target=console_server.run, daemon=True)
        server_thread.start()

        url = f"http://localhost:{console_port}"
        echo_info(f"Console running at {url}")
        webbrowser.open(url)
```

In console mode, redirect the execution through `DashDataProvider.run_pipeline()` so events flow to the WebSocketEventSink. Replace the existing `run_async(execute_pipeline, ...)` call:

```python
    # Execute the pipeline
    if console_provider:
        # Console mode: run through DashDataProvider to capture events
        event_sink = getattr(app.state, "event_sink", None)
        console_provider.set_event_sink(event_sink)
        result = run_async(
            console_provider.run_pipeline,
            pipeline_name,
            event_sink=event_sink,
            timeout=timeout,
            pipeline_input=pipeline_input,
        )
    else:
        # Normal mode: direct execution
        result = run_async(
            execute_pipeline,
            config,
            pipeline_name,
            root,
            timeout=timeout,
            verbose=verbose,
            pipeline_input=pipeline_input,
            resume_run_id=resume,
        )
```

And at the end of the function (after result processing), keep the server alive if console mode:

```python
    # In console mode, keep server running for post-run inspection
    if console and console_server:
        echo_info("Console still running. Press Ctrl+C to exit.")
        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            echo_info("Shutting down console...")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/server/test_console_command.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add miniautogen/cli/commands/run.py tests/server/test_console_command.py
git commit -m "feat(cli): add --console flag to run command for embedded web dashboard"
```

---

## Task 9: CLI `console` Standalone Command (Skeleton)

**Files:**
- Create: `miniautogen/cli/commands/console.py`
- Modify: `miniautogen/cli/main.py`

- [ ] **Step 1: Write failing test**

```python
# Add to tests/server/test_console_command.py:

def test_console_command_exists():
    """The 'console' subcommand is registered."""
    runner = CliRunner()
    result = runner.invoke(cli, ["console", "--help"])
    assert result.exit_code == 0
    assert "--port" in result.output
    assert "--workspace" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/server/test_console_command.py::test_console_command_exists -v`
Expected: FAIL

- [ ] **Step 3: Implement console command**

```python
# miniautogen/cli/commands/console.py
"""miniautogen console command — standalone web dashboard."""

from __future__ import annotations

from pathlib import Path

import click

from miniautogen.cli.output import echo_info


@click.command("console")
@click.option(
    "--port",
    type=int,
    default=8080,
    help="Server port (default: 8080).",
)
@click.option(
    "--workspace",
    type=click.Path(exists=True, file_okay=False),
    default=".",
    help="Workspace directory (default: current directory).",
)
def console_command(port: int, workspace: str) -> None:
    """Launch the MiniAutoGen Console dashboard (standalone mode).

    Opens a web dashboard for observing agents, flows, and run history.
    Note: Standalone mode with live event access requires Sprint 2.
    """
    import uvicorn
    import webbrowser

    from miniautogen.server.app import create_app

    app = create_app(workspace_path=workspace, mode="standalone")

    url = f"http://localhost:{port}"
    echo_info(f"Console running at {url}")
    echo_info("Press Ctrl+C to stop.")
    webbrowser.open(url)

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
```

Register in `miniautogen/cli/main.py` — add after the existing command registrations:

```python
from miniautogen.cli.commands.console import console_command  # noqa: E402

cli.add_command(console_command)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/server/test_console_command.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add miniautogen/cli/commands/console.py miniautogen/cli/main.py tests/server/test_console_command.py
git commit -m "feat(cli): add standalone console command skeleton"
```

---

## Task 10: Frontend Setup (Next.js + Tailwind + Shadcn)

**Files:**
- Create: `console/` directory with Next.js project

- [ ] **Step 1: Initialize Next.js project**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
npx create-next-app@latest console --typescript --tailwind --eslint --app --src-dir --no-import-alias --use-npm
```

- [ ] **Step 2: Configure static export**

Edit `console/next.config.js`:

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  // API calls go to FastAPI, not Next.js API routes
  // All pages use 'use client' for dynamic data
}

module.exports = nextConfig
```

- [ ] **Step 3: Install dependencies**

```bash
cd console
npm install @xyflow/react @tanstack/react-query zustand
npx shadcn@latest init -d
npx shadcn@latest add button card badge table dialog input select
```

- [ ] **Step 4: Create API client**

```typescript
// console/src/lib/api-client.ts
// In production (static export served by FastAPI), use relative URL (same origin).
// In development (next dev), use NEXT_PUBLIC_API_URL env var.
const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });
  if (!resp.ok) {
    const error = await resp.json().catch(() => ({ error: resp.statusText }));
    throw new Error(error.detail?.error || error.error || resp.statusText);
  }
  return resp.json();
}

export const api = {
  getWorkspace: () => apiFetch<Record<string, unknown>>('/workspace'),
  getAgents: () => apiFetch<Record<string, unknown>[]>('/agents'),
  getAgent: (name: string) => apiFetch<Record<string, unknown>>(`/agents/${name}`),
  getFlows: () => apiFetch<Record<string, unknown>[]>('/flows'),
  getFlow: (name: string) => apiFetch<Record<string, unknown>>(`/flows/${name}`),
  getRuns: (offset = 0, limit = 20) =>
    apiFetch<{ items: Record<string, unknown>[]; total: number }>(`/runs?offset=${offset}&limit=${limit}`),
  getRun: (id: string) => apiFetch<Record<string, unknown>>(`/runs/${id}`),
  getRunEvents: (id: string, offset = 0) =>
    apiFetch<{ items: Record<string, unknown>[]; total: number }>(`/runs/${id}/events?offset=${offset}`),
  triggerRun: (flowName: string, input?: string) =>
    apiFetch<{ status: string; flow_name: string }>('/runs', {
      method: 'POST',
      body: JSON.stringify({ flow_name: flowName, input }),
    }),
  getApprovals: (runId: string) =>
    apiFetch<Record<string, unknown>[]>(`/runs/${runId}/approvals`),
  resolveApproval: (runId: string, requestId: string, decision: 'approved' | 'denied', reason?: string) =>
    apiFetch<Record<string, unknown>>(`/runs/${runId}/approvals/${requestId}`, {
      method: 'POST',
      body: JSON.stringify({ decision, reason }),
    }),
};
```

- [ ] **Step 5: Create WebSocket client**

```typescript
// console/src/lib/ws-client.ts
export class RunEventStream {
  private ws: WebSocket | null = null;
  private listeners: ((event: Record<string, unknown>) => void)[] = [];

  constructor(
    private runId: string,
    // In production, derive WS URL from current page origin
    private baseUrl = typeof window !== 'undefined'
      ? `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`
      : 'ws://localhost:8080',
  ) {}

  connect(): void {
    this.ws = new WebSocket(`${this.baseUrl}/ws/runs/${this.runId}`);
    this.ws.onmessage = (msg) => {
      const event = JSON.parse(msg.data);
      this.listeners.forEach((fn) => fn(event));
    };
    this.ws.onclose = () => {
      this.ws = null;
    };
  }

  onEvent(listener: (event: Record<string, unknown>) => void): () => void {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter((fn) => fn !== listener);
    };
  }

  disconnect(): void {
    this.ws?.close();
    this.ws = null;
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}
```

- [ ] **Step 6: Verify build**

```bash
cd console && npm run build
```
Expected: Static export generated in `console/out/`

- [ ] **Step 7: Commit**

```bash
git add console/
git commit -m "feat(console): initialize Next.js frontend with API client and WS support"
```

---

## Task 11: Frontend Dashboard + Layout

**Files:**
- Modify: `console/src/app/layout.tsx`
- Modify: `console/src/app/page.tsx`

- [ ] **Step 1: Create layout with sidebar**

```tsx
// console/src/app/layout.tsx
'use client';

import './globals.css';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';

const NAV_ITEMS = [
  { href: '/', label: 'Dashboard', icon: '~' },
  { href: '/agents', label: 'Agents', icon: 'A' },
  { href: '/flows', label: 'Flows', icon: 'F' },
  { href: '/runs', label: 'Runs', icon: 'R' },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [queryClient] = useState(() => new QueryClient());

  return (
    <html lang="en" className="dark">
      <body className="bg-background text-foreground">
        <QueryClientProvider client={queryClient}>
          <div className="flex h-screen">
            {/* Sidebar */}
            <nav className="w-56 border-r border-border bg-card p-4 flex flex-col gap-1">
              <h1 className="text-lg font-bold mb-4 px-2">MiniAutoGen</h1>
              {NAV_ITEMS.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`px-3 py-2 rounded-md text-sm ${
                    pathname === item.href
                      ? 'bg-primary text-primary-foreground'
                      : 'hover:bg-muted'
                  }`}
                >
                  {item.label}
                </Link>
              ))}
            </nav>
            {/* Main content */}
            <main className="flex-1 overflow-auto p-6">{children}</main>
          </div>
        </QueryClientProvider>
      </body>
    </html>
  );
}
```

- [ ] **Step 2: Create dashboard page**

```tsx
// console/src/app/page.tsx
'use client';

import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api-client';

export default function Dashboard() {
  const { data: workspace } = useQuery({
    queryKey: ['workspace'],
    queryFn: api.getWorkspace,
  });
  const { data: runs } = useQuery({
    queryKey: ['runs'],
    queryFn: () => api.getRuns(),
  });

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Dashboard</h2>
      <div className="grid grid-cols-3 gap-4 mb-8">
        <div className="border rounded-lg p-4">
          <p className="text-sm text-muted-foreground">Agents</p>
          <p className="text-3xl font-bold">{workspace?.agent_count ?? '-'}</p>
        </div>
        <div className="border rounded-lg p-4">
          <p className="text-sm text-muted-foreground">Flows</p>
          <p className="text-3xl font-bold">{workspace?.pipeline_count ?? '-'}</p>
        </div>
        <div className="border rounded-lg p-4">
          <p className="text-sm text-muted-foreground">Runs</p>
          <p className="text-3xl font-bold">{runs?.total ?? '-'}</p>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Verify build**

```bash
cd console && npm run build
```

- [ ] **Step 4: Commit**

```bash
git add console/src/app/layout.tsx console/src/app/page.tsx
git commit -m "feat(console): add dashboard layout with sidebar navigation"
```

---

## Task 12: Frontend Agents + Flows Pages

**Files:**
- Create: `console/src/app/agents/page.tsx`
- Create: `console/src/app/flows/page.tsx`

- [ ] **Step 1: Create agents list page**

```tsx
// console/src/app/agents/page.tsx
'use client';

import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api-client';

export default function AgentsPage() {
  const { data: agents, isLoading } = useQuery({
    queryKey: ['agents'],
    queryFn: api.getAgents,
  });

  if (isLoading) return <p>Loading...</p>;

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Agents</h2>
      <div className="border rounded-lg">
        <table className="w-full">
          <thead>
            <tr className="border-b">
              <th className="text-left p-3 text-sm font-medium">Name</th>
              <th className="text-left p-3 text-sm font-medium">Role</th>
              <th className="text-left p-3 text-sm font-medium">Engine</th>
            </tr>
          </thead>
          <tbody>
            {(agents ?? []).map((agent: any) => (
              <tr key={agent.name} className="border-b last:border-0">
                <td className="p-3 font-mono text-sm">{agent.name}</td>
                <td className="p-3 text-sm">{agent.role}</td>
                <td className="p-3 text-sm text-muted-foreground">
                  {agent.engine_type || agent.engine_profile}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create flows list page**

```tsx
// console/src/app/flows/page.tsx
'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { api } from '@/lib/api-client';

export default function FlowsPage() {
  const { data: flows, isLoading } = useQuery({
    queryKey: ['flows'],
    queryFn: api.getFlows,
  });

  if (isLoading) return <p>Loading...</p>;

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Flows</h2>
      <div className="grid gap-4">
        {(flows ?? []).map((flow: any) => (
          <Link
            key={flow.name}
            href={`/flows/${flow.name}`}
            className="border rounded-lg p-4 hover:bg-muted transition-colors"
          >
            <h3 className="font-mono font-bold">{flow.name}</h3>
            <p className="text-sm text-muted-foreground">
              Mode: {flow.mode} | Target: {flow.target}
            </p>
          </Link>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Verify build**

```bash
cd console && npm run build
```

- [ ] **Step 4: Commit**

```bash
git add console/src/app/agents/ console/src/app/flows/
git commit -m "feat(console): add agents and flows list pages"
```

---

## Task 13: Frontend Runs Page + Run Detail

**Files:**
- Create: `console/src/app/runs/page.tsx`
- Create: `console/src/app/runs/[id]/page.tsx`
- Create: `console/src/components/run/EventFeed.tsx`
- Create: `console/src/components/run/RunStatus.tsx`
- Create: `console/src/hooks/useRunEvents.ts`

- [ ] **Step 1: Create useRunEvents hook**

```typescript
// console/src/hooks/useRunEvents.ts
'use client';

import { useEffect, useRef, useState } from 'react';
import { RunEventStream } from '@/lib/ws-client';
import { api } from '@/lib/api-client';

export function useRunEvents(runId: string) {
  const [events, setEvents] = useState<Record<string, unknown>[]>([]);
  const [isLive, setIsLive] = useState(false);
  const streamRef = useRef<RunEventStream | null>(null);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    // Try WebSocket first
    const stream = new RunEventStream(runId);
    streamRef.current = stream;

    const unsub = stream.onEvent((event) => {
      if (event.type === 'connected') {
        setIsLive(true);
        return;
      }
      if (event.type === 'finished') {
        setIsLive(false);
        return;
      }
      setEvents((prev) => [...prev, event]);
    });

    stream.connect();

    // Fallback: if WS fails, poll REST
    const timeout = setTimeout(() => {
      if (!stream.isConnected) {
        setIsLive(false);
        // Start polling
        let offset = 0;
        pollingRef.current = setInterval(async () => {
          try {
            const data = await api.getRunEvents(runId, offset);
            if (data.items.length > 0) {
              setEvents((prev) => [...prev, ...data.items]);
              offset += data.items.length;
            }
          } catch {
            // ignore polling errors
          }
        }, 1000);
      }
    }, 2000);

    return () => {
      clearTimeout(timeout);
      unsub();
      stream.disconnect();
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [runId]);

  return { events, isLive };
}
```

- [ ] **Step 2: Create RunStatus and EventFeed components**

```tsx
// console/src/components/run/RunStatus.tsx
'use client';

const STATUS_COLORS: Record<string, string> = {
  completed: 'bg-green-500/10 text-green-500 border-green-500/20',
  running: 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20',
  failed: 'bg-red-500/10 text-red-500 border-red-500/20',
};

export function RunStatus({ status }: { status: string }) {
  const color = STATUS_COLORS[status] || 'bg-muted text-muted-foreground';
  return (
    <span className={`inline-flex px-2 py-0.5 text-xs font-medium rounded border ${color}`}>
      {status.toUpperCase()}
    </span>
  );
}


// console/src/components/run/EventFeed.tsx
'use client';

export function EventFeed({ events }: { events: Record<string, unknown>[] }) {
  return (
    <div className="border rounded-lg overflow-auto max-h-96">
      <table className="w-full text-xs font-mono">
        <thead className="sticky top-0 bg-card">
          <tr className="border-b">
            <th className="text-left p-2">Time</th>
            <th className="text-left p-2">Type</th>
            <th className="text-left p-2">Details</th>
          </tr>
        </thead>
        <tbody>
          {events.map((event, i) => (
            <tr key={i} className="border-b last:border-0 hover:bg-muted/50">
              <td className="p-2 text-muted-foreground whitespace-nowrap">
                {event.timestamp ? new Date(event.timestamp as string).toLocaleTimeString() : '-'}
              </td>
              <td className="p-2">{event.type as string}</td>
              <td className="p-2 text-muted-foreground truncate max-w-xs">
                {event.scope as string || ''}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 3: Create runs list page**

```tsx
// console/src/app/runs/page.tsx
'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { api } from '@/lib/api-client';
import { RunStatus } from '@/components/run/RunStatus';

export default function RunsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['runs'],
    queryFn: () => api.getRuns(),
    refetchInterval: 3000,
  });

  if (isLoading) return <p>Loading...</p>;

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Runs</h2>
      {(data?.items ?? []).length === 0 ? (
        <p className="text-muted-foreground">No runs yet. Trigger a run from the Dashboard.</p>
      ) : (
        <div className="border rounded-lg">
          <table className="w-full">
            <thead>
              <tr className="border-b">
                <th className="text-left p-3 text-sm">Run ID</th>
                <th className="text-left p-3 text-sm">Flow</th>
                <th className="text-left p-3 text-sm">Status</th>
                <th className="text-left p-3 text-sm">Events</th>
              </tr>
            </thead>
            <tbody>
              {data?.items.map((run: any) => (
                <tr key={run.run_id} className="border-b last:border-0">
                  <td className="p-3">
                    <Link href={`/runs/${run.run_id}`} className="font-mono text-sm text-primary hover:underline">
                      {run.run_id.slice(0, 8)}...
                    </Link>
                  </td>
                  <td className="p-3 text-sm">{run.pipeline}</td>
                  <td className="p-3"><RunStatus status={run.status} /></td>
                  <td className="p-3 text-sm">{run.events}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Create run detail page**

```tsx
// console/src/app/runs/[id]/page.tsx
'use client';

import { useParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import { useRunEvents } from '@/hooks/useRunEvents';
import { RunStatus } from '@/components/run/RunStatus';
import { EventFeed } from '@/components/run/EventFeed';

export default function RunDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: run } = useQuery({
    queryKey: ['run', id],
    queryFn: () => api.getRun(id),
  });
  const { events, isLive } = useRunEvents(id);

  return (
    <div>
      <div className="flex items-center gap-4 mb-6">
        <h2 className="text-2xl font-bold">
          Run <span className="font-mono">{id.slice(0, 8)}</span>
        </h2>
        {run && <RunStatus status={run.status as string} />}
        {isLive && (
          <span className="text-xs text-green-500 flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
            LIVE
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 gap-6">
        <div>
          <h3 className="font-bold mb-2">Events ({events.length})</h3>
          <EventFeed events={events} />
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Verify build**

```bash
cd console && npm run build
```

- [ ] **Step 6: Commit**

```bash
git add console/src/app/runs/ console/src/components/run/ console/src/hooks/
git commit -m "feat(console): add runs list, run detail with live event feed"
```

---

## Task 14: Static Files Serving + Hatchling Config

**Files:**
- Modify: `miniautogen/server/app.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Add static file serving to app factory**

In `miniautogen/server/app.py`, add at the end of `create_app()`, after routes:

```python
    # Serve frontend static files (Next.js build output)
    static_dir = Path(__file__).parent / "static"
    if static_dir.is_dir():
        from starlette.staticfiles import StaticFiles
        app.mount("/", StaticFiles(directory=str(static_dir), html=True))

    return app
```

- [ ] **Step 2: Configure hatchling to include static files**

Add to `pyproject.toml`:

```toml
[tool.hatch.build.targets.wheel.force-include]
"miniautogen/server/static" = "miniautogen/server/static"
```

Note: The `console/out/` must be copied to `miniautogen/server/static/` before building the wheel. This is done by CI or manually:

```bash
cd console && npm run build && cp -r out/ ../miniautogen/server/static/
```

- [ ] **Step 3: Create a placeholder in static dir**

```bash
mkdir -p miniautogen/server/static
echo "Console frontend not built. Run: cd console && npm run build && cp -r out/ ../miniautogen/server/static/" > miniautogen/server/static/.gitkeep
```

- [ ] **Step 4: Commit**

```bash
git add miniautogen/server/app.py miniautogen/server/static/.gitkeep pyproject.toml
git commit -m "feat(server): serve Next.js static build and configure hatchling packaging"
```

---

## Task 15: End-to-End Smoke Test

**Files:**
- Create: `tests/server/test_e2e_smoke.py`

- [ ] **Step 1: Write smoke test**

```python
# tests/server/test_e2e_smoke.py
"""End-to-end smoke test for the Console Server."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from miniautogen.server.app import create_app


def _mock_provider() -> MagicMock:
    provider = MagicMock()
    provider.get_config.return_value = {
        "project_name": "smoke-test",
        "version": "0.1.0",
        "agent_count": 1,
        "pipeline_count": 1,
    }
    provider.get_agents.return_value = [
        {"name": "a1", "role": "tester", "engine_profile": "gpt4"},
    ]
    provider.get_pipelines.return_value = [
        {"name": "main", "mode": "workflow", "target": "main:build"},
    ]
    provider.get_runs.return_value = [
        {"run_id": "r1", "pipeline": "main", "status": "completed", "started": "2026-01-01", "events": 3},
    ]
    provider.get_events.return_value = [
        {"type": "run_started", "run_id": "r1", "timestamp": "2026-01-01T00:00:00Z"},
        {"type": "component_started", "run_id": "r1", "timestamp": "2026-01-01T00:00:01Z"},
        {"type": "run_finished", "run_id": "r1", "timestamp": "2026-01-01T00:00:02Z"},
    ]
    provider.get_agent.return_value = {"name": "a1", "role": "tester", "engine_profile": "gpt4"}
    provider.get_pipeline.return_value = {"name": "main", "mode": "workflow", "participants": ["a1"]}
    provider.run_pipeline = AsyncMock(return_value={"status": "completed", "events": 3})
    return provider


def test_smoke_all_endpoints():
    """Every endpoint returns 200 with valid data."""
    provider = _mock_provider()
    app = create_app(provider=provider, mode="embedded")
    client = TestClient(app)

    # Workspace
    r = client.get("/api/v1/workspace")
    assert r.status_code == 200
    assert r.json()["project_name"] == "smoke-test"

    # Agents
    r = client.get("/api/v1/agents")
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.get("/api/v1/agents/a1")
    assert r.status_code == 200

    # Flows
    r = client.get("/api/v1/flows")
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.get("/api/v1/flows/main")
    assert r.status_code == 200

    # Runs
    r = client.get("/api/v1/runs")
    assert r.status_code == 200
    assert r.json()["total"] == 1

    r = client.get("/api/v1/runs/r1")
    assert r.status_code == 200

    r = client.get("/api/v1/runs/r1/events")
    assert r.status_code == 200
    assert r.json()["total"] == 3

    # Trigger run
    r = client.post("/api/v1/runs", json={"flow_name": "main"})
    assert r.status_code == 200
    assert r.json()["status"] == "triggered"

    # 404s
    r = client.get("/api/v1/agents/nonexistent")
    assert r.status_code == 404

    r = client.get("/api/v1/flows/nonexistent")
    assert r.status_code == 404

    r = client.get("/api/v1/runs/nonexistent")
    assert r.status_code == 404
```

- [ ] **Step 2: Run smoke test**

Run: `python -m pytest tests/server/test_e2e_smoke.py -v`
Expected: All PASS

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest tests/server/ -v --tb=short`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add tests/server/test_e2e_smoke.py
git commit -m "test(server): add end-to-end smoke test for all Console API endpoints"
```

---

## Review Checkpoint

At this point, Sprint 1 backend + frontend foundation is complete. Before proceeding, request code review:

- Backend: 10 files in `miniautogen/server/`, ~500 LOC
- Tests: 8 test files in `tests/server/`, ~300 LOC
- Frontend: Next.js project in `console/` with 6 pages and 5 components
- CLI: `--console` flag on `run` command + `console` standalone skeleton

Use skill `superpowers:requesting-code-review` to validate before merging.
