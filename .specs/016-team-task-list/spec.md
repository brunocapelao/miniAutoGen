# Especificação: Team Task List — kanban compartilhado entre teammates

| Campo      | Valor                          |
|------------|--------------------------------|
| Data       | 2026-05-16                     |
| Autor      | Bruno Capelão                  |
| Status     | Rascunho                       |
| Spec ID    | 016                            |
| Depende de | Spec 015 (TeamRuntime)         |

---

## Contrato de Prompt (G/C/FC)

### 🎯 Goal (Objetivo)

Introduzir uma **task list compartilhada** entre lead e teammates de um `TeamRuntime`, espelhando o kanban de Claude Code Agent Teams. Lead pode atribuir tarefas explícitas; teammates podem fazer **claim** (pull) de tarefas disponíveis ou criar subtarefas. Estado canônico: `pending → in_progress → completed | failed`. Dependências entre tarefas são respeitadas (uma tarefa só fica disponível para claim quando todas as dependências estão `completed`).

Isto transforma o `TeamRuntime` de "fan-out estático" (spec 015) em "fan-out dinâmico com delegação ativa": lead pode agora rodar **antes** dos teammates, popular o board, e os teammates consomem por iniciativa própria.

**Não-objetivo deste ciclo:**
- Comunicação direta entre teammates → spec 017.
- Plan approval por tarefa → spec 017.
- Hooks `TeammateIdle` (idle implica board vazio + inbox vazio → exige mailbox) → spec 017.
- Persistência cross-process da task list (DB-backed) — v1 é in-memory por team run. SQL-backed store é fase 2.

### 🚧 Constraint (Restrição)

1. **`TaskListStore` é um `StoreProtocol`.** Implementa a interface canônica de `core/contracts/store.py`; nenhuma API paralela de persistência é introduzida.
2. **Isolamento de Adapters.** Implementação default `InMemoryTaskListStore` em `core/runtime/team_task_list.py`; nenhuma referência a SQLAlchemy, Redis etc. neste módulo.
3. **Race conditions via AnyIO.** Operações `claim`/`update_status` são serializadas via `anyio.Lock` por task ou por board (a definir no plano). Zero `threading.*`.
4. **Tools são padrão.** Teammates ganham acesso à task list via `ToolProtocol`s registradas em `BuiltinToolRegistry` (`task_list`, `task_claim`, `task_complete`, `task_fail`, `task_add`, `task_view`). Nenhum hook hardcoded no `AgentRuntime`.
5. **Eventos canônicos.** Cada operação emite `ExecutionEvent` (`TASK_ADDED`, `TASK_CLAIMED`, `TASK_COMPLETED`, `TASK_FAILED`, `TASK_BLOCKED_BY_DEPENDENCY`).
6. **Sem prompts hardcoded.** Per §3.5 CLAUDE.md, o `AgentRuntime` não ganha lógica que diga "consuma a task list" — isso é responsabilidade do prompt do agente (system prompt define o comportamento).

### 🛑 Failure Condition (Condição de Falha)

A implementação **falhou** se, ao fim do ciclo, qualquer um for verdadeiro:

1. Dois teammates conseguem fazer `claim` da mesma tarefa em paralelo (race condition); o segundo deveria receber erro/None.
2. Uma tarefa `B` com `depends_on=[A]` pode ser `claim`ed antes de `A` estar `completed`.
3. Cancelamento de um teammate que detinha uma tarefa em `in_progress` **não devolve** a tarefa para `pending` ou marca como `failed` — vazamento de estado.
4. Algum `task_*` tool importa de `miniautogen/adapters/` ou bypassa o `StoreProtocol`.
5. `pytest tests/core/runtime/test_team_task_list.py` ou cobertura do módulo < 85%.
6. Fluxo E2E: lead cria 5 tarefas, 3 teammates consomem em paralelo, todas terminam — não produz event log determinístico que reconstrua "quem fez o quê".

---

## User Stories

- Como **engenheiro de IA**, quero que o lead do meu time decomponha o briefing em 5 tarefas independentes e que os 3 teammates consumam essas tarefas em paralelo, sem eu codar a coordenação — quero apenas declarar o time no YAML e prompt do lead.
- Como **teammate especializado** (e.g. data scientist), quero poder pular tarefas que não são minha expertise (filtro por label/role) e claim apenas as que cabem a mim — para não ser engargalado.
- Como **operador**, quero ver no log de eventos quem fez claim de qual tarefa e em que ordem, para auditoria — sem ter que inferir de timestamps.
- Como **autor de spec**, quero que uma tarefa que falha NÃO bloqueie tarefas que não dependem dela — falhas isoladas, não em cascata.

---

## Critérios de Aceitação

### Contratos novos

- [ ] `TaskStatus(str, Enum)`: `PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`, `CANCELLED`.
- [ ] `TaskEntry(BaseModel)`:
  - `id: str` (UUID4)
  - `title: str`
  - `description: str | None`
  - `assigned_to: str | None` — teammate name (None = qualquer um pode pegar)
  - `labels: list[str]` — filtros opcionais (e.g. `["legal", "high-priority"]`)
  - `depends_on: list[str]` — IDs de tarefas que devem estar `COMPLETED`
  - `status: TaskStatus`
  - `created_by: str` — nome do agente que criou
  - `claimed_by: str | None`
  - `result_summary: str | None` — preenchido em `complete`/`fail`
  - `created_at`, `claimed_at`, `finished_at: datetime | None`
- [ ] `TaskListStore(StoreProtocol)`:
  - `async add(entry: TaskEntry) -> str`
  - `async list(filter: TaskFilter | None) -> list[TaskEntry]`
  - `async claim(task_id: str, teammate: str) -> TaskEntry | None` (atomic; None se já claimed ou bloqueada por deps)
  - `async update_status(task_id: str, status: TaskStatus, summary: str | None = None) -> TaskEntry`
  - `async release(task_id: str) -> TaskEntry` — devolve tarefa `IN_PROGRESS` para `PENDING` (e.g. em cancelamento)
  - `async wait_for(task_id: str, target_status: TaskStatus, timeout: float | None = None) -> TaskEntry` — usado pelo lead para aguardar conclusão

### Tools registradas em `BuiltinToolRegistry`

- [ ] `task_add(title, description?, assigned_to?, labels?, depends_on?) -> task_id` (lead e teammates podem criar)
- [ ] `task_list(status?, assigned_to?, labels?) -> list[TaskEntry]`
- [ ] `task_claim(task_id?, labels?) -> TaskEntry | None` — se `task_id` vazio, claim a primeira `PENDING` que matche `labels`
- [ ] `task_complete(task_id, summary)` — só funciona se quem chama é `claimed_by`
- [ ] `task_fail(task_id, reason)` — idem
- [ ] `task_view(task_id) -> TaskEntry`

### Integração com `TeamRuntime` (estende spec 015)

- [ ] `TeamPlan` ganha campo opcional `task_list: TaskListConfig | None`:
  - `enabled: bool = False`
  - `initial_tasks: list[TaskEntrySpec] = []` — populadas no boot do team
  - `lead_runs_first: bool = True` — quando `task_list.enabled`, lead roda **antes** dos teammates (override do default v1 da spec 015)
- [ ] Quando `task_list.enabled`, `TeamRuntime` injeta um `TaskListStore` per-team-run e registra as 6 tools acima no `ToolRegistry` de cada teammate + lead.
- [ ] Teammates ficam em loop "claim → execute → complete/fail" até o board ficar vazio ou todos `task_list({status: PENDING})` ficarem `[]` por N segundos (idle threshold configurável; default 5s).
- [ ] Cancelamento de teammate com tarefa em `IN_PROGRESS` → `release(task_id)` automático.

### Novos `EventType`

- [ ] `TASK_ADDED`, `TASK_CLAIMED`, `TASK_COMPLETED`, `TASK_FAILED`, `TASK_RELEASED`, `TASK_BLOCKED_BY_DEPENDENCY`.
- [ ] Payload de cada evento inclui `task_id`, `team_run_id` (= `parent_run_id`), `actor` (teammate ou lead).

### Concorrência e correctness

- [ ] `claim` é atômico: dois teammates chamando `claim(task_id="abc")` simultaneamente → exatamente 1 recebe o `TaskEntry`, o outro recebe `None`. Teste com `anyio.create_task_group` + N teammates competindo.
- [ ] Dependências: tarefa `B` com `depends_on=[A]` aparece em `task_list(status=PENDING)` mas `claim(B)` retorna `None` até `A` estar `COMPLETED`. Emite `TASK_BLOCKED_BY_DEPENDENCY`.
- [ ] Dependência transitiva: A → B → C. Completar A libera B; completar B libera C; falhar A bloqueia B e C (que ficam em `PENDING` para sempre — comportamento documentado, não erro).

### Configuração declarativa

- [ ] `miniautogen.yaml` ganha:
  ```yaml
  teams:
    review_team:
      lead: orchestrator
      teammates: [legal, security, architect]
      task_list:
        enabled: true
        initial_tasks:
          - title: "Revisar contrato"
            assigned_to: legal
          - title: "Auditar dependências"
            assigned_to: security
            depends_on: ["..."]  # by index ou id pré-definido
  ```
- [ ] Validação Pydantic: detecção de ciclos em `depends_on` → erro de configuração explícito.

### Testes (Test-First, AnyIO)

- [ ] `tests/core/runtime/test_task_list_store_basic.py` — CRUD + status transitions; `update_status(COMPLETED→COMPLETED)` é idempotente; transições inválidas levantam erro.
- [ ] `tests/core/runtime/test_task_list_claim_race.py` — 10 teammates competindo por 1 tarefa: exatamente 1 vence.
- [ ] `tests/core/runtime/test_task_list_dependencies.py` — A→B→C; B/C não claimables até deps; ciclo detectado no boot.
- [ ] `tests/core/runtime/test_task_list_release_on_cancel.py` — teammate cancelado em meio a `IN_PROGRESS` libera tarefa.
- [ ] `tests/core/runtime/test_team_runtime_with_task_list.py` — E2E: lead cria 5 tarefas no system prompt → 3 teammates consomem em paralelo → todas `COMPLETED` → event log canônico.
- [ ] `tests/core/runtime/test_task_list_filter_by_labels.py` — teammate "legal" só claim de tarefas com label `legal`; ignora outras.

---

## Invariantes Afetadas

- [x] **Isolamento de Adapters** — `TaskListStore` é interno; default `InMemoryTaskListStore` sem dependências externas.
- [x] **Microkernel** — sem novos runtimes; estende `TeamRuntime`.
- [x] **Assincronismo Canônico (AnyIO)** — `anyio.Lock` para concorrência; zero `threading`.
- [x] **Policies Event-Driven** — operações emitem eventos canônicos; `TaskListStore` não dispara comportamento, apenas registra estado.

---

## Dependências

| Dependência                                     | Tipo     | Estado                       |
|-------------------------------------------------|----------|------------------------------|
| `TeamRuntime` (spec 015)                        | Interna  | A entregar primeiro          |
| `StoreProtocol` (`core/contracts/store.py`)     | Interna  | Pronta                       |
| `BuiltinToolRegistry`                           | Interna  | Pronta — estender com 6 tools |
| `ExecutionEvent` / `EventType`                  | Interna  | Pronta — adicionar novos     |
| `anyio.Lock`, `anyio.move_on_after`             | Externa  | Já em uso                    |

---

## Arquitetura proposta (alto nível)

```
miniautogen/
├── core/
│   ├── contracts/
│   │   ├── store.py                # (existente) — TaskListStore herda StoreProtocol
│   │   └── team_task.py            # NOVO — TaskStatus, TaskEntry, TaskFilter
│   └── runtime/
│       ├── team_runtime.py         # estendido — instancia TaskListStore quando enabled
│       ├── team_task_list.py       # NOVO — InMemoryTaskListStore
│       └── builtin_tools.py        # estendido — task_add/list/claim/complete/fail/view
└── schemas.py                       # estendido — TaskListConfig, TaskEntrySpec
```

**Boundary:** `team_task_list.py` importa apenas de `core/contracts/`, `anyio`, stdlib, `observability`. Sem adapters.

---

## Notas Adicionais

### Por que in-memory na v1?

A task list de um team run é **efêmera** — vive enquanto o team run vive. Persistência cross-process (e.g. retomar um team após reboot) é cenário diferente, com requisitos de schema migration, race entre processos, etc. Adiar para spec 018+ mantém o MVP focado.

### `lead_runs_first` vs spec 015

Spec 015 estabelece lead-depois-dos-teammates como default (fan-out estático). Esta spec inverte para `lead_runs_first=True` **quando `task_list.enabled`**, porque o board precisa estar populado antes dos teammates terem o que consumir. Os dois modos coexistem; o YAML decide.

### Detecção de idle (terminar o team run)

Sem mailbox (spec 017), a única condição de idle é "board vazio E nenhum teammate em `IN_PROGRESS`". O `TeamRuntime` polla isso a cada N ms (default 200ms) e, após `idle_threshold_seconds` (default 5s) estável, sinaliza fim do team run. Spec 017 substitui essa heurística pelo hook `TeammateIdle` canônico (que considera também o mailbox).

### Ciclos em `depends_on`

Detecção é estática (no boot do team) via topological sort. Tarefas adicionadas em runtime (`task_add` por um teammate) também passam pelo check antes de aceitar — `add` rejeita se criar ciclo. Comportamento documentado em docstring.

### Future Work (fora deste ciclo)

- **Persistência via SQLAlchemy** (`SqlAlchemyTaskListStore`) para retomar team runs entre processos. Spec separada.
- **Subscribe pattern** — em vez de polling, teammates `await store.next_available(labels=...)` que bloqueia até tarefa apta surgir. Otimização; correctness não muda.
- **Prioridades** — campo `priority: int` em `TaskEntry`; `claim` retorna prioridade mais alta primeiro. Pode entrar nesta spec se trivial; senão fica para depois.
