# MiniAutoGen Console — Web Dashboard de Observabilidade e Controlo

**Status:** Aprovado
**Data:** 2026-03-22
**Autores:** Arquitectura MiniAutoGen

---

## 1. Resumo Executivo

Substituicao total da TUI (Textual) por uma aplicacao web moderna — o **MiniAutoGen Console**. A TUI sera depreciada e removida.

A solucao propoe um backend FastAPI (thin wrapper sobre o `DashDataProvider` existente) e um frontend Next.js compilado para ficheiros estaticos, servido pelo proprio FastAPI. Comunicacao via REST (read-only + run trigger) e WebSocket (streaming de eventos em tempo real).

### Decisoes Chave

| Decisao | Escolha | Racional |
|---------|---------|----------|
| TUI vs Web | Substituicao total | TUI sera depreciada e removida |
| Deployment | Hibrido | `--console` embebido + `console` standalone |
| Frontend stack | Next.js static export | DX rica, zero Node.js para o utilizador final |
| Time-travel | Replay visual (grafo animado) | Impacto alto, complexidade gerivel |
| Scope Sprint 1 | Read-only + Run trigger | Observabilidade + interaccao, sem CRUD de config |
| Backend approach | Thin HTTP Wrapper sobre DashDataProvider | Reutiliza logica existente, zero mudancas no core |
| Terminologia | "flow" (API) = "pipeline" (core) | Termo user-facing mais intuitivo; traducao na camada REST |

---

## 2. Arquitectura Geral

O MiniAutoGen Console e composto por dois artefactos:

**Console Server** (`miniautogen/server/`) — FastAPI app que expoe o `DashDataProvider` via REST + WebSocket. Servido como parte do pacote Python.

**Console Web** (`console/`) — Next.js app compilada para ficheiros estaticos (`console/out/`), embebida no pacote Python e servida pelo FastAPI via `StaticFiles`.

```
+-----------------------------------------------------+
|  Browser                                            |
|  Next.js Static App (React + React Flow + Zustand)  |
|    GET /api/v1/*  <->  REST (read-only + run trigger)|
|    WS  /ws/runs/* <->  Event stream (live)          |
+-----------------------------------------------------+
                         |
+-----------------------------------------------------+
|  FastAPI (Console Server)                           |
|  +- REST Router (/api/v1/*)                         |
|  +- WebSocket Handler (/ws/runs/{run_id})           |
|  +- StaticFiles mount (/) -> console/out/           |
|  +- WebSocketEventSink (implements EventSink)       |
|         |                                           |
|  DashDataProvider                                   |
|  +- agent_ops  -> WorkspaceConfig (YAML)            |
|  +- pipeline_ops -> PipelineRunner                  |
|  +- event_ops  -> EventStore / RunStore             |
+-----------------------------------------------------+
                         |
+-----------------------------------------------------+
|  MiniAutoGen Core (unchanged)                       |
|  PipelineRunner -> EventSink -> ExecutionEvent stream|
|  Stores (SQLite/Postgres) -> Event/Run/Checkpoint   |
+-----------------------------------------------------+
```

### Dois Modos de Operacao

**Embebido** (`miniautogen run meu-flow --console`) — Sprint 1:
- FastAPI + PipelineRunner no mesmo processo
- WebSocketEventSink recebe eventos em memoria
- Abre browser automaticamente
- Servidor mantem-se activo apos o run para inspeccao

**Standalone** (`miniautogen console`) — Sprint 2:
- Apenas FastAPI (sem PipelineRunner)
- Requer extensao do `DashDataProvider` com metodos store-backed (actualmente in-memory)
- Novos metodos: `query_events_from_store(run_id, offset, limit)`, `query_runs_from_store(offset, limit)`
- Polling de eventos para runs activos de outros processos
- Util para equipas observarem runs remotos

**Nota:** O `DashDataProvider` actual armazena eventos e runs em memoria (`self._events`, `self._run_history`). O modo standalone requer acesso ao `EventStore`/`RunStore` persistentes. Esta extensao e scope do Sprint 2, nao do Sprint 1. O Sprint 1 foca exclusivamente no modo embebido.

---

## 3. Especificacao da API

### 3.1. REST Endpoints (`/api/v1`)

Todos read-only excepto `POST /runs` e `POST /runs/{run_id}/approvals/{request_id}`.

| Metodo | Endpoint | Descricao | Response Model |
|--------|----------|-----------|----------------|
| `GET` | `/workspace` | Config actual do workspace | `WorkspaceConfig` (projectado) |
| `GET` | `/agents` | Lista agentes definidos no YAML | `List[AgentSummary]` |
| `GET` | `/agents/{name}` | Detalhe de um agente (5 camadas) | `AgentDetail` |
| `GET` | `/flows` | Lista flows disponiveis | `List[FlowSummary]` |
| `GET` | `/flows/{name}` | Detalhe de um flow (plano visual) | `FlowDetail` |
| `POST` | `/runs` | Dispara execucao de um flow | Request: `RunRequest`, Response: `{ run_id: str }` |
| `GET` | `/runs` | Lista runs (paginado) | `Page[RunSummary]` |
| `GET` | `/runs/{id}` | Detalhe de um run | `RunDetail` |
| `GET` | `/runs/{id}/events` | Eventos de um run (paginado) | `Page[ExecutionEvent]` |
| `GET` | `/runs/{id}/approvals` | Lista approvals pendentes de um run | `List[PendingApproval]` |
| `POST` | `/runs/{run_id}/approvals/{request_id}` | Resolve um ApprovalGate especifico | Request: `ApprovalDecision` |

**Request/Response Models:**

```python
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
    code: str  # machine-readable: "flow_not_found", "run_not_found", "approval_already_resolved"
```

**Error Handling:**

| Situacao | Status Code | Error Code |
|----------|-------------|------------|
| Flow nao encontrado em `POST /runs` | 404 | `flow_not_found` |
| Run nao encontrado | 404 | `run_not_found` |
| Approval ja resolvido | 409 | `approval_already_resolved` |
| Request body invalido | 422 | `validation_error` |
| PipelineRunner ocupado | 503 | `runner_busy` |

**Nota sobre ApprovalChannel:** O Console Server mantem referencia ao `InMemoryApprovalChannel` ou `CallbackApprovalChannel` injectado no PipelineRunner. O endpoint `POST /approvals/{request_id}` chama `handle.resolve(decision, reason)` no handle correspondente. No modo standalone (Sprint 2), sera necessario um `WebConsoleApprovalChannel` que persiste handles no store.

### 3.2. Projeccoes Pydantic

O `DashDataProvider` retorna objectos completos. Os response models filtram campos:

```python
class AgentSummary(BaseModel):
    name: str
    role: str
    engine_type: str
    status: str  # "idle" | "running" | "error"

class AgentDetail(AgentSummary):
    identity: IdentityConfig
    engine: EngineConfig
    runtime: RuntimeConfig
    skills: list[SkillRef]
    tools: ToolAccessConfig
```

### 3.3. Paginacao

```python
class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    offset: int
    limit: int
```

### 3.4. WebSocket (`/ws/runs/{run_id}`)

Canal unidireccional (server -> client) para streaming de eventos.

**Protocolo:**
1. Cliente conecta a `/ws/runs/{run_id}`
2. Servidor envia `{"type": "connected", "run_id": "..."}`
3. Eventos `ExecutionEvent` em JSON a medida que o PipelineRunner os emite
4. `{"type": "finished"}` quando o run termina
5. Cliente pode enviar `{"type": "ping"}` para keepalive

**WebSocketEventSink** — Implementa `EventSink`:

```python
class WebSocketEventSink(EventSink):
    """Multiplexa eventos para N conexoes WebSocket activas."""

    async def publish(self, event: ExecutionEvent) -> None:
        message = event.model_dump_json()
        if event.run_id is None:
            # Eventos sem run_id (system-level) sao descartados no WebSocket.
            # Decisao de design: estes eventos sao persistidos pelo store sink
            # (via CompositeEventSink) mas nao sao relevantes para clientes WS
            # que subscrevem a um run_id especifico.
            return
        for ws in self._connections.get(event.run_id, []):
            await ws.send_text(message)
```

**Eventos com `run_id=None`:** Eventos system-level (sem run_id) nao sao enviados via WebSocket. Sao persistidos pelo store sink (via `CompositeEventSink`) e podem ser consultados via `GET /runs/{id}/events`. Esta e uma decisao de design explicita — clientes WebSocket subscrevem a runs especificos.

**Modo standalone (fallback — Sprint 2):** Frontend faz polling de `GET /runs/{id}/events?offset=last_seen` a cada 1s. O hook `useRunEvents` abstrai esta dualidade.

---

## 4. Frontend (Console Web)

### 4.1. Stack Tecnologica

| Tecnologia | Papel |
|-----------|-------|
| Next.js 14+ (App Router, static export) | Framework, routing. `output: 'export'` em `next.config.js` |
| TypeScript | Type safety alinhada com Pydantic |
| Tailwind CSS + Shadcn/UI | Estilizacao + componentes acessiveis |
| React Flow | Visualizacao de grafos (flows, runs) |
| TanStack Query | Cache de dados REST |
| Zustand | Estado de UI local (WS, slider, filtros) |
| openapi-typescript | Geracao automatica de tipos a partir do OpenAPI |

**Restricoes do Static Export:** Com `output: 'export'`, o Next.js gera ficheiros HTML/CSS/JS puros. Isto implica:
- Todas as paginas com dados dinamicos usam `'use client'` directive
- Todo data fetching e client-side (TanStack Query para FastAPI)
- Nao ha Next.js API routes — toda a API e servida pelo FastAPI
- Nao ha Server Components com data fetching dinamico
- Nao ha middleware Next.js (auth, redirects, etc.)

### 4.2. Estrutura do Projecto

```
console/
+-- src/
|   +-- app/                      # App Router
|   |   +-- layout.tsx            # Shell: sidebar + header
|   |   +-- page.tsx              # Dashboard (/)
|   |   +-- agents/page.tsx       # Lista agentes
|   |   +-- flows/
|   |   |   +-- page.tsx          # Lista flows
|   |   |   +-- [name]/page.tsx   # Detalhe flow + grafo
|   |   +-- runs/
|   |       +-- page.tsx          # Lista runs
|   |       +-- [id]/page.tsx     # Detalhe run + live view
|   +-- components/
|   |   +-- flow-graph/           # React Flow wrapper
|   |   |   +-- FlowCanvas.tsx
|   |   |   +-- AgentNode.tsx
|   |   |   +-- EdgeAnimated.tsx
|   |   +-- run/
|   |   |   +-- EventFeed.tsx     # Lista de eventos (logs)
|   |   |   +-- TimeSlider.tsx    # Slider de time-travel
|   |   |   +-- RunStatus.tsx
|   |   +-- approval/
|   |   |   +-- ApprovalModal.tsx
|   |   +-- ui/                   # Shadcn components
|   +-- hooks/
|   |   +-- useRunEvents.ts       # WS + polling fallback
|   |   +-- useApi.ts             # TanStack Query wrappers
|   |   +-- useTimeTravel.ts
|   +-- lib/
|   |   +-- api-client.ts         # Fetch wrapper typed
|   |   +-- ws-client.ts          # WebSocket manager
|   +-- stores/
|   |   +-- connection.ts         # Zustand: WS state
|   +-- types/
|       +-- generated.ts          # openapi-typescript output
+-- out/                          # Build estatico -> embebido no Python
```

### 4.3. Paginas Principais

**Dashboard (`/`):**
- Contagem de agentes, flows, runs recentes
- Lista de runs activos com status live (WS)
- Botao "Run Flow" -> selector de flow -> `POST /runs`

**Flows (`/flows/[name]`):**
- React Flow renderiza o plano (WorkflowPlan = sequencia linear, DeliberationPlan = estrela)
- Nos customizados `AgentNode` com nome, role, engine type
- Read-only (sem edicao)

**Run Detail (`/runs/[id]`)** — Tres paineis:

```
+--------------------------------------------------+
|  Header: Run #abc | RUNNING | 12.3s | Flow X     |
+------------------------+-------------------------+
|                        |  Event Feed             |
|  Flow Graph            |  +-------------------+  |
|  (React Flow)          |  | 12:01 STARTED     |  |
|                        |  | 12:02 Agent A >   |  |
|  [A] --> [B] --> [C]   |  | 12:03 Agent A OK  |  |
|   OK      >>      .    |  | 12:04 Agent B >   |  |
|                        |  +-------------------+  |
+------------------------+-------------------------+
|  <==============*==========================>      |
|  Time Slider            t=12:03                   |
+--------------------------------------------------+
```

- **Grafo:** Nos colorem em tempo real (cinza=pendente, amarelo=running, verde=success, vermelho=error)
- **Event Feed:** Log cronologico filtravel por categoria (Lifecycle, Backend, Tool, Error)
- **Time Slider:** Arrasta para re-colorir o grafo e sincronizar o feed ao momento `t`
- **Approval Modal:** Aparece automaticamente em evento `APPROVAL_REQUESTED`

### 4.4. Gestao de Estado

| Camada | Ferramenta | Responsabilidade |
|--------|-----------|-----------------|
| Server state (REST) | TanStack Query | Cache, revalidacao, paginacao |
| Real-time events | `useRunEvents` hook | WS + polling fallback |
| UI state | Zustand | Conexao WS, slider position, filtros |
| Time-travel | `useTimeTravel` hook | Indice `t`, eventos filtrados ate `t` |

O `useRunEvents` abstrai a dualidade WS/polling:

```typescript
function useRunEvents(runId: string) {
  // Tenta WebSocket primeiro
  // Se falhar ou modo standalone -> fallback polling
  // GET /runs/{id}/events?offset=lastSeen a cada 1s
  // Retorna: events[], isLive, connectionStatus
}
```

### 4.5. Build e Distribuicao

```bash
# No CI/CD ou durante o build do pacote:
cd console && npm run build   # next build -> gera console/out/
```

**Empacotamento no Poetry:**

O projecto usa Poetry (`poetry-core`) como build backend. A inclusao de assets estaticos (HTML/CSS/JS) num pacote Python requer um passo de build previo:

```bash
# 1. Build do frontend (gera console/out/)
cd console && npm run build

# 2. Copiar estaticos para dentro do pacote Python
cp -r console/out/ miniautogen/server/static/

# 3. Build do pacote Python (inclui os estaticos copiados)
poetry build
```

No `pyproject.toml`:

```toml
[tool.poetry]
packages = [
    { include = "miniautogen" },
]
```

O directorio `miniautogen/server/static/` e incluido automaticamente pelo Poetry por estar dentro do pacote `miniautogen`. A copia de `console/out/` para este directorio deve ser automatizada via script de CI/CD ou Makefile.

**Nota:** A implementacao exacta do empacotamento (Makefile, pre-build hook, ou CI step) e uma tarefa de infraestrutura do Sprint 1.

---

## 5. Integracao CLI

### 5.1. Novos Comandos

**Modo embebido:**
```bash
miniautogen run meu-flow --console [--port 8080]
```
- FastAPI + PipelineRunner no mesmo processo
- Abre browser automaticamente
- Servidor mantem-se activo apos o run para inspeccao
- `Ctrl+C` encerra tudo

**Modo standalone:**
```bash
miniautogen console [--port 8080] [--workspace ./path]
```
- Apenas FastAPI, sem PipelineRunner
- Le `miniautogen.yaml` para listar agentes/flows
- Acede aos Stores para runs passados
- Activo ate `Ctrl+C`

### 5.2. Implementacao

```python
# miniautogen/server/app.py

def create_app(workspace_path: str, mode: Literal["embedded", "standalone"]) -> FastAPI:
    app = FastAPI(title="MiniAutoGen Console")

    provider = DashDataProvider(workspace_path)

    # REST routes
    app.include_router(workspace_router(provider))
    app.include_router(agents_router(provider))
    app.include_router(flows_router(provider))
    app.include_router(runs_router(provider))

    # WebSocket (only in embedded mode)
    if mode == "embedded":
        app.include_router(ws_router())

    # Static files (Next.js build)
    static_dir = Path(__file__).parent / "static"
    app.mount("/", StaticFiles(directory=static_dir, html=True))

    # CORS: apenas necessario em Development Mode (next dev em localhost:3000).
    # Em producao (static export servido pelo FastAPI), a origem e a mesma
    # (localhost:8080), logo CORS nao se aplica. O middleware deve ser
    # condicionalmente activado apenas quando DEBUG=true ou via flag.
    if os.getenv("MINIAUTOGEN_DEV"):
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[
                "http://localhost:3000",   # Next.js dev server
                "http://127.0.0.1:3000",
            ],
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
        )

    return app
```

---

## 6. Seguranca

| Aspecto | Abordagem |
|---------|-----------|
| Bind | `127.0.0.1` (nunca `0.0.0.0`) |
| CORS | Dev only (`MINIAUTOGEN_DEV`): `localhost:3000`, `127.0.0.1:3000`. Producao: same-origin, CORS desactivado |
| Secrets | `api_key` e `credentials` mascarados (`****`) nas projeccoes Pydantic |
| Auth | Nenhuma (fase inicial, ferramenta local) |
| Futura | Auth quando/se houver deployment remoto |

---

## 7. Plano de Sprints

### Sprint 1: Fundacao e Observabilidade (Modo Embebido)
- **Backend:** `create_app`, REST routes (GET), `POST /runs`, `POST /runs/{run_id}/approvals/{request_id}`
- **Backend:** `WebSocketEventSink` implementando `EventSink` (com `CompositeEventSink`)
- **Backend:** Error response models e status codes
- **Frontend:** Setup Next.js + Shadcn/UI, paginas de lista (Dashboard, Agents, Flows, Runs)
- **CLI:** `miniautogen run --console` (modo embebido apenas)
- **Entregavel:** Dashboard funcional com listagem + run trigger + logs + approvals

### Sprint 2: Standalone + Visualizacao
- **Backend:** Extensao do `DashDataProvider` com metodos store-backed
- **Backend:** `miniautogen console` (modo standalone)
- **Frontend:** React Flow para visualizacao de FlowPlans
- **Frontend:** Run Detail page com grafo live + event feed
- **Frontend:** WebSocket integration + polling fallback (`useRunEvents`)
- **Frontend:** Approval Modal
- **Entregavel:** Runs visiveis em tempo real + modo standalone funcional

### Sprint 3: Time-Travel e Polish
- **Frontend:** Time Slider com replay visual no grafo (replay de events[0..t] com debounce de 100ms para runs >1000 eventos)
- **Frontend:** Filtros avancados no Event Feed
- **Frontend:** Dark mode, responsive tweaks
- **Backend:** Optimizacao de queries paginadas nos Stores
- **Entregavel:** Produto polido com time-travel debugging

---

## 8. Fora de Scope (Futuro)

- CRUD de agentes/flows via UI (requer edicao programatica de YAML)
- Reconstrucao completa de estado (snapshot viewer) no time-travel
- Autenticacao e deployment remoto
- Multi-workspace no mesmo servidor
- Comparacao visual entre runs
- `WebConsoleApprovalChannel` para modo standalone (persistencia de handles no store)
- Suporte a multiplos runs simultaneos no WebSocket (broadcast global channel)
