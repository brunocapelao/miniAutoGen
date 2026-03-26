# DX Sprint 2: Dashboard Completo -- Implementation Plan

> **For Agents:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Complete the web console with settings management, real-time log streaming, a global status CLI command, Docker deployment, and first-class daemon lifecycle management.

**Architecture:** Five additive features (G6-G10) that extend the existing CLI (Click commands), FastAPI server (new routes + global WebSocket), Next.js console (new pages), and DevOps tooling (Docker). G6 adds engine CRUD endpoints + settings page. G7 adds a global WebSocket for event streaming + log viewer page. G8 adds a `status` command aggregating workspace info. G9 adds Dockerfile/docker-compose for deployment. G10 promotes daemon to a first-class CLI group. Each backend feature follows the established pattern: protocol method -> provider delegation -> DashDataProvider -> CLI service layer. Frontend follows: api-client function -> React Query hook -> page component.

**Tech Stack:** Python 3.10+ (AnyIO, Click, FastAPI, Pydantic, PyYAML), Next.js 16 (React 19, TanStack Query, Tailwind CSS), pytest + pytest-anyio, Docker

**Global Prerequisites:**
- Environment: macOS/Linux, Python 3.10+, Node.js 18+
- Tools: `python --version`, `pip`, `pytest`, `npm`
- Access: No API keys required for tests (mocked providers)
- State: Branch from `main` (post-Sprint 1 commit `d1c2a9f`), clean working tree

**Verification before starting:**
```bash
python --version        # Expected: Python 3.10+
pytest --version        # Expected: 7.0+
cd /Users/brunocapelao/Projects/miniAutoGen && git status  # Expected: clean working tree on main
```

---

## G6: Settings Editor in Web Console

### Task 1: Add engine CRUD methods to ConsoleDataProvider protocol

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/server/provider_protocol.py`

**Prerequisites:**
- None (additive protocol extension)

**Step 1: Add engine CRUD method signatures to the protocol**

Add the following after the `delete_pipeline` method (after line 88) in `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/server/provider_protocol.py`:

```python
    # -- CRUD: Engines ---------------------------------------------------------

    def get_engines(self) -> list[dict[str, Any]]: ...

    def get_engine(self, name: str) -> dict[str, Any]: ...

    def create_engine(
        self,
        name: str,
        *,
        provider: str,
        model: str,
        kind: str = "api",
        temperature: float = 0.2,
        api_key_env: str | None = None,
        endpoint: str | None = None,
    ) -> dict[str, Any]: ...

    def update_engine(self, name: str, **updates: Any) -> dict[str, Any]: ...

    def delete_engine(self, name: str) -> dict[str, Any]: ...

    # -- Config: Read-only view ------------------------------------------------

    def get_config_detail(self) -> dict[str, Any]:
        """Get detailed config including engines, defaults, database.

        Unlike get_config() which returns a summary, this returns
        the full structure needed for the settings editor.
        """
        ...
```

**Step 2: Verify the protocol file is valid Python**

Run: `python -c "from miniautogen.server.provider_protocol import ConsoleDataProvider; print('OK')"`

**Expected output:**
```
OK
```

**If you see ImportError:** Check indentation matches the existing protocol methods (4 spaces).

**Step 3: Commit**

```bash
git add miniautogen/server/provider_protocol.py
git commit -m "feat(server): add engine CRUD and config_detail to ConsoleDataProvider protocol"
```

---

### Task 2: Add engine CRUD delegation to StandaloneProvider

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/server/standalone_provider.py`

**Prerequisites:**
- Task 1 complete (protocol updated)

**Step 1: Add engine CRUD and config_detail delegations**

Add the following after the `delete_pipeline` method (after line 69) in `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/server/standalone_provider.py`:

```python
    # -- CRUD: Engines ----------------------------------------------------------

    def get_engines(self) -> list[dict[str, Any]]:
        return self._base.get_engines()

    def get_engine(self, name: str) -> dict[str, Any]:
        return self._base.get_engine(name)

    def create_engine(self, name: str, *, provider: str, model: str, kind: str = "api", temperature: float = 0.2, api_key_env: str | None = None, endpoint: str | None = None) -> dict[str, Any]:
        return self._base.create_engine(name, provider=provider, model=model, kind=kind, temperature=temperature, api_key_env=api_key_env, endpoint=endpoint)

    def update_engine(self, name: str, **updates: Any) -> dict[str, Any]:
        return self._base.update_engine(name, **updates)

    def delete_engine(self, name: str) -> dict[str, Any]:
        return self._base.delete_engine(name)

    # -- Config: Read-only view ------------------------------------------------

    def get_config_detail(self) -> dict[str, Any]:
        return self._base.get_config_detail()
```

**Step 2: Verify import works**

Run: `python -c "from miniautogen.server.standalone_provider import StandaloneProvider; print('OK')"`

**Expected output:**
```
OK
```

---

### Task 3: Add get_config_detail to DashDataProvider

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/data_provider.py`

**Prerequisites:**
- Task 1 complete (protocol defines `get_config_detail`)

**Step 1: Add the get_config_detail method**

Add the following after the `get_config` method (after line 116) in `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/tui/data_provider.py`:

```python
    def get_config_detail(self) -> dict[str, Any]:
        """Get detailed config for settings editor.

        Returns engines, defaults, database, project metadata
        in a structure suitable for the settings page.
        """
        if not self._config_path.is_file():
            return {}
        try:
            config = load_config(self._config_path)
            engines = self.get_engines()
            return {
                "project": {
                    "name": config.project.name,
                    "version": config.project.version,
                },
                "defaults": {
                    "engine": config.defaults.engine,
                    "memory_profile": config.defaults.memory_profile,
                },
                "database": {
                    "url": config.database.url if config.database else "(none)",
                },
                "engines": engines,
                "env_vars": self._get_safe_env_vars(),
            }
        except Exception:
            logger.exception("Failed to load detailed config from %s", self._config_path)
            return {}

    def _get_safe_env_vars(self) -> list[dict[str, str]]:
        """Return env var names relevant to MiniAutoGen (values masked)."""
        import os
        relevant_prefixes = ("OPENAI_", "ANTHROPIC_", "GOOGLE_", "MINIAUTOGEN_", "GEMINI_")
        result = []
        for key in sorted(os.environ):
            if any(key.startswith(p) for p in relevant_prefixes):
                value = os.environ[key]
                masked = value[:4] + "..." if len(value) > 4 else "***"
                result.append({"name": key, "value": masked})
        return result
```

**Step 2: Verify**

Run: `python -c "from miniautogen.tui.data_provider import DashDataProvider; print('OK')"`

**Expected output:**
```
OK
```

---

### Task 4: Create engines route file with CRUD endpoints

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/server/routes/engines.py`

**Prerequisites:**
- Task 1 complete (protocol has engine methods)

**Step 1: Create the engines route module**

Create file `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/server/routes/engines.py`:

```python
"""Engine endpoints for settings management."""

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
    kind: str = Field(default="api")
    temperature: float = Field(default=0.2, ge=0, le=2)
    api_key_env: str | None = None
    endpoint: str | None = None


class UpdateEngineRequest(BaseModel):
    provider: str | None = None
    model: str | None = None
    kind: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
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
        except ValueError as exc:
            raise HTTPException(
                status_code=409,
                detail=ErrorResponse(
                    error=str(exc),
                    code="engine_in_use",
                ).model_dump(),
            )

    @router.get("/config")
    async def get_config_detail() -> dict[str, Any]:
        return provider.get_config_detail()

    return router
```

**Step 2: Verify syntax**

Run: `python -c "from miniautogen.server.routes.engines import engines_router; print('OK')"`

**Expected output:**
```
OK
```

---

### Task 5: Register engines router in FastAPI app

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/server/app.py`

**Prerequisites:**
- Task 4 complete (engines route exists)

**Step 1: Add the import**

In `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/server/app.py`, add after the `from miniautogen.server.routes.flows import flows_router` line (line 21):

```python
from miniautogen.server.routes.engines import engines_router
```

**Step 2: Register the router**

In the same file, after `app.include_router(flows_router(provider), dependencies=auth_deps)` (line 76), add:

```python
    app.include_router(engines_router(provider), dependencies=auth_deps)
```

**Step 3: Verify app creation**

Run: `python -c "from miniautogen.server.app import create_app; print('OK')"`

**Expected output:**
```
OK
```

---

### Task 6: Write tests for engine CRUD endpoints

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/server/test_engines_crud.py`

**Prerequisites:**
- Task 5 complete (router registered)
- Tests use the existing `conftest.py` fixtures (`client`, `mock_provider`)

**Step 1: Create the test file**

Create file `/Users/brunocapelao/Projects/miniAutoGen/tests/server/test_engines_crud.py`:

```python
"""Tests for engine CRUD endpoints (GET, POST, PUT, DELETE)."""

from __future__ import annotations


def test_list_engines(client, mock_provider):
    mock_provider.get_engines.return_value = [
        {"name": "gpt4", "provider": "openai", "model": "gpt-4o", "kind": "api"},
        {"name": "gemini", "provider": "google", "model": "gemini-pro", "kind": "api"},
    ]
    resp = client.get("/api/v1/engines")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["name"] == "gpt4"
    mock_provider.get_engines.assert_called_once()


def test_get_engine(client, mock_provider):
    mock_provider.get_engine.return_value = {
        "name": "gpt4", "provider": "openai", "model": "gpt-4o",
        "kind": "api", "temperature": 0.2,
    }
    resp = client.get("/api/v1/engines/gpt4")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "gpt4"
    assert data["provider"] == "openai"
    mock_provider.get_engine.assert_called_once_with("gpt4")


def test_get_engine_not_found_404(client, mock_provider):
    mock_provider.get_engine.side_effect = KeyError("nonexistent")
    resp = client.get("/api/v1/engines/nonexistent")
    assert resp.status_code == 404
    data = resp.json()
    assert data["code"] == "engine_not_found"


def test_create_engine(client, mock_provider):
    mock_provider.create_engine.return_value = {
        "name": "claude", "provider": "anthropic", "model": "claude-3",
        "kind": "api", "temperature": 0.3,
    }
    resp = client.post("/api/v1/engines", json={
        "name": "claude",
        "provider": "anthropic",
        "model": "claude-3",
        "temperature": 0.3,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "claude"
    mock_provider.create_engine.assert_called_once_with(
        "claude",
        provider="anthropic",
        model="claude-3",
        kind="api",
        temperature=0.3,
        api_key_env=None,
        endpoint=None,
    )


def test_create_engine_duplicate_409(client, mock_provider):
    mock_provider.create_engine.side_effect = ValueError("Engine 'gpt4' already exists")
    resp = client.post("/api/v1/engines", json={
        "name": "gpt4",
        "provider": "openai",
        "model": "gpt-4o",
    })
    assert resp.status_code == 409
    data = resp.json()
    assert data["code"] == "engine_exists"


def test_create_engine_validation_error(client):
    resp = client.post("/api/v1/engines", json={
        "name": "",
        "provider": "openai",
        "model": "gpt-4o",
    })
    assert resp.status_code == 422


def test_update_engine(client, mock_provider):
    mock_provider.update_engine.return_value = {
        "before": {"temperature": 0.2},
        "after": {"temperature": 0.8},
    }
    resp = client.put("/api/v1/engines/gpt4", json={
        "temperature": 0.8,
    })
    assert resp.status_code == 200
    mock_provider.update_engine.assert_called_once_with("gpt4", temperature=0.8)


def test_update_engine_not_found_404(client, mock_provider):
    mock_provider.update_engine.side_effect = KeyError("nonexistent")
    resp = client.put("/api/v1/engines/nonexistent", json={
        "model": "gpt-4o-mini",
    })
    assert resp.status_code == 404
    data = resp.json()
    assert data["code"] == "engine_not_found"


def test_update_engine_empty_body_400(client):
    resp = client.put("/api/v1/engines/gpt4", json={})
    assert resp.status_code == 400
    data = resp.json()
    assert data["code"] == "empty_update"


def test_delete_engine(client, mock_provider):
    mock_provider.delete_engine.return_value = {"deleted": "gpt4"}
    resp = client.delete("/api/v1/engines/gpt4")
    assert resp.status_code == 200
    data = resp.json()
    assert data["deleted"] == "gpt4"
    mock_provider.delete_engine.assert_called_once_with("gpt4")


def test_delete_engine_not_found_404(client, mock_provider):
    mock_provider.delete_engine.side_effect = KeyError("nonexistent")
    resp = client.delete("/api/v1/engines/nonexistent")
    assert resp.status_code == 404
    data = resp.json()
    assert data["code"] == "engine_not_found"


def test_delete_engine_in_use_409(client, mock_provider):
    mock_provider.delete_engine.side_effect = ValueError("Engine referenced by agents")
    resp = client.delete("/api/v1/engines/gpt4")
    assert resp.status_code == 409
    data = resp.json()
    assert data["code"] == "engine_in_use"


def test_get_config_detail(client, mock_provider):
    mock_provider.get_config_detail.return_value = {
        "project": {"name": "test", "version": "0.1.0"},
        "defaults": {"engine": "default_api", "memory_profile": "default"},
        "database": {"url": "sqlite:///test.db"},
        "engines": [],
        "env_vars": [{"name": "OPENAI_API_KEY", "value": "sk-t..."}],
    }
    resp = client.get("/api/v1/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["project"]["name"] == "test"
    assert data["defaults"]["engine"] == "default_api"
    mock_provider.get_config_detail.assert_called_once()
```

**Step 2: Run tests**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/server/test_engines_crud.py -v`

**Expected output:**
```
tests/server/test_engines_crud.py::test_list_engines PASSED
tests/server/test_engines_crud.py::test_get_engine PASSED
tests/server/test_engines_crud.py::test_get_engine_not_found_404 PASSED
tests/server/test_engines_crud.py::test_create_engine PASSED
tests/server/test_engines_crud.py::test_create_engine_duplicate_409 PASSED
tests/server/test_engines_crud.py::test_create_engine_validation_error PASSED
tests/server/test_engines_crud.py::test_update_engine PASSED
tests/server/test_engines_crud.py::test_update_engine_not_found_404 PASSED
tests/server/test_engines_crud.py::test_update_engine_empty_body_400 PASSED
tests/server/test_engines_crud.py::test_delete_engine PASSED
tests/server/test_engines_crud.py::test_delete_engine_not_found_404 PASSED
tests/server/test_engines_crud.py::test_delete_engine_in_use_409 PASSED
tests/server/test_engines_crud.py::test_get_config_detail PASSED
```

**If mock_provider lacks `get_engines` etc.:** The conftest `mock_provider` is a MagicMock, so new methods auto-create. No conftest changes needed.

**Step 3: Commit**

```bash
git add miniautogen/server/routes/engines.py miniautogen/server/app.py miniautogen/server/provider_protocol.py miniautogen/server/standalone_provider.py miniautogen/tui/data_provider.py tests/server/test_engines_crud.py
git commit -m "feat(server): add engine CRUD endpoints and config detail API"
```

---

### Task 7: Add Engine type and API client methods for frontend

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/console/src/types/api.ts`
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/console/src/lib/api-client.ts`

**Prerequisites:**
- Task 5 complete (backend endpoints available)

**IMPORTANT:** Read `console/AGENTS.md` before modifying any Next.js code. It warns about breaking changes in Next.js 16 -- check `node_modules/next/dist/docs/` for current API conventions.

**Step 1: Add Engine type to api.ts**

In `/Users/brunocapelao/Projects/miniAutoGen/console/src/types/api.ts`, add after the `Agent` type (after line 18):

```typescript
export type Engine = {
  name: string;
  provider: string;
  model: string;
  kind: string;
  temperature?: number;
  api_key_env?: string;
  endpoint?: string;
  capabilities?: string[];
  source?: string;
};

export type ConfigDetail = {
  project: { name: string; version: string };
  defaults: { engine: string; memory_profile: string };
  database: { url: string };
  engines: Engine[];
  env_vars: Array<{ name: string; value: string }>;
};
```

**Step 2: Add engine API methods to api-client.ts**

In `/Users/brunocapelao/Projects/miniAutoGen/console/src/lib/api-client.ts`, add the Engine import to the first line:

```typescript
import type { Workspace, Agent, Engine, ConfigDetail, Flow, RunSummary, RunEvent, Approval, Page } from '@/types/api';
```

Then add after the `deleteFlow` method (before the closing `};` on line 73):

```typescript

  // Engine CRUD
  getEngines: () => apiFetch<Engine[]>('/engines'),
  getEngine: (name: string) => apiFetch<Engine>(`/engines/${encodeURIComponent(name)}`),
  createEngine: (data: { name: string; provider: string; model: string; kind?: string; temperature?: number; api_key_env?: string; endpoint?: string }) =>
    post<Engine>('/engines', data),
  updateEngine: (name: string, data: Record<string, unknown>) =>
    put<Engine>(`/engines/${encodeURIComponent(name)}`, data),
  deleteEngine: (name: string) =>
    del<{ deleted: string }>(`/engines/${encodeURIComponent(name)}`),

  // Config
  getConfigDetail: () => apiFetch<ConfigDetail>('/config'),
```

**Step 3: Verify TypeScript compilation**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen/console && npx tsc --noEmit --pretty 2>&1 | head -20`

**Expected output:** No errors related to Engine or ConfigDetail types. Some pre-existing warnings may appear.

---

### Task 8: Add React Query hooks for engines and config

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/console/src/hooks/useApi.ts`

**Prerequisites:**
- Task 7 complete (API client has engine methods)

**Step 1: Add engine hooks**

In `/Users/brunocapelao/Projects/miniAutoGen/console/src/hooks/useApi.ts`, add after the `useDeleteFlow` hook (at end of file, before the closing):

```typescript

export function useEngines() {
  return useQuery({
    queryKey: ['engines'],
    queryFn: api.getEngines,
  });
}

export function useEngine(name: string) {
  return useQuery({
    queryKey: ['engine', name],
    queryFn: () => api.getEngine(name),
    enabled: !!name,
  });
}

export function useCreateEngine() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; provider: string; model: string; kind?: string; temperature?: number; api_key_env?: string; endpoint?: string }) =>
      api.createEngine(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['engines'] });
      queryClient.invalidateQueries({ queryKey: ['config'] });
    },
  });
}

export function useUpdateEngine() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ name, data }: { name: string; data: Record<string, unknown> }) =>
      api.updateEngine(name, data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['engines'] });
      queryClient.invalidateQueries({ queryKey: ['engine', variables.name] });
      queryClient.invalidateQueries({ queryKey: ['config'] });
    },
  });
}

export function useDeleteEngine() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => api.deleteEngine(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['engines'] });
      queryClient.invalidateQueries({ queryKey: ['config'] });
    },
  });
}

export function useConfigDetail() {
  return useQuery({
    queryKey: ['config'],
    queryFn: api.getConfigDetail,
  });
}
```

---

### Task 9: Create EngineForm component

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/console/src/components/EngineForm.tsx`

**Prerequisites:**
- Task 8 complete (hooks available)

**Step 1: Create the EngineForm component**

Create file `/Users/brunocapelao/Projects/miniAutoGen/console/src/components/EngineForm.tsx`:

```tsx
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useCreateEngine, useUpdateEngine } from '@/hooks/useApi';
import type { Engine } from '@/types/api';

type EngineFormProps = {
  mode: 'create' | 'edit';
  initialData?: Engine;
};

export function EngineForm({ mode, initialData }: EngineFormProps) {
  const router = useRouter();
  const createEngine = useCreateEngine();
  const updateEngine = useUpdateEngine();

  const [name, setName] = useState(initialData?.name ?? '');
  const [provider, setProvider] = useState(initialData?.provider ?? '');
  const [model, setModel] = useState(initialData?.model ?? '');
  const [kind, setKind] = useState(initialData?.kind ?? 'api');
  const [temperature, setTemperature] = useState<string>(
    initialData?.temperature != null ? String(initialData.temperature) : '0.2'
  );
  const [apiKeyEnv, setApiKeyEnv] = useState(initialData?.api_key_env ?? '');
  const [endpoint, setEndpoint] = useState(initialData?.endpoint ?? '');
  const [error, setError] = useState<string | null>(null);

  const isSubmitting = createEngine.isPending || updateEngine.isPending;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    try {
      if (mode === 'create') {
        await createEngine.mutateAsync({
          name,
          provider,
          model,
          kind,
          temperature: temperature ? parseFloat(temperature) : undefined,
          api_key_env: apiKeyEnv || undefined,
          endpoint: endpoint || undefined,
        });
      } else {
        await updateEngine.mutateAsync({
          name,
          data: {
            provider,
            model,
            kind,
            temperature: temperature ? parseFloat(temperature) : undefined,
            api_key_env: apiKeyEnv || undefined,
            endpoint: endpoint || undefined,
          },
        });
      }
      router.push('/settings');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    }
  }

  const inputClass = 'w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-md text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500';

  return (
    <form onSubmit={handleSubmit} className="max-w-lg space-y-5">
      {error && (
        <div className="border border-red-500/30 bg-red-500/5 rounded-lg p-3">
          <p className="text-red-400 text-sm">{error}</p>
        </div>
      )}

      <div>
        <label htmlFor="name" className="block text-sm font-medium text-gray-400 mb-1">Name</label>
        <input
          id="name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          readOnly={mode === 'edit'}
          required
          className={`${inputClass} ${mode === 'edit' ? 'opacity-60 cursor-not-allowed' : ''}`}
          placeholder="e.g. gpt-4o"
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label htmlFor="provider" className="block text-sm font-medium text-gray-400 mb-1">Provider</label>
          <input
            id="provider"
            type="text"
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            required
            className={inputClass}
            placeholder="e.g. openai"
          />
        </div>
        <div>
          <label htmlFor="model" className="block text-sm font-medium text-gray-400 mb-1">Model</label>
          <input
            id="model"
            type="text"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            required
            className={inputClass}
            placeholder="e.g. gpt-4o-mini"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label htmlFor="kind" className="block text-sm font-medium text-gray-400 mb-1">Kind</label>
          <select
            id="kind"
            value={kind}
            onChange={(e) => setKind(e.target.value)}
            className={inputClass}
          >
            <option value="api">API</option>
            <option value="cli">CLI</option>
            <option value="local">Local</option>
          </select>
        </div>
        <div>
          <label htmlFor="temperature" className="block text-sm font-medium text-gray-400 mb-1">Temperature</label>
          <input
            id="temperature"
            type="number"
            step="0.1"
            min="0"
            max="2"
            value={temperature}
            onChange={(e) => setTemperature(e.target.value)}
            className={inputClass}
          />
        </div>
      </div>

      <div>
        <label htmlFor="api_key_env" className="block text-sm font-medium text-gray-400 mb-1">
          API Key Env Var <span className="text-gray-600">(optional)</span>
        </label>
        <input
          id="api_key_env"
          type="text"
          value={apiKeyEnv}
          onChange={(e) => setApiKeyEnv(e.target.value)}
          className={inputClass}
          placeholder="e.g. OPENAI_API_KEY"
        />
        <p className="text-xs text-gray-600 mt-1">Environment variable name (not the key itself)</p>
      </div>

      <div>
        <label htmlFor="endpoint" className="block text-sm font-medium text-gray-400 mb-1">
          Endpoint <span className="text-gray-600">(optional)</span>
        </label>
        <input
          id="endpoint"
          type="text"
          value={endpoint}
          onChange={(e) => setEndpoint(e.target.value)}
          className={inputClass}
          placeholder="e.g. https://api.openai.com/v1"
        />
      </div>

      <div className="flex gap-3 pt-2">
        <button
          type="submit"
          disabled={isSubmitting}
          className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-500 text-white rounded-md transition-colors disabled:opacity-50"
        >
          {isSubmitting ? 'Saving...' : mode === 'create' ? 'Create Engine' : 'Save Changes'}
        </button>
        <button
          type="button"
          onClick={() => router.push('/settings')}
          disabled={isSubmitting}
          className="px-4 py-2 text-sm bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-md transition-colors disabled:opacity-50"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
```

---

### Task 10: Create Settings page

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/console/src/app/settings/page.tsx`

**Prerequisites:**
- Task 8 complete (hooks available)
- Task 9 complete (EngineForm available)

**Step 1: Create the settings page**

Create file `/Users/brunocapelao/Projects/miniAutoGen/console/src/app/settings/page.tsx`:

```tsx
'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useConfigDetail, useEngines, useDeleteEngine } from '@/hooks/useApi';
import type { Engine } from '@/types/api';
import { SkeletonTable } from '@/components/Skeleton';
import { QueryError } from '@/components/QueryError';
import { DeleteConfirmModal } from '@/components/DeleteConfirmModal';

export default function SettingsPage() {
  const { data: config, isLoading: configLoading, error: configError, refetch: refetchConfig } = useConfigDetail();
  const { data: engines, isLoading: enginesLoading, error: enginesError, refetch: refetchEngines } = useEngines();
  const deleteEngine = useDeleteEngine();
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  async function handleDelete() {
    if (!deleteTarget) return;
    await deleteEngine.mutateAsync(deleteTarget);
    setDeleteTarget(null);
  }

  return (
    <div className="space-y-8">
      <h2 className="text-2xl font-bold">Settings</h2>

      {/* Project Info */}
      {configLoading ? (
        <div className="border border-gray-800 rounded-lg p-6 bg-gray-900/50">
          <div className="animate-pulse space-y-3">
            <div className="h-4 bg-gray-800 rounded w-1/4" />
            <div className="h-4 bg-gray-800 rounded w-1/2" />
          </div>
        </div>
      ) : configError ? (
        <QueryError error={configError as Error} message="Failed to load config" onRetry={refetchConfig} />
      ) : config ? (
        <div className="border border-gray-800 rounded-lg p-6 bg-gray-900/50">
          <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Project</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs text-gray-500">Name</p>
              <p className="text-sm font-mono mt-0.5">{config.project.name}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Version</p>
              <p className="text-sm font-mono mt-0.5">{config.project.version}</p>
            </div>
          </div>
        </div>
      ) : null}

      {/* Defaults */}
      {config && (
        <div className="border border-gray-800 rounded-lg p-6 bg-gray-900/50">
          <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Defaults</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs text-gray-500">Default Engine</p>
              <p className="text-sm font-mono mt-0.5">{config.defaults.engine}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Memory Profile</p>
              <p className="text-sm font-mono mt-0.5">{config.defaults.memory_profile}</p>
            </div>
          </div>
        </div>
      )}

      {/* Database */}
      {config && (
        <div className="border border-gray-800 rounded-lg p-6 bg-gray-900/50">
          <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Database</h3>
          <div>
            <p className="text-xs text-gray-500">URL</p>
            <p className="text-sm font-mono mt-0.5">{config.database.url}</p>
          </div>
        </div>
      )}

      {/* Engines */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Engines</h3>
          <Link
            href="/settings/engines/new"
            className="px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-500 text-white rounded-md transition-colors"
          >
            New Engine
          </Link>
        </div>
        {enginesLoading ? (
          <SkeletonTable rows={3} cols={4} />
        ) : enginesError ? (
          <QueryError error={enginesError as Error} message="Failed to load engines" onRetry={refetchEngines} />
        ) : (
          <div className="border border-gray-800 rounded-lg bg-gray-900">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-800">
                  <th className="text-left p-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Engine</th>
                  <th className="text-left p-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Provider</th>
                  <th className="text-left p-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Model</th>
                  <th className="text-left p-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Kind</th>
                  <th className="text-right p-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody>
                {(engines ?? []).map((engine: Engine) => (
                  <tr key={engine.name} className="border-b border-gray-800 last:border-0 hover:bg-gray-800/30 transition-colors">
                    <td className="p-3 font-mono text-sm">{engine.name}</td>
                    <td className="p-3 text-sm text-gray-300">{engine.provider}</td>
                    <td className="p-3 text-sm text-gray-300">{engine.model}</td>
                    <td className="p-3">
                      <span className="text-xs px-2 py-0.5 rounded-full bg-gray-800 text-gray-400 border border-gray-700">
                        {engine.kind}
                      </span>
                    </td>
                    <td className="p-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        {engine.source !== 'env' && engine.source !== 'local' && (
                          <>
                            <Link
                              href={`/settings/engines/edit?name=${encodeURIComponent(engine.name)}`}
                              className="text-xs px-2 py-1 bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-gray-200 rounded transition-colors"
                            >
                              Edit
                            </Link>
                            <button
                              type="button"
                              onClick={() => setDeleteTarget(engine.name)}
                              className="text-xs px-2 py-1 bg-red-600/10 hover:bg-red-600/20 text-red-400 rounded transition-colors"
                            >
                              Delete
                            </button>
                          </>
                        )}
                        {(engine.source === 'env' || engine.source === 'local') && (
                          <span className="text-xs text-gray-600 italic">auto-discovered</span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Environment Variables (read-only) */}
      {config?.env_vars && config.env_vars.length > 0 && (
        <div className="border border-gray-800 rounded-lg p-6 bg-gray-900/50">
          <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Environment Variables</h3>
          <p className="text-xs text-gray-600 mb-3">Detected MiniAutoGen-related environment variables (values masked).</p>
          <div className="space-y-2">
            {config.env_vars.map((v) => (
              <div key={v.name} className="flex items-center gap-3">
                <span className="font-mono text-sm text-gray-300">{v.name}</span>
                <span className="text-xs text-gray-600">{v.value}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {deleteTarget && (
        <DeleteConfirmModal
          resourceName={deleteTarget}
          resourceType="Engine"
          onConfirm={handleDelete}
          onCancel={() => setDeleteTarget(null)}
          isDeleting={deleteEngine.isPending}
        />
      )}
    </div>
  );
}
```

---

### Task 11: Create engine new/edit pages

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/console/src/app/settings/engines/new/page.tsx`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/console/src/app/settings/engines/edit/page.tsx`

**Prerequisites:**
- Task 9 complete (EngineForm component exists)

**Step 1: Create the new engine page**

Create file `/Users/brunocapelao/Projects/miniAutoGen/console/src/app/settings/engines/new/page.tsx`:

```tsx
'use client';

import { EngineForm } from '@/components/EngineForm';

export default function NewEnginePage() {
  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">New Engine</h2>
      <EngineForm mode="create" />
    </div>
  );
}
```

**Step 2: Create the edit engine page**

Create file `/Users/brunocapelao/Projects/miniAutoGen/console/src/app/settings/engines/edit/page.tsx`:

```tsx
'use client';

import { useSearchParams } from 'next/navigation';
import { useEngine } from '@/hooks/useApi';
import { EngineForm } from '@/components/EngineForm';
import { SkeletonTable } from '@/components/Skeleton';
import { QueryError } from '@/components/QueryError';

export default function EditEnginePage() {
  const searchParams = useSearchParams();
  const name = searchParams.get('name') ?? '';
  const { data: engine, isLoading, error, refetch } = useEngine(name);

  if (!name) return <p className="text-gray-400">No engine name provided.</p>;
  if (isLoading) return <SkeletonTable rows={5} cols={2} />;
  if (error) return <QueryError error={error as Error} message="Failed to load engine" onRetry={refetch} />;

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Edit Engine: {name}</h2>
      {engine && <EngineForm mode="edit" initialData={engine} />}
    </div>
  );
}
```

---

### Task 12: Add Settings to sidebar navigation

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/console/src/app/layout.tsx`

**Prerequisites:**
- Task 10 complete (settings page exists)

**Step 1: Add settings icon to ICONS**

In `/Users/brunocapelao/Projects/miniAutoGen/console/src/app/layout.tsx`, add after the `/runs` icon entry (after line 39):

```typescript
  '/settings': (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
      <path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z" />
    </svg>
  ),
```

**Step 2: Add Settings to NAV_ITEMS**

In the same file, add `{ href: '/settings', label: 'Settings' }` to the `NAV_ITEMS` array (after the `/runs` entry):

```typescript
const NAV_ITEMS = [
  { href: '/', label: 'Dashboard' },
  { href: '/agents', label: 'Agents' },
  { href: '/flows', label: 'Flows' },
  { href: '/runs', label: 'Runs' },
  { href: '/settings', label: 'Settings' },
];
```

**Step 3: Commit all G6 frontend work**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add console/src/types/api.ts console/src/lib/api-client.ts console/src/hooks/useApi.ts console/src/components/EngineForm.tsx console/src/app/settings/ console/src/app/layout.tsx
git commit -m "feat(console): add settings page with engine CRUD and config viewer"
```

---

### Task 13: Run Code Review (G6 checkpoint)

1. **Dispatch all 3 reviewers in parallel:**
   - REQUIRED SUB-SKILL: Use requesting-code-review
   - All reviewers run simultaneously (code-reviewer, business-logic-reviewer, security-reviewer)
   - Wait for all to complete

2. **Handle findings by severity (MANDATORY):**

**Critical/High/Medium Issues:**
- Fix immediately (do NOT add TODO comments for these severities)
- Re-run all 3 reviewers in parallel after fixes
- Repeat until zero Critical/High/Medium issues remain

**Low Issues:**
- Add `TODO(review):` comments in code at the relevant location
- Format: `TODO(review): [Issue description] (reported by [reviewer] on [date], severity: Low)`

**Cosmetic/Nitpick Issues:**
- Add `FIXME(nitpick):` comments in code at the relevant location
- Format: `FIXME(nitpick): [Issue description] (reported by [reviewer] on [date], severity: Cosmetic)`

3. **Proceed only when:**
   - Zero Critical/High/Medium issues remain
   - All Low issues have TODO(review): comments added
   - All Cosmetic issues have FIXME(nitpick): comments added

---

## G7: Log Viewer with Streaming in Web Console

### Task 14: Create global WebSocket event sink

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/server/global_ws.py`

**Prerequisites:**
- Understanding of existing `ws.py` (per-run WebSocket). The global WS broadcasts ALL events regardless of run_id.

**Step 1: Create the global WebSocket module**

Create file `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/server/global_ws.py`:

```python
"""Global WebSocket event streaming for the MiniAutoGen Console.

Unlike ws.py which streams events per-run, this module provides a global
endpoint that broadcasts ALL events (for the log viewer page).

Clients can filter client-side by event type, agent, flow.
"""

from __future__ import annotations

import json
import logging
from collections import deque
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.event_sink import EventSink

logger = logging.getLogger(__name__)

MAX_GLOBAL_EVENTS = 5_000
MAX_GLOBAL_CONNECTIONS = 20


class GlobalEventSink(EventSink):
    """EventSink that stores all events and broadcasts to global WebSocket clients.

    All events are accepted (including those without run_id).
    Events are stored in a bounded deque for replay on connect.
    """

    def __init__(self, *, replay_count: int = 100) -> None:
        self._events: deque[ExecutionEvent] = deque(maxlen=MAX_GLOBAL_EVENTS)
        self._connections: list[WebSocket] = []
        self._replay_count = replay_count

    async def publish(self, event: ExecutionEvent) -> None:
        self._events.append(event)

        message = event.model_dump_json()
        dead_connections: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead_connections.append(ws)

        for ws in dead_connections:
            try:
                self._connections.remove(ws)
            except ValueError:
                pass

    def get_recent_events(self, count: int | None = None) -> list[dict[str, Any]]:
        """Get recent events as dicts for REST endpoint fallback."""
        limit = count or len(self._events)
        recent = list(self._events)[-limit:]
        return [json.loads(e.model_dump_json()) for e in recent]

    async def connect(self, websocket: WebSocket) -> None:
        if len(self._connections) >= MAX_GLOBAL_CONNECTIONS:
            await websocket.close(code=1013, reason="Too many connections")
            return
        await websocket.accept()
        self._connections.append(websocket)
        try:
            # Send replay of recent events
            replay = list(self._events)[-self._replay_count:]
            await websocket.send_json({
                "type": "connected",
                "replay_count": len(replay),
            })
            for event in replay:
                await websocket.send_text(event.model_dump_json())
        except Exception:
            try:
                self._connections.remove(websocket)
            except ValueError:
                pass

    def disconnect(self, websocket: WebSocket) -> None:
        try:
            self._connections.remove(websocket)
        except ValueError:
            pass


def global_ws_router(event_sink: GlobalEventSink) -> APIRouter:
    router = APIRouter(tags=["websocket"])

    @router.websocket("/ws/events")
    async def ws_global_events(websocket: WebSocket) -> None:
        await event_sink.connect(websocket)
        try:
            while True:
                data = await websocket.receive_json()
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            event_sink.disconnect(websocket)
        except Exception as exc:
            logger.warning("Global WebSocket error: %s", exc)
            event_sink.disconnect(websocket)
            try:
                await websocket.close(code=1011, reason="Internal error")
            except Exception:
                pass

    @router.get("/api/v1/events", tags=["events"])
    async def list_recent_events(
        limit: int = 100,
        event_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """REST fallback for recent events (for clients that don't use WebSocket)."""
        events = event_sink.get_recent_events(limit)
        if event_type:
            events = [e for e in events if e.get("type") == event_type]
        return events

    return router
```

**Step 2: Verify import**

Run: `python -c "from miniautogen.server.global_ws import GlobalEventSink, global_ws_router; print('OK')"`

**Expected output:**
```
OK
```

---

### Task 15: Integrate GlobalEventSink into FastAPI app

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/server/app.py`

**Prerequisites:**
- Task 14 complete (global_ws module exists)

**Step 1: Import GlobalEventSink and router**

In `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/server/app.py`, add after the `from miniautogen.server.ws import WebSocketEventSink, ws_router` line:

```python
from miniautogen.server.global_ws import GlobalEventSink, global_ws_router
```

**Step 2: Create global event sink and register router**

In the same file, after the line `event_sink = None` (line 66), add:

```python
    # Global event sink for log viewer (all modes)
    global_event_sink = GlobalEventSink()
```

After the line `if event_sink is not None:` block (after line 80), add:

```python
    # Global WebSocket for event streaming (log viewer)
    app.include_router(global_ws_router(global_event_sink))
    app.state.global_event_sink = global_event_sink
```

**Step 3: Verify app creation**

Run: `python -c "from miniautogen.server.app import create_app; app = create_app(); print('global' in str(app.state.__dict__))"`

**Expected output:** Should not error.

---

### Task 16: Write tests for global WebSocket and events endpoint

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/server/test_global_ws.py`

**Prerequisites:**
- Task 15 complete (global WS integrated)

**Step 1: Create the test file**

Create file `/Users/brunocapelao/Projects/miniAutoGen/tests/server/test_global_ws.py`:

```python
"""Tests for global WebSocket event streaming and REST events endpoint."""

from __future__ import annotations

import pytest

from miniautogen.server.global_ws import GlobalEventSink
from miniautogen.core.contracts.events import ExecutionEvent


@pytest.mark.anyio
async def test_global_event_sink_stores_events():
    sink = GlobalEventSink()
    event = ExecutionEvent(type="test_event", run_id="r1", payload={"key": "value"})
    await sink.publish(event)
    events = sink.get_recent_events()
    assert len(events) == 1
    assert events[0]["type"] == "test_event"


@pytest.mark.anyio
async def test_global_event_sink_bounded():
    sink = GlobalEventSink()
    sink._events = __import__("collections").deque(maxlen=5)
    for i in range(10):
        await sink.publish(ExecutionEvent(type=f"event_{i}", payload={}))
    assert len(sink._events) == 5
    events = sink.get_recent_events()
    assert events[0]["type"] == "event_5"


def test_rest_events_endpoint(client):
    """Test the /api/v1/events REST endpoint returns recent events."""
    resp = client.get("/api/v1/events")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_rest_events_with_type_filter(client):
    """Test /api/v1/events with event_type filter."""
    resp = client.get("/api/v1/events?event_type=run_started&limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
```

**Step 2: Run tests**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/server/test_global_ws.py -v`

**Expected output:**
```
tests/server/test_global_ws.py::test_global_event_sink_stores_events PASSED
tests/server/test_global_ws.py::test_global_event_sink_bounded PASSED
tests/server/test_global_ws.py::test_rest_events_endpoint PASSED
tests/server/test_global_ws.py::test_rest_events_with_type_filter PASSED
```

**Step 3: Commit**

```bash
git add miniautogen/server/global_ws.py miniautogen/server/app.py tests/server/test_global_ws.py
git commit -m "feat(server): add global WebSocket event streaming for log viewer"
```

---

### Task 17: Add event streaming hook to frontend

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/console/src/hooks/useEventStream.ts`

**Prerequisites:**
- Task 15 complete (WebSocket endpoint `/ws/events` available)

**Step 1: Create the event stream hook**

Create file `/Users/brunocapelao/Projects/miniAutoGen/console/src/hooks/useEventStream.ts`:

```typescript
'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import type { RunEvent } from '@/types/api';

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || `ws://${typeof window !== 'undefined' ? window.location.host : 'localhost:8080'}`;

type EventFilter = {
  eventType?: string;
  agent?: string;
  flow?: string;
};

type UseEventStreamReturn = {
  events: RunEvent[];
  connected: boolean;
  error: string | null;
  clearEvents: () => void;
};

export function useEventStream(filter?: EventFilter, maxEvents = 500): UseEventStreamReturn {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout>>();

  const clearEvents = useCallback(() => setEvents([]), []);

  useEffect(() => {
    let cancelled = false;

    function connect() {
      if (cancelled) return;

      const ws = new WebSocket(`${WS_BASE}/ws/events`);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        setError(null);
      };

      ws.onmessage = (evt) => {
        try {
          const data = JSON.parse(evt.data);
          if (data.type === 'connected' || data.type === 'pong') return;

          const event: RunEvent = {
            type: data.type,
            timestamp: data.timestamp,
            run_id: data.run_id ?? '',
            scope: data.scope ?? '',
            payload: data.payload ?? {},
          };

          // Apply client-side filters
          if (filter?.eventType && event.type !== filter.eventType) return;
          if (filter?.agent && event.scope !== filter.agent) return;

          setEvents((prev) => {
            const next = [...prev, event];
            return next.length > maxEvents ? next.slice(-maxEvents) : next;
          });
        } catch {
          // Ignore unparseable messages
        }
      };

      ws.onclose = () => {
        setConnected(false);
        if (!cancelled) {
          reconnectTimeoutRef.current = setTimeout(connect, 3000);
        }
      };

      ws.onerror = () => {
        setError('WebSocket connection failed');
        ws.close();
      };
    }

    connect();

    // Ping keepalive
    const pingInterval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000);

    return () => {
      cancelled = true;
      clearInterval(pingInterval);
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      wsRef.current?.close();
    };
  }, [filter?.eventType, filter?.agent, filter?.flow, maxEvents]);

  return { events, connected, error, clearEvents };
}
```

---

### Task 18: Create Logs page

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/console/src/app/logs/page.tsx`

**Prerequisites:**
- Task 17 complete (useEventStream hook available)

**Step 1: Create the logs page**

Create file `/Users/brunocapelao/Projects/miniAutoGen/console/src/app/logs/page.tsx`:

```tsx
'use client';

import { useState, useRef, useEffect } from 'react';
import { useEventStream } from '@/hooks/useEventStream';
import type { RunEvent } from '@/types/api';

const SEVERITY_COLORS: Record<string, string> = {
  error: 'bg-red-500/20 text-red-400 border-red-500/30',
  warning: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  info: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
};

function getSeverity(eventType: string): string {
  if (eventType.includes('error') || eventType.includes('failed')) return 'error';
  if (eventType.includes('warning') || eventType.includes('retry')) return 'warning';
  return 'info';
}

function EventRow({ event }: { event: RunEvent }) {
  const severity = getSeverity(event.type);
  const colors = SEVERITY_COLORS[severity] ?? SEVERITY_COLORS.info;
  const time = new Date(event.timestamp).toLocaleTimeString();

  return (
    <div className="flex items-start gap-3 px-4 py-2 border-b border-gray-800/50 hover:bg-gray-800/20 transition-colors text-sm font-mono">
      <span className="text-gray-600 text-xs w-20 flex-shrink-0 pt-0.5">{time}</span>
      <span className={`text-xs px-1.5 py-0.5 rounded border ${colors} flex-shrink-0`}>
        {severity}
      </span>
      <span className="text-gray-300 flex-shrink-0 w-48 truncate" title={event.type}>
        {event.type}
      </span>
      <span className="text-gray-500 truncate" title={event.scope ?? ''}>
        {event.scope || '-'}
      </span>
      {event.run_id && (
        <span className="text-gray-600 text-xs ml-auto flex-shrink-0">
          {event.run_id.slice(0, 8)}
        </span>
      )}
    </div>
  );
}

export default function LogsPage() {
  const [typeFilter, setTypeFilter] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  const filter = typeFilter ? { eventType: typeFilter } : undefined;
  const { events, connected, error, clearEvents } = useEventStream(filter);

  // Auto-scroll on new events
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events.length, autoScroll]);

  // Pause auto-scroll on manual scroll
  function handleScroll() {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    const atBottom = scrollHeight - scrollTop - clientHeight < 50;
    setAutoScroll(atBottom);
  }

  function handleExport() {
    const blob = new Blob([JSON.stringify(events, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `miniautogen-events-${new Date().toISOString().slice(0, 19)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h2 className="text-2xl font-bold">Logs</h2>
          <span className={`flex items-center gap-1.5 text-xs ${connected ? 'text-green-400' : 'text-red-400'}`}>
            <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`} />
            {connected ? 'Live' : 'Disconnected'}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <input
            type="text"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            placeholder="Filter by event type..."
            className="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-md text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500 w-56"
          />
          <button
            type="button"
            onClick={clearEvents}
            className="px-3 py-1.5 text-xs bg-gray-800 hover:bg-gray-700 text-gray-400 rounded-md transition-colors"
          >
            Clear
          </button>
          <button
            type="button"
            onClick={handleExport}
            disabled={events.length === 0}
            className="px-3 py-1.5 text-xs bg-gray-800 hover:bg-gray-700 text-gray-400 rounded-md transition-colors disabled:opacity-50"
          >
            Export JSON
          </button>
        </div>
      </div>

      {error && (
        <div className="border border-yellow-500/30 bg-yellow-500/5 rounded-lg p-3 mb-4">
          <p className="text-yellow-400 text-sm">{error}. Events will resume when server is available.</p>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-gray-700 text-xs font-medium text-gray-500 uppercase tracking-wider bg-gray-900/50 rounded-t-lg">
        <span className="w-20 flex-shrink-0">Time</span>
        <span className="w-14 flex-shrink-0">Level</span>
        <span className="w-48 flex-shrink-0">Event Type</span>
        <span className="flex-1">Scope</span>
        <span className="w-16 text-right flex-shrink-0">Run</span>
      </div>

      {/* Event list */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="flex-1 overflow-auto border border-gray-800 rounded-b-lg bg-gray-900/30"
      >
        {events.length === 0 ? (
          <div className="flex items-center justify-center h-48 text-gray-600 text-sm">
            {connected ? 'Waiting for events...' : 'Connect to see live events'}
          </div>
        ) : (
          events.map((event: RunEvent, idx: number) => (
            <EventRow key={`${event.timestamp}-${idx}`} event={event} />
          ))
        )}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between mt-2 text-xs text-gray-600">
        <span>{events.length} events</span>
        <button
          type="button"
          onClick={() => {
            setAutoScroll(true);
            scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
          }}
          className={`transition-colors ${autoScroll ? 'text-gray-600' : 'text-blue-400 hover:text-blue-300'}`}
        >
          {autoScroll ? 'Auto-scroll on' : 'Scroll to bottom'}
        </button>
      </div>
    </div>
  );
}
```

---

### Task 19: Add Logs to sidebar navigation

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/console/src/app/layout.tsx`

**Prerequisites:**
- Task 18 complete (logs page exists)

**Step 1: Add logs icon to ICONS**

In `/Users/brunocapelao/Projects/miniAutoGen/console/src/app/layout.tsx`, add after the `/settings` icon entry:

```typescript
  '/logs': (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
      <path d="M14 2v6h6" />
      <path d="M16 13H8" />
      <path d="M16 17H8" />
      <path d="M10 9H8" />
    </svg>
  ),
```

**Step 2: Add Logs to NAV_ITEMS**

Add `{ href: '/logs', label: 'Logs' }` after Settings:

```typescript
const NAV_ITEMS = [
  { href: '/', label: 'Dashboard' },
  { href: '/agents', label: 'Agents' },
  { href: '/flows', label: 'Flows' },
  { href: '/runs', label: 'Runs' },
  { href: '/logs', label: 'Logs' },
  { href: '/settings', label: 'Settings' },
];
```

**Step 3: Commit all G7 work**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add console/src/hooks/useEventStream.ts console/src/app/logs/ console/src/app/layout.tsx
git commit -m "feat(console): add logs page with real-time event streaming via WebSocket"
```

---

### Task 20: Run Code Review (G7 checkpoint)

1. **Dispatch all 3 reviewers in parallel:**
   - REQUIRED SUB-SKILL: Use requesting-code-review
   - All reviewers run simultaneously (code-reviewer, business-logic-reviewer, security-reviewer)
   - Wait for all to complete

2. **Handle findings by severity (MANDATORY):**

**Critical/High/Medium Issues:**
- Fix immediately (do NOT add TODO comments for these severities)
- Re-run all 3 reviewers in parallel after fixes
- Repeat until zero Critical/High/Medium issues remain

**Low Issues:**
- Add `TODO(review):` comments in code at the relevant location

**Cosmetic/Nitpick Issues:**
- Add `FIXME(nitpick):` comments in code at the relevant location

3. **Proceed only when:**
   - Zero Critical/High/Medium issues remain

---

## G8: `miniautogen status` Command

### Task 21: Create status service

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/status_ops.py`

**Prerequisites:**
- Existing services: `server_ops.py`, `engine_ops.py`, `agent_ops.py`, `pipeline_ops.py`

**Step 1: Create the status service**

Create file `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/status_ops.py`:

```python
"""Workspace status aggregation service for the CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from miniautogen.cli.config import (
    CONFIG_FILENAME,
    load_config,
)
from miniautogen.cli.services.agent_ops import list_agents
from miniautogen.cli.services.engine_ops import list_engines
from miniautogen.cli.services.pipeline_ops import list_pipelines
from miniautogen.cli.services.server_ops import server_status


def workspace_status(project_root: Path) -> dict[str, Any]:
    """Aggregate workspace status from all subsystems.

    Returns a dict with keys: project, server, agents, engines, flows, runs.
    Each key has relevant counts and metadata.
    """
    config_path = project_root / CONFIG_FILENAME
    result: dict[str, Any] = {
        "project": {"name": "(unknown)", "version": "(unknown)"},
        "server": {"status": "stopped", "message": "No server running."},
        "agents": {"count": 0, "names": []},
        "engines": {"count": 0, "names": []},
        "flows": {"count": 0, "names": []},
        "runs": {"total": 0, "completed": 0, "running": 0, "failed": 0},
        "last_run": None,
    }

    # Project metadata
    if config_path.is_file():
        try:
            config = load_config(config_path)
            result["project"] = {
                "name": config.project.name,
                "version": config.project.version,
            }
        except Exception:
            pass

    # Server status
    try:
        result["server"] = server_status(project_root)
    except Exception:
        pass

    # Agents
    try:
        agents = list_agents(project_root)
        result["agents"] = {
            "count": len(agents),
            "names": [a["name"] for a in agents],
        }
    except Exception:
        pass

    # Engines
    try:
        engines = list_engines(project_root)
        result["engines"] = {
            "count": len(engines),
            "names": [e["name"] for e in engines],
        }
    except Exception:
        pass

    # Flows
    try:
        flows = list_pipelines(project_root)
        result["flows"] = {
            "count": len(flows),
            "names": [f["name"] for f in flows],
        }
    except Exception:
        pass

    # Runs summary (from SQLite if available)
    try:
        db_path = project_root / "miniautogen.db"
        if db_path.is_file():
            import sqlite3

            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # Total runs
            cursor.execute("SELECT COUNT(*) FROM runs")
            total = cursor.fetchone()[0]

            # By status
            cursor.execute(
                "SELECT status, COUNT(*) FROM runs GROUP BY status"
            )
            status_counts = dict(cursor.fetchall())

            # Last run
            cursor.execute(
                "SELECT run_id, pipeline, status, started FROM runs "
                "ORDER BY started DESC LIMIT 1"
            )
            last = cursor.fetchone()

            conn.close()

            result["runs"] = {
                "total": total,
                "completed": status_counts.get("completed", 0),
                "running": status_counts.get("running", 0),
                "failed": status_counts.get("failed", 0),
            }
            if last:
                result["last_run"] = {
                    "run_id": last[0],
                    "pipeline": last[1],
                    "status": last[2],
                    "started": last[3],
                }
    except Exception:
        pass

    return result
```

**Step 2: Verify import**

Run: `python -c "from miniautogen.cli.services.status_ops import workspace_status; print('OK')"`

**Expected output:**
```
OK
```

---

### Task 22: Write tests for status service

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/test_status_ops.py`

**Prerequisites:**
- Task 21 complete (status service exists)

**Step 1: Check tests directory exists**

Run: `ls /Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/ 2>/dev/null || echo "needs creation"`

If "needs creation" is shown, create the directory.

**Step 2: Create the test file**

Create file `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/test_status_ops.py`:

```python
"""Tests for workspace_status service."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


def test_workspace_status_empty_dir(tmp_path):
    """Status on a dir without miniautogen.yaml returns defaults."""
    from miniautogen.cli.services.status_ops import workspace_status

    result = workspace_status(tmp_path)
    assert result["project"]["name"] == "(unknown)"
    assert result["agents"]["count"] == 0
    assert result["engines"]["count"] == 0
    assert result["flows"]["count"] == 0
    assert result["runs"]["total"] == 0


def test_workspace_status_with_config(tmp_path):
    """Status picks up project metadata from config."""
    config_content = """
project:
  name: test-project
  version: "1.0.0"
defaults:
  engine: default_api
engines:
  default_api:
    kind: api
    provider: openai
    model: gpt-4o
flows:
  main:
    mode: workflow
    participants: []
"""
    (tmp_path / "miniautogen.yaml").write_text(config_content)

    from miniautogen.cli.services.status_ops import workspace_status

    result = workspace_status(tmp_path)
    assert result["project"]["name"] == "test-project"
    assert result["project"]["version"] == "1.0.0"
    assert result["engines"]["count"] >= 1


def test_workspace_status_server_stopped(tmp_path):
    """Status reports server as stopped when no PID file."""
    (tmp_path / "miniautogen.yaml").write_text("project:\n  name: test\n")

    from miniautogen.cli.services.status_ops import workspace_status

    result = workspace_status(tmp_path)
    assert result["server"]["status"] == "stopped"
```

**Step 3: Run tests**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/services/test_status_ops.py -v`

**Expected output:**
```
tests/cli/services/test_status_ops.py::test_workspace_status_empty_dir PASSED
tests/cli/services/test_status_ops.py::test_workspace_status_with_config PASSED
tests/cli/services/test_status_ops.py::test_workspace_status_server_stopped PASSED
```

---

### Task 23: Create status CLI command

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/commands/status.py`

**Prerequisites:**
- Task 21 complete (status service exists)

**Step 1: Create the status command**

Create file `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/commands/status.py`:

```python
"""miniautogen status command -- workspace overview."""

from __future__ import annotations

import click

from miniautogen.cli.config import require_project_config
from miniautogen.cli.output import echo_error, echo_info, echo_success, echo_warning


@click.command("status")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def status_command(as_json: bool) -> None:
    """Show workspace status overview."""
    from miniautogen.cli.services.status_ops import workspace_status

    root, _config = require_project_config()
    result = workspace_status(root)

    if as_json:
        from miniautogen.cli.output import echo_json

        echo_json(result)
        return

    # Project header
    project = result["project"]
    click.echo()
    click.echo(f"  Workspace: {project['name']} (v{project['version']})")

    # Server status
    server = result["server"]
    status = server["status"]
    if status == "running":
        port = server.get("port", "?")
        echo_success(f"  Server:    ● running on :{port}")
    elif status == "degraded":
        echo_warning(f"  Server:    ◐ degraded ({server.get('message', '')})")
    elif status == "unreachable":
        echo_warning(f"  Server:    ○ unreachable ({server.get('message', '')})")
    else:
        echo_info("  Server:    ○ stopped")

    # Agents
    agents = result["agents"]
    names = ", ".join(agents["names"][:6])
    if agents["count"] > 6:
        names += f" (+{agents['count'] - 6} more)"
    click.echo(f"  Agents:    {agents['count']} configured ({names})" if agents["count"] else "  Agents:    0 configured")

    # Engines
    engines = result["engines"]
    enames = ", ".join(engines["names"][:4])
    if engines["count"] > 4:
        enames += f" (+{engines['count'] - 4} more)"
    click.echo(f"  Engines:   {engines['count']} configured ({enames})" if engines["count"] else "  Engines:   0 configured")

    # Flows
    flows = result["flows"]
    fnames = ", ".join(flows["names"][:4])
    if flows["count"] > 4:
        fnames += f" (+{flows['count'] - 4} more)"
    click.echo(f"  Flows:     {flows['count']} configured ({fnames})" if flows["count"] else "  Flows:     0 configured")

    # Runs
    runs = result["runs"]
    if runs["total"] > 0:
        parts = []
        if runs["completed"]:
            parts.append(f"{runs['completed']} completed")
        if runs["running"]:
            parts.append(f"{runs['running']} running")
        if runs["failed"]:
            parts.append(f"{runs['failed']} failed")
        click.echo(f"  Runs:      {runs['total']} total ({', '.join(parts)})")
    else:
        click.echo("  Runs:      0 total")

    # Last run
    last_run = result.get("last_run")
    if last_run:
        from datetime import datetime, timezone

        try:
            started = datetime.fromisoformat(last_run["started"])
            now = datetime.now(timezone.utc)
            delta = now - started
            if delta.days > 0:
                ago = f"{delta.days}d ago"
            elif delta.seconds > 3600:
                ago = f"{delta.seconds // 3600}h ago"
            elif delta.seconds > 60:
                ago = f"{delta.seconds // 60}m ago"
            else:
                ago = "just now"
        except Exception:
            ago = last_run.get("started", "?")
        click.echo(f"  Last run:  {last_run['pipeline']} -- {last_run['status']} {ago}")

    click.echo()
```

**Step 2: Verify import**

Run: `python -c "from miniautogen.cli.commands.status import status_command; print('OK')"`

**Expected output:**
```
OK
```

---

### Task 24: Register status command in CLI

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/main.py`

**Prerequisites:**
- Task 23 complete (status command exists)

**Step 1: Add status command registration**

In `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/main.py`, add after the `cli.add_command(chat_command)` line (at end of file):

```python

from miniautogen.cli.commands.status import status_command  # noqa: E402

cli.add_command(status_command)
```

**Step 2: Verify CLI registration**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m miniautogen.cli.main status --help`

**Expected output:**
```
Usage: main status [OPTIONS]

  Show workspace status overview.

Options:
  --json  Output as JSON.
  --help  Show this message and exit.
```

---

### Task 25: Write test for status command

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/commands/test_status_command.py`

**Prerequisites:**
- Task 24 complete (command registered)

**Step 1: Check tests directory exists**

Run: `ls /Users/brunocapelao/Projects/miniAutoGen/tests/cli/commands/ 2>/dev/null || echo "needs creation"`

**Step 2: Create the test file**

Create file `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/commands/test_status_command.py`:

```python
"""Tests for miniautogen status command."""

from __future__ import annotations

import os

from click.testing import CliRunner

from miniautogen.cli.main import cli


def test_status_command_no_project(tmp_path):
    """Status fails gracefully when no project config found."""
    runner = CliRunner()
    result = runner.invoke(cli, ["status"], catch_exceptions=False)
    # Should error because no miniautogen.yaml in cwd
    assert result.exit_code != 0 or "not found" in result.output.lower() or "no project" in result.output.lower() or "error" in result.output.lower()


def test_status_command_with_project(tmp_path):
    """Status shows workspace info when config exists."""
    config = """
project:
  name: test-project
  version: "1.0.0"
defaults:
  engine: default_api
engines:
  default_api:
    kind: api
    provider: openai
    model: gpt-4o
flows:
  main:
    mode: workflow
    participants: []
"""
    (tmp_path / "miniautogen.yaml").write_text(config)

    runner = CliRunner()
    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        result = runner.invoke(cli, ["status"], catch_exceptions=False)
    finally:
        os.chdir(old_cwd)

    assert result.exit_code == 0
    assert "test-project" in result.output
    assert "Workspace" in result.output


def test_status_command_json_output(tmp_path):
    """Status --json outputs JSON."""
    config = """
project:
  name: json-test
  version: "0.1.0"
defaults:
  engine: default_api
engines:
  default_api:
    kind: api
    provider: openai
    model: gpt-4o
"""
    (tmp_path / "miniautogen.yaml").write_text(config)

    runner = CliRunner()
    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        result = runner.invoke(cli, ["status", "--json"], catch_exceptions=False)
    finally:
        os.chdir(old_cwd)

    assert result.exit_code == 0
    import json
    data = json.loads(result.output)
    assert data["project"]["name"] == "json-test"
```

**Step 3: Run tests**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/commands/test_status_command.py -v`

**Expected output:**
```
tests/cli/commands/test_status_command.py::test_status_command_no_project PASSED
tests/cli/commands/test_status_command.py::test_status_command_with_project PASSED
tests/cli/commands/test_status_command.py::test_status_command_json_output PASSED
```

**Step 4: Commit all G8 work**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/cli/services/status_ops.py miniautogen/cli/commands/status.py miniautogen/cli/main.py tests/cli/services/test_status_ops.py tests/cli/commands/test_status_command.py
git commit -m "feat(cli): add miniautogen status command for workspace overview"
```

---

### Task 26: Run Code Review (G8 checkpoint)

1. **Dispatch all 3 reviewers in parallel:**
   - REQUIRED SUB-SKILL: Use requesting-code-review
   - All reviewers run simultaneously (code-reviewer, business-logic-reviewer, security-reviewer)
   - Wait for all to complete

2. **Handle findings by severity (MANDATORY):**
   - Critical/High/Medium: Fix immediately
   - Low: Add `TODO(review):` comments
   - Cosmetic: Add `FIXME(nitpick):` comments

3. **Proceed only when zero Critical/High/Medium issues remain**

---

## G9: Docker Image

### Task 27: Create .dockerignore

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/.dockerignore`

**Prerequisites:**
- None (standalone file)

**Step 1: Create .dockerignore**

Create file `/Users/brunocapelao/Projects/miniAutoGen/.dockerignore`:

```
.git
.gitignore
__pycache__
*.pyc
*.pyo
.pytest_cache
.mypy_cache
.ruff_cache
.tox
.venv
venv
env
node_modules
console/node_modules
console/.next
.miniautogen/
*.egg-info
dist
build
*.db
*.sqlite3
.env
.env.*
!.env.example
docs/
tests/
*.md
!README.md
output/
teste/
Projeto/
```

---

### Task 28: Create Dockerfile

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/Dockerfile`

**Prerequisites:**
- Task 27 complete (.dockerignore exists)

**Step 1: Create the Dockerfile**

Create file `/Users/brunocapelao/Projects/miniAutoGen/Dockerfile`:

```dockerfile
# Stage 1: Build console frontend
FROM node:20-alpine AS console-builder

WORKDIR /app/console
COPY console/package.json console/package-lock.json* ./
RUN npm ci --ignore-scripts 2>/dev/null || npm install --ignore-scripts
COPY console/ ./
RUN npm run build

# Stage 2: Python application
FROM python:3.11-slim AS runtime

# Set labels
LABEL org.opencontainers.image.title="MiniAutoGen"
LABEL org.opencontainers.image.description="Multi-agent orchestration framework"
LABEL org.opencontainers.image.source="https://github.com/miniautogen/miniautogen"

# Create non-root user
RUN groupadd -r miniautogen && useradd -r -g miniautogen -d /app -s /bin/bash miniautogen

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml setup.py ./
COPY miniautogen/ ./miniautogen/
RUN pip install --no-cache-dir -e ".[all]" 2>/dev/null || pip install --no-cache-dir -e .

# Copy built console static files
COPY --from=console-builder /app/console/out/ ./miniautogen/server/static/

# Create workspace volume mount point
RUN mkdir -p /workspace && chown miniautogen:miniautogen /workspace

# Switch to non-root user
USER miniautogen

# Default workspace
WORKDIR /workspace

# Expose API port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health', timeout=3)" || exit 1

# Default command: start console server
ENTRYPOINT ["python", "-m", "miniautogen.cli.main"]
CMD ["console", "--host", "0.0.0.0", "--port", "8080"]
```

---

### Task 29: Create docker-compose.yml

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/docker-compose.yml`

**Prerequisites:**
- Task 28 complete (Dockerfile exists)

**Step 1: Create docker-compose.yml**

Create file `/Users/brunocapelao/Projects/miniAutoGen/docker-compose.yml`:

```yaml
# MiniAutoGen Docker Compose
#
# Quick start:
#   docker compose up
#
# With workspace:
#   docker compose run -v $(pwd)/my-project:/workspace miniautogen
#
# Environment variables:
#   Set API keys in .env file or pass via environment

services:
  miniautogen:
    build: .
    ports:
      - "8080:8080"
    volumes:
      - ./:/workspace:ro  # Mount current dir as workspace (read-only by default)
      - miniautogen-data:/workspace/.miniautogen  # Persist runtime data
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY:-}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
      - GOOGLE_API_KEY=${GOOGLE_API_KEY:-}
      - MINIAUTOGEN_API_KEY=${MINIAUTOGEN_API_KEY:-}
    restart: unless-stopped

volumes:
  miniautogen-data:
```

---

### Task 30: Write Docker build test

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/docker/test_dockerfile.py`

**Prerequisites:**
- Task 28, 29 complete (Docker files exist)

**Step 1: Create a basic validation test (does not require Docker)**

Create file `/Users/brunocapelao/Projects/miniAutoGen/tests/docker/test_dockerfile.py`:

```python
"""Validation tests for Docker configuration (no Docker required)."""

from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent


def test_dockerfile_exists():
    assert (PROJECT_ROOT / "Dockerfile").is_file()


def test_docker_compose_exists():
    assert (PROJECT_ROOT / "docker-compose.yml").is_file()


def test_dockerignore_exists():
    assert (PROJECT_ROOT / ".dockerignore").is_file()


def test_dockerignore_excludes_secrets():
    content = (PROJECT_ROOT / ".dockerignore").read_text()
    assert ".env" in content
    assert "*.db" in content
    assert "tests/" in content


def test_dockerfile_uses_non_root_user():
    content = (PROJECT_ROOT / "Dockerfile").read_text()
    assert "USER" in content
    assert "miniautogen" in content


def test_dockerfile_has_healthcheck():
    content = (PROJECT_ROOT / "Dockerfile").read_text()
    assert "HEALTHCHECK" in content


def test_docker_compose_valid_yaml():
    import yaml
    content = (PROJECT_ROOT / "docker-compose.yml").read_text()
    data = yaml.safe_load(content)
    assert "services" in data
    assert "miniautogen" in data["services"]
```

**Step 2: Create __init__.py for docker test package**

Run: `touch /Users/brunocapelao/Projects/miniAutoGen/tests/docker/__init__.py`

**Step 3: Run tests**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/docker/test_dockerfile.py -v`

**Expected output:**
```
tests/docker/test_dockerfile.py::test_dockerfile_exists PASSED
tests/docker/test_dockerfile.py::test_docker_compose_exists PASSED
tests/docker/test_dockerfile.py::test_dockerignore_exists PASSED
tests/docker/test_dockerfile.py::test_dockerignore_excludes_secrets PASSED
tests/docker/test_dockerfile.py::test_dockerfile_uses_non_root_user PASSED
tests/docker/test_dockerfile.py::test_dockerfile_has_healthcheck PASSED
tests/docker/test_dockerfile.py::test_docker_compose_valid_yaml PASSED
```

**Step 4: Commit all G9 work**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add .dockerignore Dockerfile docker-compose.yml tests/docker/
git commit -m "feat(devops): add Dockerfile and docker-compose for deployment"
```

---

## G10: Daemon Mode Refinado

### Task 31: Create daemon service layer

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/daemon_ops.py`

**Prerequisites:**
- Existing `server_ops.py` has `start_server`, `stop_server`, `server_status`, `server_logs` functions. The daemon service wraps these with enhanced lifecycle management.

**Step 1: Create the daemon service**

Create file `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/daemon_ops.py`:

```python
"""Daemon lifecycle management service for the CLI.

Wraps server_ops with daemon-specific features:
- Always runs in daemon mode (background)
- Log rotation
- PID file management
- Restart semantics
"""

from __future__ import annotations

import os
import signal
import time
from pathlib import Path
from typing import Any

from miniautogen.cli.services.server_ops import (
    _logfile,
    _pidfile,
    _read_pid,
    _read_port,
    server_logs,
    server_status,
    start_server,
    stop_server,
)


def daemon_start(
    project_root: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8080,
) -> dict[str, Any]:
    """Start the daemon (always background mode)."""
    return start_server(project_root, host=host, port=port, daemon=True)


def daemon_stop(project_root: Path) -> dict[str, Any]:
    """Stop the daemon gracefully."""
    return stop_server(project_root)


def daemon_restart(
    project_root: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8080,
) -> dict[str, Any]:
    """Restart the daemon (stop + start)."""
    existing = _read_pid(project_root)
    if existing is not None:
        stop_result = stop_server(project_root)
        # Wait briefly for process to terminate
        for _ in range(10):
            try:
                os.kill(existing, 0)
                time.sleep(0.3)
            except OSError:
                break

    return daemon_start(project_root, host=host, port=port)


def daemon_status(project_root: Path) -> dict[str, Any]:
    """Get daemon status with enhanced info."""
    result = server_status(project_root)

    # Add log file info
    log_path = _logfile(project_root)
    if log_path.is_file():
        stat = log_path.stat()
        result["log_file"] = str(log_path)
        result["log_size_kb"] = round(stat.st_size / 1024, 1)
    else:
        result["log_file"] = None
        result["log_size_kb"] = 0

    # Add PID file info
    pid = _read_pid(project_root)
    if pid is not None:
        result["pid"] = pid

    return result


def daemon_logs(
    project_root: Path,
    *,
    lines: int = 50,
    follow: bool = False,
) -> str | None:
    """Get daemon logs.

    If follow=True, returns None (caller handles streaming).
    Otherwise returns the last N lines as a string.
    """
    if follow:
        return None  # Caller handles streaming
    return server_logs(project_root, lines=lines)


def daemon_logs_follow(project_root: Path) -> Path | None:
    """Return the log file path for follow mode, or None if no log file."""
    log_path = _logfile(project_root)
    if log_path.is_file():
        return log_path
    return None


def rotate_logs(project_root: Path, *, max_size_mb: float = 10.0) -> dict[str, Any]:
    """Rotate the daemon log file if it exceeds max_size_mb.

    Renames current log to .log.1 and creates fresh log file.
    Keeps at most 3 rotated files (.log.1, .log.2, .log.3).
    """
    log_path = _logfile(project_root)
    if not log_path.is_file():
        return {"rotated": False, "reason": "no log file"}

    size_mb = log_path.stat().st_size / (1024 * 1024)
    if size_mb < max_size_mb:
        return {"rotated": False, "reason": f"size {size_mb:.1f}MB < {max_size_mb}MB threshold"}

    # Rotate existing backups
    for i in range(3, 0, -1):
        old = log_path.with_suffix(f".log.{i}")
        new = log_path.with_suffix(f".log.{i + 1}")
        if i == 3 and old.is_file():
            old.unlink()  # Delete oldest
        elif old.is_file():
            old.rename(new)

    # Rename current to .1
    backup = log_path.with_suffix(".log.1")
    log_path.rename(backup)

    # Create fresh log
    log_path.touch()

    return {"rotated": True, "old_size_mb": round(size_mb, 1), "backup": str(backup)}
```

**Step 2: Verify import**

Run: `python -c "from miniautogen.cli.services.daemon_ops import daemon_start, daemon_stop, daemon_restart, daemon_status, daemon_logs, rotate_logs; print('OK')"`

**Expected output:**
```
OK
```

---

### Task 32: Create daemon CLI command group

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/commands/daemon.py`

**Prerequisites:**
- Task 31 complete (daemon service exists)

**Step 1: Create the daemon command group**

Create file `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/commands/daemon.py`:

```python
"""miniautogen daemon command group.

First-class daemon lifecycle: start/stop/restart/status/logs.
"""

from __future__ import annotations

import sys
import time

import click

from miniautogen.cli.config import require_project_config
from miniautogen.cli.output import echo_error, echo_info, echo_success, echo_warning


@click.group("daemon")
def daemon_group() -> None:
    """Manage the MiniAutoGen daemon."""


@daemon_group.command("start")
@click.option("--host", default="127.0.0.1", help="Bind address.")
@click.option("--port", type=int, default=8080, help="Bind port.")
def daemon_start_cmd(host: str, port: int) -> None:
    """Start the daemon in background."""
    from miniautogen.cli.services.daemon_ops import daemon_start

    root, _config = require_project_config()

    if host != "127.0.0.1":
        echo_warning(
            f"Binding to {host} exposes the daemon on the network. "
            "Use 127.0.0.1 for local-only access."
        )

    result = daemon_start(root, host=host, port=port)

    if result["status"] == "already_running":
        echo_info(result["message"])
    elif result["status"] == "started":
        echo_success(result["message"])
    else:
        echo_error(f"Unexpected status: {result['status']}")


@daemon_group.command("stop")
def daemon_stop_cmd() -> None:
    """Stop the daemon."""
    from miniautogen.cli.services.daemon_ops import daemon_stop

    root, _config = require_project_config()
    result = daemon_stop(root)

    if result["status"] == "stopped" and result.get("pid"):
        echo_success(result["message"])
    else:
        echo_info(result["message"])


@daemon_group.command("restart")
@click.option("--host", default="127.0.0.1", help="Bind address.")
@click.option("--port", type=int, default=8080, help="Bind port.")
def daemon_restart_cmd(host: str, port: int) -> None:
    """Restart the daemon."""
    from miniautogen.cli.services.daemon_ops import daemon_restart

    root, _config = require_project_config()
    echo_info("Restarting daemon...")
    result = daemon_restart(root, host=host, port=port)

    if result["status"] == "started":
        echo_success(result["message"])
    else:
        echo_error(f"Restart failed: {result.get('message', 'unknown error')}")


@daemon_group.command("status")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def daemon_status_cmd(as_json: bool) -> None:
    """Show daemon status."""
    from miniautogen.cli.services.daemon_ops import daemon_status

    root, _config = require_project_config()
    result = daemon_status(root)

    if as_json:
        from miniautogen.cli.output import echo_json

        echo_json(result)
        return

    status = result["status"]
    if status == "running":
        echo_success(f"Daemon running (PID {result.get('pid', '?')}), port {result.get('port', '?')}")
    elif status == "degraded":
        echo_warning(f"Daemon degraded: {result.get('message', '')}")
    elif status == "unreachable":
        echo_warning(f"Daemon unreachable: {result.get('message', '')}")
    else:
        echo_info("Daemon not running.")

    if result.get("log_file"):
        echo_info(f"Log file: {result['log_file']} ({result.get('log_size_kb', 0)} KB)")


@daemon_group.command("logs")
@click.option("--lines", "-n", type=int, default=50, help="Number of lines to show.")
@click.option("--follow", "-f", is_flag=True, default=False, help="Follow log output (tail -f).")
def daemon_logs_cmd(lines: int, follow: bool) -> None:
    """Show daemon logs."""
    from miniautogen.cli.services.daemon_ops import daemon_logs, daemon_logs_follow

    root, _config = require_project_config()

    if follow:
        log_path = daemon_logs_follow(root)
        if log_path is None:
            echo_info("No log file found. Start the daemon first.")
            return

        echo_info(f"Following {log_path} (Ctrl+C to stop)...")
        try:
            with log_path.open() as f:
                # Skip to end
                f.seek(0, 2)
                while True:
                    line = f.readline()
                    if line:
                        click.echo(line.rstrip("\n"))
                    else:
                        time.sleep(0.2)
        except KeyboardInterrupt:
            echo_info("\nStopped following logs.")
    else:
        output = daemon_logs(root, lines=lines)
        if output:
            click.echo(output)
        else:
            echo_info("No log output available.")
```

**Step 2: Verify import**

Run: `python -c "from miniautogen.cli.commands.daemon import daemon_group; print('OK')"`

**Expected output:**
```
OK
```

---

### Task 33: Register daemon command in CLI

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/main.py`

**Prerequisites:**
- Task 32 complete (daemon command group exists)

**Step 1: Add daemon command registration**

In `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/main.py`, add after the `cli.add_command(status_command)` line (at end of file):

```python

from miniautogen.cli.commands.daemon import daemon_group  # noqa: E402

cli.add_command(daemon_group)
```

**Step 2: Verify CLI registration**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m miniautogen.cli.main daemon --help`

**Expected output:**
```
Usage: main daemon [OPTIONS] COMMAND [ARGS]...

  Manage the MiniAutoGen daemon.

Commands:
  logs     Show daemon logs.
  restart  Restart the daemon.
  start    Start the daemon in background.
  status   Show daemon status.
  stop     Stop the daemon.
```

---

### Task 34: Write tests for daemon service and command

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/test_daemon_ops.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/commands/test_daemon_command.py`

**Prerequisites:**
- Task 33 complete (daemon fully registered)

**Step 1: Create daemon service tests**

Create file `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/test_daemon_ops.py`:

```python
"""Tests for daemon_ops service."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_rotate_logs_no_file(tmp_path):
    """Rotate with no log file returns not rotated."""
    from miniautogen.cli.services.daemon_ops import rotate_logs

    result = rotate_logs(tmp_path)
    assert result["rotated"] is False


def test_rotate_logs_under_threshold(tmp_path):
    """Rotate skips when file is under threshold."""
    from miniautogen.cli.services.daemon_ops import rotate_logs

    log_dir = tmp_path / ".miniautogen"
    log_dir.mkdir()
    log_file = log_dir / "server.log"
    log_file.write_text("small log\n" * 10)

    result = rotate_logs(tmp_path, max_size_mb=1.0)
    assert result["rotated"] is False


def test_rotate_logs_over_threshold(tmp_path):
    """Rotate creates backup when file exceeds threshold."""
    from miniautogen.cli.services.daemon_ops import rotate_logs

    log_dir = tmp_path / ".miniautogen"
    log_dir.mkdir()
    log_file = log_dir / "server.log"
    # Write > 1KB to exceed a low threshold
    log_file.write_text("x" * 2048)

    result = rotate_logs(tmp_path, max_size_mb=0.001)  # 1KB threshold
    assert result["rotated"] is True
    assert (log_dir / "server.log.1").is_file()
    assert log_file.is_file()  # Fresh log created


def test_daemon_status_stopped(tmp_path):
    """Daemon status when no PID file."""
    from miniautogen.cli.services.daemon_ops import daemon_status

    result = daemon_status(tmp_path)
    assert result["status"] == "stopped"
    assert result["log_file"] is None


def test_daemon_logs_no_file(tmp_path):
    """Daemon logs returns message when no log file."""
    from miniautogen.cli.services.daemon_ops import daemon_logs

    result = daemon_logs(tmp_path)
    assert result == "(no log file found)"
```

**Step 2: Create daemon command tests**

Create file `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/commands/test_daemon_command.py`:

```python
"""Tests for miniautogen daemon command group."""

from __future__ import annotations

import os

from click.testing import CliRunner

from miniautogen.cli.main import cli


def test_daemon_help():
    """Daemon group shows help with subcommands."""
    runner = CliRunner()
    result = runner.invoke(cli, ["daemon", "--help"])
    assert result.exit_code == 0
    assert "start" in result.output
    assert "stop" in result.output
    assert "restart" in result.output
    assert "status" in result.output
    assert "logs" in result.output


def test_daemon_status_no_project(tmp_path):
    """Daemon status fails without project config."""
    runner = CliRunner()
    result = runner.invoke(cli, ["daemon", "status"], catch_exceptions=False)
    assert result.exit_code != 0 or "not found" in result.output.lower() or "no project" in result.output.lower() or "error" in result.output.lower()


def test_daemon_status_with_project(tmp_path):
    """Daemon status works with project config."""
    config = "project:\n  name: test\ndefaults:\n  engine: default_api\nengines:\n  default_api:\n    kind: api\n    provider: openai\n    model: gpt-4o\n"
    (tmp_path / "miniautogen.yaml").write_text(config)

    runner = CliRunner()
    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        result = runner.invoke(cli, ["daemon", "status"], catch_exceptions=False)
    finally:
        os.chdir(old_cwd)

    assert result.exit_code == 0
    assert "not running" in result.output.lower() or "stopped" in result.output.lower()


def test_daemon_stop_no_server(tmp_path):
    """Daemon stop when nothing running."""
    config = "project:\n  name: test\ndefaults:\n  engine: default_api\nengines:\n  default_api:\n    kind: api\n    provider: openai\n    model: gpt-4o\n"
    (tmp_path / "miniautogen.yaml").write_text(config)

    runner = CliRunner()
    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        result = runner.invoke(cli, ["daemon", "stop"], catch_exceptions=False)
    finally:
        os.chdir(old_cwd)

    assert result.exit_code == 0
    assert "no server" in result.output.lower() or "not running" in result.output.lower() or "stopped" in result.output.lower()
```

**Step 3: Run tests**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/services/test_daemon_ops.py tests/cli/commands/test_daemon_command.py -v`

**Expected output:**
```
tests/cli/services/test_daemon_ops.py::test_rotate_logs_no_file PASSED
tests/cli/services/test_daemon_ops.py::test_rotate_logs_under_threshold PASSED
tests/cli/services/test_daemon_ops.py::test_rotate_logs_over_threshold PASSED
tests/cli/services/test_daemon_ops.py::test_daemon_status_stopped PASSED
tests/cli/services/test_daemon_ops.py::test_daemon_logs_no_file PASSED
tests/cli/commands/test_daemon_command.py::test_daemon_help PASSED
tests/cli/commands/test_daemon_command.py::test_daemon_status_no_project PASSED
tests/cli/commands/test_daemon_command.py::test_daemon_status_with_project PASSED
tests/cli/commands/test_daemon_command.py::test_daemon_stop_no_server PASSED
```

**Step 4: Commit all G10 work**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/cli/services/daemon_ops.py miniautogen/cli/commands/daemon.py miniautogen/cli/main.py tests/cli/services/test_daemon_ops.py tests/cli/commands/test_daemon_command.py
git commit -m "feat(cli): add daemon command group for first-class daemon lifecycle management"
```

---

### Task 35: Run Code Review (G9+G10 checkpoint)

1. **Dispatch all 3 reviewers in parallel:**
   - REQUIRED SUB-SKILL: Use requesting-code-review
   - All reviewers run simultaneously (code-reviewer, business-logic-reviewer, security-reviewer)
   - Wait for all to complete

2. **Handle findings by severity (MANDATORY):**
   - Critical/High/Medium: Fix immediately
   - Low: Add `TODO(review):` comments
   - Cosmetic: Add `FIXME(nitpick):` comments

3. **Proceed only when zero Critical/High/Medium issues remain**

---

## Final Validation

### Task 36: Run full test suite

**Files:** None (validation only)

**Prerequisites:**
- All previous tasks complete

**Step 1: Run ALL server tests**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/server/ -v --tb=short`

**Expected output:** All tests pass, including the new engine CRUD and global WS tests.

**Step 2: Run ALL CLI tests**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/ -v --tb=short`

**Expected output:** All tests pass, including status and daemon tests.

**Step 3: Run Docker tests**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/docker/ -v --tb=short`

**Expected output:** All Docker validation tests pass.

**Step 4: Verify no regressions in full suite**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest --tb=short -q`

**Expected output:** All existing tests + new tests pass. No regressions.

**If Task Fails:**

1. **Single test failure:**
   - Read the error message carefully
   - Fix the specific failing test or code
   - Re-run only the failing test to verify

2. **Multiple test failures:**
   - Run: `python -m pytest --tb=short -q 2>&1 | tail -20` to see summary
   - Check if failures are in new code or pre-existing
   - Rollback: `git stash` to verify pre-existing failures

3. **Can't recover:**
   - Document what failed and why
   - Return to human partner

---

## Summary of Files Modified/Created

### Backend (Python)
| File | Action | Feature |
|------|--------|---------|
| `miniautogen/server/provider_protocol.py` | Modified | G6 |
| `miniautogen/server/standalone_provider.py` | Modified | G6 |
| `miniautogen/tui/data_provider.py` | Modified | G6 |
| `miniautogen/server/routes/engines.py` | Created | G6 |
| `miniautogen/server/app.py` | Modified | G6, G7 |
| `miniautogen/server/global_ws.py` | Created | G7 |
| `miniautogen/cli/services/status_ops.py` | Created | G8 |
| `miniautogen/cli/commands/status.py` | Created | G8 |
| `miniautogen/cli/services/daemon_ops.py` | Created | G10 |
| `miniautogen/cli/commands/daemon.py` | Created | G10 |
| `miniautogen/cli/main.py` | Modified | G8, G10 |
| `Dockerfile` | Created | G9 |
| `docker-compose.yml` | Created | G9 |
| `.dockerignore` | Created | G9 |

### Frontend (TypeScript/React)
| File | Action | Feature |
|------|--------|---------|
| `console/src/types/api.ts` | Modified | G6 |
| `console/src/lib/api-client.ts` | Modified | G6 |
| `console/src/hooks/useApi.ts` | Modified | G6 |
| `console/src/hooks/useEventStream.ts` | Created | G7 |
| `console/src/components/EngineForm.tsx` | Created | G6 |
| `console/src/app/settings/page.tsx` | Created | G6 |
| `console/src/app/settings/engines/new/page.tsx` | Created | G6 |
| `console/src/app/settings/engines/edit/page.tsx` | Created | G6 |
| `console/src/app/logs/page.tsx` | Created | G7 |
| `console/src/app/layout.tsx` | Modified | G6, G7 |

### Tests
| File | Action | Feature |
|------|--------|---------|
| `tests/server/test_engines_crud.py` | Created | G6 |
| `tests/server/test_global_ws.py` | Created | G7 |
| `tests/cli/services/test_status_ops.py` | Created | G8 |
| `tests/cli/commands/test_status_command.py` | Created | G8 |
| `tests/docker/test_dockerfile.py` | Created | G9 |
| `tests/cli/services/test_daemon_ops.py` | Created | G10 |
| `tests/cli/commands/test_daemon_command.py` | Created | G10 |
