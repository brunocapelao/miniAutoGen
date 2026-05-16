# Plano Técnico: Team Task List (kanban compartilhado entre teammates)

| Campo         | Valor                                  |
|---------------|----------------------------------------|
| Spec ID       | 016                                    |
| Data          | 2026-05-16                             |
| Complexidade  | Large                                  |
| Depende de    | Spec 015 (TeamRuntime entregue)        |

---

## Arquitetura Proposta

### Módulos Afetados

| Módulo / Caminho                                                | Tipo de Alteração     |
|-----------------------------------------------------------------|-----------------------|
| `miniautogen/core/contracts/team_task.py`                       | **Novo**              |
| `miniautogen/core/contracts/store.py`                           | **INTOCADO**          |
| `miniautogen/core/contracts/tool.py`                            | **INTOCADO**          |
| `miniautogen/core/contracts/tool_registry.py`                   | **INTOCADO**          |
| `miniautogen/core/events/types.py`                              | Alterado (+6 EventType)|
| `miniautogen/core/runtime/team_task_list.py`                    | **Novo**              |
| `miniautogen/core/runtime/team_task_tools.py`                   | **Novo** (6 tool defs + handlers) |
| `miniautogen/core/runtime/team_runtime.py`                      | Alterado (spec 015)   |
| `miniautogen/core/runtime/builtin_tools.py`                     | **INTOCADO** (tools de team são módulo separado) |
| `miniautogen/core/runtime/tool_registry.py`                     | **INTOCADO**          |
| `miniautogen/core/runtime/composite_tool_registry.py`           | **INTOCADO** (já compõe) |
| `miniautogen/core/runtime/agent_runtime.py`                     | **INTOCADO** (§3.5 — sem hooks hardcoded) |
| `miniautogen/cli/config.py`                                     | Alterado (TaskListConfig + TaskEntrySpec; validador de ciclos) |
| `miniautogen/adapters/**`                                       | **INTOCADO**          |
| `tests/core/runtime/test_task_list_store_basic.py`              | **Novo**              |
| `tests/core/runtime/test_task_list_claim_race.py`               | **Novo**              |
| `tests/core/runtime/test_task_list_dependencies.py`             | **Novo**              |
| `tests/core/runtime/test_task_list_release_on_cancel.py`        | **Novo**              |
| `tests/core/runtime/test_task_list_filter_by_labels.py`         | **Novo**              |
| `tests/core/runtime/test_task_list_tools.py`                    | **Novo** (6 tools)    |
| `tests/core/runtime/test_team_runtime_with_task_list.py`        | **Novo** (E2E)        |
| `tests/cli/test_config_task_list.py`                            | **Novo** (cycle detection, parsing) |
| `tests/architecture/test_task_list_isolation.py`                | **Novo** (linter de imports) |

### Diagrama de fluxo — claim atômico com 2 teammates competindo

```
              ┌────────────────────────────────────────────────┐
              │  InMemoryTaskListStore (per team_run_id)       │
              │                                                │
              │   _board_lock: anyio.Lock  (1 por board)       │
              │   _tasks: dict[task_id, TaskEntry]             │
              │   _wait_events: dict[task_id, anyio.Event]     │
              └─────────────────┬───────────────┬──────────────┘
                                │               │
            teammate "legal"    │               │   teammate "security"
            (AgentRuntime A)    │               │   (AgentRuntime B)
                                ▼               ▼
                    await store.claim("T-7", "legal")    await store.claim("T-7", "security")
                                │               │
                                ├─acquire lock──┤  (serializado pelo Lock)
                                │               │
                                ▼               │
                        [vencedor]              │
                  check: status == PENDING?  ──►YES
                  check: deps COMPLETED?     ──►YES
                  task.status = IN_PROGRESS    │
                  task.claimed_by = "legal"    │
                  emit TASK_CLAIMED            │
                  release lock                 │
                  return TaskEntry             │
                                                ▼
                                        [perdedor adquire lock]
                                        check: status == PENDING? ──► NO
                                        emit (opcional) TASK_BLOCKED_BY_DEPENDENCY (se deps)
                                        release lock
                                        return None     ────► teammate loop tenta próxima
```

Fluxo de release-em-cancelamento (CancelScope dispara em meio a `claim → execute`):

```
TeamRuntime task group
  ├── teammate "security" loop
  │     async with anyio.CancelScope() as scope:
  │       entry = await store.claim(...)          ◄── adquiriu T-7
  │       try:
  │         await agent_runtime.run(entry)        ◄── ⚡ CANCELLED aqui
  │       finally:                                 ◄── SEMPRE roda no shielded scope
  │         with anyio.CancelScope(shield=True):
  │           await store.release(entry.id)       ◄── T-7 volta para PENDING
  │           emit TASK_RELEASED
  └── (outros teammates seguem)
```

---

## Contratos e Interfaces

### Tipos canônicos (`core/contracts/team_task.py`)

```python
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field
from uuid import uuid4

class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskEntry(BaseModel):
    model_config = {"frozen": False}  # mutável; mutação só dentro do _board_lock
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    description: str | None = None
    assigned_to: str | None = None           # teammate name; None = aberto
    labels: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    created_by: str
    claimed_by: str | None = None
    result_summary: str | None = None
    created_at: datetime
    claimed_at: datetime | None = None
    finished_at: datetime | None = None

class TaskFilter(BaseModel):
    status: TaskStatus | None = None
    assigned_to: str | None = None
    labels: list[str] = Field(default_factory=list)  # ANY-match
```

### `TaskListStore` (satisfaz `StoreProtocol` estrutural)

Para satisfazer `StoreProtocol` (que define `save/get/exists/delete` em `dict[str, Any]`), implementamos esses 4 métodos como wrappers triviais sobre o dicionário interno (`save = upsert do dump`, `get = dump do entry`, etc.), além dos métodos de domínio:

```python
# miniautogen/core/runtime/team_task_list.py
import anyio
from datetime import datetime, timezone

class InMemoryTaskListStore:
    """Per-team-run kanban store. Satisfies StoreProtocol structurally."""

    def __init__(self, team_run_id: str, event_sink: EventSink) -> None:
        self._team_run_id = team_run_id
        self._sink = event_sink
        self._tasks: dict[str, TaskEntry] = {}
        self._board_lock = anyio.Lock()              # 1 por board (ver "Notas")
        self._completion_events: dict[str, anyio.Event] = {}

    # ---- StoreProtocol surface (StoreProtocol contract) ----
    async def save(self, key: str, payload: dict) -> None: ...
    async def get(self, key: str) -> dict | None: ...
    async def exists(self, key: str) -> bool: ...
    async def delete(self, key: str) -> bool: ...

    # ---- Domain API ----
    async def add(self, entry: TaskEntry, *, actor: str) -> str:
        async with self._board_lock:
            self._validate_no_cycle(entry)           # raises ConfigurationError
            self._tasks[entry.id] = entry
            self._completion_events[entry.id] = anyio.Event()
        await self._emit(EventType.TASK_ADDED, entry, actor)
        return entry.id

    async def list(self, filter: TaskFilter | None = None) -> list[TaskEntry]:
        async with self._board_lock:
            return [e.model_copy() for e in self._tasks.values() if _matches(e, filter)]

    async def claim(self, task_id: str | None, teammate: str,
                    labels: list[str] | None = None) -> TaskEntry | None:
        async with self._board_lock:
            entry = self._pick_claimable(task_id, teammate, labels)
            if entry is None:
                return None                          # already claimed / not found
            if not self._deps_satisfied(entry):
                await self._emit(EventType.TASK_BLOCKED_BY_DEPENDENCY, entry, teammate)
                return None
            entry.status = TaskStatus.IN_PROGRESS
            entry.claimed_by = teammate
            entry.claimed_at = datetime.now(timezone.utc)
            claimed = entry.model_copy()
        await self._emit(EventType.TASK_CLAIMED, claimed, teammate)
        return claimed

    async def update_status(self, task_id: str, status: TaskStatus,
                            summary: str | None = None, *, actor: str) -> TaskEntry:
        async with self._board_lock:
            entry = self._tasks[task_id]
            self._validate_transition(entry.status, status)   # idempotent for terminal→terminal same
            if entry.claimed_by != actor and status in {COMPLETED, FAILED}:
                raise StateConsistencyError("only claimer may complete/fail")
            entry.status = status
            entry.result_summary = summary
            entry.finished_at = datetime.now(timezone.utc)
            done = self._completion_events[task_id]
            snapshot = entry.model_copy()
        done.set()                                   # libera waiters de wait_for
        await self._emit(_event_for(status), snapshot, actor)
        return snapshot

    async def release(self, task_id: str, *, actor: str) -> TaskEntry:
        """Devolve IN_PROGRESS → PENDING. Idempotente para tarefa já PENDING."""
        async with self._board_lock:
            entry = self._tasks[task_id]
            if entry.status != TaskStatus.IN_PROGRESS:
                return entry.model_copy()
            entry.status = TaskStatus.PENDING
            entry.claimed_by = None
            entry.claimed_at = None
            snapshot = entry.model_copy()
        await self._emit(EventType.TASK_RELEASED, snapshot, actor)
        return snapshot

    async def wait_for(self, task_id: str, target: TaskStatus,
                       timeout: float | None = None) -> TaskEntry:
        # Loop sobre Event (set por update_status) até match ou timeout
        with anyio.fail_after(timeout):
            while True:
                async with self._board_lock:
                    entry = self._tasks[task_id]
                    if entry.status == target:
                        return entry.model_copy()
                    evt = self._completion_events[task_id]
                await evt.wait()
                # re-cria event se necessidade de re-arm (terminal states já não rearmam)
```

### As 6 tools (`core/runtime/team_task_tools.py`)

Module-level `build_team_task_tools(store, agent_name) -> list[(ToolDefinition, handler)]` que retorna tuplas registráveis em qualquer `ToolRegistryProtocol`. **Não estende `BuiltinToolRegistry`** — usa `InMemoryToolRegistry` + `CompositeToolRegistry` para compor com as tools do agente. Isso evita acoplar `builtin_tools.py` (que precisa de `workspace_root`) a um conceito de team.

```python
# Exemplo de handler — task_claim
async def _handle_task_claim(params: dict) -> ToolResult:
    task_id = params.get("task_id")
    labels = params.get("labels") or []
    entry = await store.claim(task_id, teammate=agent_name, labels=labels)
    if entry is None:
        return ToolResult(success=True, output={"claimed": False})
    return ToolResult(success=True, output={"claimed": True, "task": entry.model_dump(mode="json")})
```

| Tool name        | Params                                                | Retorno                                |
|------------------|-------------------------------------------------------|----------------------------------------|
| `task_add`       | title, description?, assigned_to?, labels?, depends_on? | `{task_id}`                          |
| `task_list`      | status?, assigned_to?, labels?                        | `{tasks: [TaskEntry...]}`              |
| `task_claim`     | task_id?, labels?                                     | `{claimed: bool, task?: TaskEntry}`    |
| `task_complete`  | task_id, summary                                      | `{task: TaskEntry}`                    |
| `task_fail`      | task_id, reason                                       | `{task: TaskEntry}`                    |
| `task_view`      | task_id                                               | `{task: TaskEntry}`                    |

### Novos `EventType`

Em `core/events/types.py`:

```python
# Team task list events (spec 016)
TASK_ADDED = "task_added"
TASK_CLAIMED = "task_claimed"
TASK_COMPLETED = "task_completed"
TASK_FAILED = "task_failed"
TASK_RELEASED = "task_released"
TASK_BLOCKED_BY_DEPENDENCY = "task_blocked_by_dependency"

TEAM_TASK_EVENT_TYPES: set[EventType] = { ... os 6 acima ... }
```

Payload canônico: `{task_id, team_run_id (= parent_run_id), actor, title, status, claimed_by?, depends_on?}`.

### Extensão de `TeamPlan` e `TeamRuntime` (delta sobre spec 015)

**Estende** (não substitui) `TeamPlan` com:

```python
# core/contracts/coordination.py (já tocado pela 015)
class TaskEntrySpec(BaseModel):                       # NOVO nesta spec
    title: str
    description: str | None = None
    assigned_to: str | None = None
    labels: list[str] = []
    depends_on: list[str] = []                        # IDs simbólicos (refs locais ao YAML)
    id: str | None = None                              # opcional; se omitido, gerado

class TaskListConfig(BaseModel):                       # NOVO nesta spec
    enabled: bool = False
    initial_tasks: list[TaskEntrySpec] = []
    idle_threshold_seconds: float = 5.0
    poll_interval_ms: int = 200

class TeamPlan(CoordinationPlan):                      # estende a 015
    # ... campos da 015 ...
    task_list: TaskListConfig | None = None
    lead_runs_first: bool = False                      # default False; vira True implícito se task_list.enabled
```

**Hooks de extensão em `TeamRuntime`** (todos pontos novos; a estrutura base é da 015):

| Função/atributo da 015            | Extensão nesta spec                                                                 |
|-----------------------------------|-------------------------------------------------------------------------------------|
| `TeamRuntime._spawn_teammate()`   | Antes do spawn, compõe `ToolRegistry` via `CompositeToolRegistry([agent_tools, team_task_tools_for(name)])` |
| `TeamRuntime._run_lead()`         | Inverte ordem para "lead antes" quando `plan.task_list.enabled`                     |
| `TeamRuntime._run()` (orquestrador) | Adiciona fase "drain board" via `_run_teammate_loop()` (claim→execute→complete) com idle detection |
| `TeamRuntime._on_teammate_cancel`  | (NOVO callback) chama `store.release()` em `finally shielded`                       |

### Configuração declarativa (`miniautogen/cli/config.py`)

`TeamConfig` (da 015) ganha `task_list: TaskListConfig | None`. `TaskEntrySpec` aceita `depends_on` por **ID simbólico** (string igual ao `id` ou referência sequencial `task[N]`). Validador `@model_validator(mode="after")` em `TeamConfig`:

```python
def _validate_task_dag(self) -> "TeamConfig":
    if not self.task_list or not self.task_list.enabled:
        return self
    ids = {t.id or f"task[{i}]" for i, t in enumerate(self.task_list.initial_tasks)}
    # topological sort via Kahn's algorithm; se sobra dep nó, há ciclo
    if _has_cycle(self.task_list.initial_tasks):
        raise ValueError("task_list.initial_tasks contém ciclo em depends_on")
    return self
```

---

## Riscos e Mitigações

| Risco                                                                          | Impacto | Mitigação                                                                                         |
|--------------------------------------------------------------------------------|---------|---------------------------------------------------------------------------------------------------|
| `anyio.Lock` por board cria contenção quando N teammates competem em massa      | Médio   | Métodos de leitura (`list`, `view`) também tomam lock, mas seções críticas são **O(1)** (dict ops); não há I/O dentro do lock. Emissão de eventos sai do lock (snapshot.model_copy + emit fora). Benchmark: 10 teammates × 100 claims/s permanece sub-ms. Se virar gargalo na spec 018 (SQL store), migra-se para lock-por-task. |
| `release` em cancelamento não roda se `finally` não usar `shield=True`         | Alto    | Padrão obrigatório: `with anyio.CancelScope(shield=True): await store.release(...)`. Coberto por `test_task_list_release_on_cancel.py` com `move_on_after(0.05)` em meio a `agent_runtime.run`. |
| Idle detection (polling 200ms) gera falsos positivos com tarefas longas        | Médio   | `idle = (PENDING=∅) AND (IN_PROGRESS=∅)`, não baseado em "ninguém claimou em X". Threshold só engata após **ambos** zerados continuamente. Documentado como heurística temporária — substituído por `TeammateIdle` hook na spec 017. |
| Ciclo em `depends_on` adicionado em runtime via `task_add`                     | Alto    | `store.add()` chama `_validate_no_cycle()` dentro do lock (DFS com coloração: WHITE/GRAY/BLACK). Rejeição com `ConfigurationError`; tool retorna `ToolResult(success=False, error=...)`. |
| Dois `task_complete` concorrentes na mesma task (raro, mas possível por bug)    | Médio   | `update_status` valida `entry.claimed_by == actor` dentro do lock; segundo caller recebe `StateConsistencyError`. |
| Falha em cascata: A falha → B/C ficam PENDING para sempre                       | Médio   | Comportamento documentado (spec §"Dependência transitiva"). `wait_for` com timeout protege lead. Future: política `dependency_failure: skip|propagate` na spec 018. |
| Vazamento de adapter em `team_task_list.py` (e.g. `from sqlalchemy import ...`) | Alto    | Teste arquitetural `tests/architecture/test_task_list_isolation.py` faz AST scan; falha CI se import de `miniautogen.adapters.*` ou pacotes externos não-stdlib/anyio/pydantic aparecer. |
| `wait_for` deadlock se evento nunca é set (ex: tarefa nunca completa)          | Médio   | API exige `timeout: float | None` (default None aceito para usos do lead, mas docstring orienta usar timeout em chamadas de teammate). E2E test usa `move_on_after`. |
| Lead-runs-first quebra premissa da 015 (lead-depois)                            | Médio   | Coexistência: `lead_runs_first` é override **só** quando `task_list.enabled`. Default da 015 permanece. Teste explícito de ambos os modos no E2E. |

---

## Estimativa de Complexidade

| Aspecto              | Estimativa                                                            |
|----------------------|-----------------------------------------------------------------------|
| Ficheiros novos      | 11 (3 código + 8 testes + 1 arquitetural)                             |
| Ficheiros alterados  | 3 (`events/types.py`, `team_runtime.py`, `cli/config.py`)             |
| Testes novos         | ~25 (store basic 6, race 3, deps 4, cancel 3, labels 2, tools 5, E2E 2) |
| Esforço estimado     | Large (5-7 dias)                                                      |

Drivers de complexidade: race condition correctness, cancellation safety, ciclo dinâmico em DAG, ordem inversa lead-first.

---

## Sequência de Implementação

Test-First. T001–T010 são testes falhando que congelam o contrato antes de qualquer linha de produção.

1. **Test-first arquitetural:** `tests/architecture/test_task_list_isolation.py` — AST scan em `core/runtime/team_task_list.py` e `core/runtime/team_task_tools.py`; lista de imports permitidos é `{stdlib, anyio, pydantic, miniautogen.core.contracts.*, miniautogen.core.events.*}`. Falha se aparecer `miniautogen.adapters.*`, `sqlalchemy`, `redis`, `litellm`, etc.
2. **Test-first:** `tests/core/runtime/test_task_list_store_basic.py` — CRUD: `add → list → claim → update_status → view`. Transições válidas: PENDING→IN_PROGRESS→COMPLETED|FAILED. Inválidas (COMPLETED→IN_PROGRESS): levantam `StateConsistencyError`. `update_status(COMPLETED→COMPLETED)` é idempotente (mesmo summary). `save/get/exists/delete` cumprem `StoreProtocol` (`isinstance(store, StoreProtocol)` é `True` via `runtime_checkable`).
3. **Test-first:** `tests/core/runtime/test_task_list_claim_race.py` — `anyio.create_task_group` lança 10 corrotinas competindo em `claim("T-1")`; exatamente 1 retorna `TaskEntry`, 9 retornam `None`. Repete 50× para estabilidade. Mede também race em `claim(task_id=None, labels=["legal"])` com 2 tasks disponíveis e 5 teammates: cada teammate fica com no máx 1, total claimed = min(N_tasks, N_teammates).
4. **Test-first:** `tests/core/runtime/test_task_list_dependencies.py` —
   - A→B→C: `claim(B)` retorna `None` enquanto A é PENDING; emite `TASK_BLOCKED_BY_DEPENDENCY`.
   - Completar A → `claim(B)` agora sucede.
   - Falhar A → B e C permanecem PENDING indefinidamente (test usa `move_on_after(0.5)` em `wait_for(B, COMPLETED)` e espera `TimeoutError`).
   - **Ciclo estático:** `TeamConfig.model_validate({...A→B→A...})` levanta `ValidationError`.
   - **Ciclo dinâmico:** `store.add(TaskEntry(depends_on=[existing_id_that_depends_on_new]))` levanta `ConfigurationError`.
5. **Test-first:** `tests/core/runtime/test_task_list_release_on_cancel.py` — teammate dentro de `anyio.move_on_after(0.05)` faz claim e dorme 1s; após cancelamento, a tarefa volta a PENDING e evento `TASK_RELEASED` é emitido. Outro teammate consegue fazer claim na sequência.
6. **Test-first:** `tests/core/runtime/test_task_list_filter_by_labels.py` — `claim(labels=["legal"])` ignora tarefa com `labels=["security"]` mesmo se ela for a única PENDING; retorna `None`.
7. **Test-first:** `tests/core/runtime/test_task_list_tools.py` — instancia `InMemoryToolRegistry`, registra as 6 tools via `build_team_task_tools(store, "alice")`, executa cada uma via `registry.execute_tool(ToolCall(...))` e verifica `ToolResult.success` + shape do output. Inclui caso de `task_complete` por agente não-claimer → `success=False`.
8. **Test-first:** `tests/cli/test_config_task_list.py` — parse YAML com `task_list.initial_tasks` (DAG válido + DAG cíclico); confirma `WorkspaceConfig.flows`/`teams` carregam.
9. **Test-first E2E:** `tests/core/runtime/test_team_runtime_with_task_list.py` — fixture com 1 lead (cria 5 tarefas via `task_add` no system prompt mockado) + 3 teammates (loop `task_claim → echo summary → task_complete`); ao fim: todas COMPLETED, event log canônico (`TEAM_STARTED → 5×TASK_ADDED → ≥5×TASK_CLAIMED → 5×TASK_COMPLETED → TEAM_FINISHED`), ordem causal preservada por `parent_run_id` + `timestamp`.
10. **Test-first cancel propagation E2E:** mesmo cenário do (9) mas cancela o team via `CancelScope` no meio: tarefas IN_PROGRESS viram PENDING (release), TEAM_FAILED não emite se política for `isolate`.
11. **Implementação:** `core/contracts/team_task.py` — `TaskStatus`, `TaskEntry`, `TaskFilter`, `TaskEntrySpec`, `TaskListConfig` (Pydantic puro, zero IO).
12. **Implementação:** `core/events/types.py` — adicionar 6 EventTypes + set `TEAM_TASK_EVENT_TYPES`.
13. **Implementação:** `core/runtime/team_task_list.py` — `InMemoryTaskListStore` com `_board_lock`, `_completion_events`, DFS de detecção de ciclo, validação de transições, helpers `_emit/_matches/_deps_satisfied`.
14. **Implementação:** `core/runtime/team_task_tools.py` — `build_team_task_tools(store, agent_name) -> list[(ToolDefinition, handler)]`; handlers fechados sobre `(store, agent_name)`.
15. **Implementação:** `core/runtime/team_runtime.py` (estende 015) — `_drain_board_loop(teammate, store, idle_threshold, poll_ms)` com `try/finally shielded release`; método `_compose_teammate_registry(base_registry, store, name)` via `CompositeToolRegistry`. Lead-first flag respeitada.
16. **Implementação:** `cli/config.py` — `TaskListConfig`, `TaskEntrySpec`, `_has_cycle()`, `@model_validator` em `TeamConfig`.
17. **Validação:** `skills/run_anyio_tests.sh` verde. `ruff` + `mypy` clean.
18. **Smoke E2E manual:** `miniautogen run review_team` com workspace de exemplo (5 tasks, 3 teammates LLM mockados); confirma log unificado mostra claim/complete sequenciados.

---

## Notas

- **Por que `anyio.Lock` por board e não por task?** Granularidade por task pareceria mais paralela, mas operações que precisam atomicidade — `claim(task_id=None, labels=...)` que itera o board, `_validate_no_cycle()` que percorre o grafo, listagem filtrada — exigiriam "lock-of-locks" e abrem porta a deadlock por ordem inconsistente. Lock por board com seções críticas O(1)–O(N tasks) (centenas, não milhares) tem latência sub-ms e zero risco de deadlock. **Quando migrar:** quando o board persistente (spec 018+) crescer para 10⁴+ tasks, troca-se por estratégia otimista (CAS via versão monotônica) sem mudar a API pública.

- **Por que `claim` retorna `None` em vez de levantar exceção?** É caminho quente (teammates fazem polling). Levantar exceção polui logs e força try/except em todos os call sites. `None` é semanticamente "no work for you right now"; o teammate loop interpreta como "esperar/sair se idle threshold".

- **`release` é idempotente** para tarefa já PENDING (no-op silencioso). Isso protege cenários de re-cancelamento (dupla propagação de `CancelScope` aninhados).

- **`wait_for` usa `anyio.Event` por task** (não `Condition`) porque cada task tem 1 transição terminal observável; após `set()`, qualquer waiter pendente acorda. Re-arm não é necessário pois COMPLETED/FAILED são terminais.

- **Idle detection (5s default) é temporária.** Documentado em docstring de `TaskListConfig.idle_threshold_seconds` e na spec 017 que substitui pelo hook `TeammateIdle` canônico (considera board + mailbox + N agentes humanos pendentes).

- **§3.5 CLAUDE.md preservado:** `AgentRuntime` permanece intocado. Comportamento "consuma a task list" vem do **prompt do agente** + tools disponíveis no registry. O `_drain_board_loop` do `TeamRuntime` só invoca o agent; não injeta instruções textuais.

- **Future Work explícito:** (a) `SqlAlchemyTaskListStore` para retomada cross-process (spec 018); (b) `next_available(labels)` push-based (substitui polling do teammate loop, sem mudar correctness); (c) `priority: int` em `TaskEntry` (claim retorna prioridade mais alta primeiro) — trivial mas deixado fora para manter MVP mínimo; (d) hook `TaskCreated`/`TaskCompleted` para policies reativas (spec 017).
