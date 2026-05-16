# Plano Técnico: Team Mailbox & Plan Approval

| Campo         | Valor                                |
|---------------|--------------------------------------|
| Spec ID       | 017                                  |
| Data          | 2026-05-16                           |
| Complexidade  | Large                                |
| Depende de    | Specs 015 (TeamRuntime) e 016 (TaskListStore) entregues |

---

## Arquitetura Proposta

### Visão Geral

O ciclo entrega quatro primitivos coesos:

1. **`MailboxStore`** — `StoreProtocol`-shaped, in-memory por team run. Encapsula um `anyio.MemoryObjectStream` **por destinatário** (decisão justificada em Notas) e expõe API FIFO `send` / `receive_stream` / `peek` / `pending_count`.
2. **`TeamHook` (NOVO protocolo)** — irmão de `AgentHook` mas focado no ciclo de vida do **time**, não do turno do agente. Hospeda os 4 hooks novos (`MessageReceived`, `TeammateIdle`, `PlanApprovalRequested`, `PlanApprovalDecided`). Justificativa abaixo.
3. **6 tools canônicas** em `BuiltinToolRegistry`: `send_message`, `inbox_read`, `inbox_pop`, `request_plan_approval`, `approve_plan`, `reject_plan`. Tools recebem injeção do `MailboxStore` + `agent_id` corrente via factory no boot do team run.
4. **`ApprovalGatedToolRegistry`** — `ToolRegistryProtocol` decorator que **envelopa** o `ToolRegistry` do teammate quando `plan_approval.required_for` está configurado no YAML. Antes de executar uma tool sensível, dispara `request_plan_approval` internamente; aprovação libera execução, rejeição/timeout cancela. **Esta é a alternativa correta a um `RuntimeInterceptor`** (justificativa nas Notas).

O `TeamRuntime` (entregue na 015, estendido aqui) detecta `mailbox_enabled=True`, instancia `MailboxStore` + `TeamHook`-bus, registra as 6 tools e — quando `plan_approval.required_for` listado — embrulha o tool registry de cada teammate.

### Módulos Afetados

| Módulo / Caminho                                            | Tipo                  |
|-------------------------------------------------------------|-----------------------|
| `miniautogen/core/contracts/team_message.py`                | **Novo**              |
| `miniautogen/core/contracts/team_hook.py`                   | **Novo**              |
| `miniautogen/core/runtime/team_mailbox.py`                  | **Novo**              |
| `miniautogen/core/runtime/team_plan_approval.py`            | **Novo** (request registry + lookup) |
| `miniautogen/core/runtime/approval_gated_tool_registry.py`  | **Novo** (decorator)  |
| `miniautogen/core/runtime/builtin_team_tools.py`            | **Novo** (factories das 6 tools — fora de `builtin_tools.py` para preservar boundary single-agent) |
| `miniautogen/core/runtime/team_runtime.py`                  | Alterado (mailbox bootstrap, hook bus, idle aggregator, ApprovalGated registry wiring) |
| `miniautogen/core/runtime/team_task_list.py`                | Alterado (loop principal de teammate ganha branch `inbox.receive_stream()` — ponto de extensão sobre spec 016) |
| `miniautogen/core/contracts/coordination.py`                | Alterado (`TeamPlan.mailbox_enabled`, `plan_approval: PlanApprovalConfig | None`) |
| `miniautogen/core/events/types.py`                          | Alterado (novos `EventType`) |
| `miniautogen/schemas.py`                                    | Alterado (`MailboxConfig`, `PlanApprovalConfig`) |
| `miniautogen/core/runtime/builtin_tools.py`                 | **INTOCADO**          |
| `miniautogen/core/runtime/agent_runtime.py`                 | **INTOCADO** (regra §3.5; zero código novo) |
| `miniautogen/core/contracts/agent_hook.py`                  | **INTOCADO** (não estendido — decisão Hook vs TeamHook nas Notas) |
| `miniautogen/policies/approval*.py`                         | **INTOCADO** (semântica de pipeline-gate humano permanece intacta) |
| `miniautogen/core/effect_interceptor.py`                    | **INTOCADO**          |
| `tests/core/runtime/test_mailbox_basic.py`                  | **Novo**              |
| `tests/core/runtime/test_mailbox_concurrent_senders.py`     | **Novo**              |
| `tests/core/runtime/test_mailbox_cancellation.py`           | **Novo**              |
| `tests/core/runtime/test_plan_approval_granted.py`          | **Novo**              |
| `tests/core/runtime/test_plan_approval_denied.py`           | **Novo**              |
| `tests/core/runtime/test_plan_approval_timeout.py`          | **Novo**              |
| `tests/core/runtime/test_teammate_idle_hook.py`             | **Novo**              |
| `tests/core/runtime/test_team_runtime_full.py`              | **Novo** (E2E)        |
| `tests/core/runtime/test_approval_gated_tool_registry.py`   | **Novo**              |
| `tests/architecture/test_mailbox_isolation.py`              | **Novo** (verifica zero import de adapters / SDKs em `team_mailbox.py` e parentes) |

### Diagrama de fluxo

```
                                      ┌────────────────────────────┐
                                      │   TeamRuntime  (per run)   │
                                      │  - MailboxStore            │
                                      │  - TeamHookBus             │
                                      │  - PlanApprovalRegistry    │
                                      │  - IdleAggregator          │
                                      └─────┬──────────────────────┘
                                            │ spawns N sub-runs
                ┌───────────────────────────┼──────────────────────────────┐
                ▼                           ▼                              ▼
        ┌───────────────┐           ┌───────────────┐              ┌───────────────┐
        │ Teammate A    │           │ Teammate B    │              │   Lead        │
        │ AgentRuntime  │           │ AgentRuntime  │              │ AgentRuntime  │
        │  + tools:     │           │  + tools:     │              │  + tools:     │
        │  send/inbox/* │           │  send/inbox/* │              │  approve/reject│
        └──────┬────────┘           └──────┬────────┘              └──────┬────────┘
               │                           │                              │
   send_message(to="B")                    │                              │
               ▼                           │                              │
        ┌──────────────────────────────────┴──────────────────────────────┴────┐
        │              MailboxStore (per-team-run)                            │
        │   inbox_A: MemoryObjectStream  ┐                                    │
        │   inbox_B: MemoryObjectStream  ├── send → ev MESSAGE_SENT           │
        │   inbox_lead: MemoryObjectStream┘  receive → ev MESSAGE_DELIVERED   │
        └──────┬─────────────────────────────────────────────────────────────┘
               │ B's loop: await inbox_B.receive_stream().__anext__()
               ▼
        ┌──────────────────────────────────────────────────────────────────┐
        │  TeammateLoop (estende loop da spec 016):                        │
        │    while not cancelled:                                          │
        │      with anyio.move_on_after(idle_threshold):                   │
        │        msg = await inbox.next()  ─────────►  TeamHookBus.fire(   │
        │                                                MessageReceived)  │
        │      if no msg: task = await task_list.claim(...)                │
        │      if no task: IdleAggregator.mark(self); fire(TeammateIdle)   │
        │      if all idle: break                                          │
        └──────────────────────────────────────────────────────────────────┘

   Plan approval cycle (cross-process inside same team run):
        Teammate.request_plan_approval(plan, timeout=300)
           │
           ├── PlanApprovalRegistry.register(corr_id, future)
           ├── mailbox.send(MailMessage(kind="plan_approval_request",
           │                            to=lead, correlation_id=corr_id))
           └── result = await move_on_after(timeout): future.wait()
                                              │
        Lead.approve_plan(corr_id, comment)   ▼
           └── mailbox.send(MailMessage(kind="plan_approval_granted",
                                        to=teammate, correlation_id=corr_id))
                  ▲
                  │ teammate's inbox loop sees granted msg
                  └─ PlanApprovalRegistry.resolve(corr_id, "granted")
                     → future completes → teammate returns "granted"
```

---

## Contratos e Interfaces

### `MailMessage` & `PlanApprovalRequest`

```python
# miniautogen/core/contracts/team_message.py
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field

MailKind = Literal[
    "chat",
    "plan_approval_request",
    "plan_approval_granted",
    "plan_approval_denied",
]

class MailMessage(BaseModel):
    id: str                         # UUID4
    from_agent: str
    to_agent: str
    content: str
    kind: MailKind = "chat"
    correlation_id: str | None = None
    metadata: tuple[tuple[str, Any], ...] = ()   # frozen, como ExecutionEvent
    sent_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PlanApprovalRequest(BaseModel):
    correlation_id: str            # UUID4
    from_agent: str                # quem pediu
    to_agent: str                  # lead
    plan: str | dict[str, Any]
    timeout_seconds: float = 300.0
    created_at: datetime
```

### `MailboxStore`

```python
# miniautogen/core/runtime/team_mailbox.py
from typing import AsyncIterator, Protocol, runtime_checkable

@runtime_checkable
class MailboxStore(Protocol):
    async def send(self, message: MailMessage) -> None: ...
    def receive_stream(self, agent: str) -> AsyncIterator[MailMessage]: ...
    async def peek(self, agent: str) -> list[MailMessage]: ...
    async def pending_count(self, agent: str) -> int: ...
    async def aclose(self) -> None: ...   # fecha todos os streams (cancel-safe)

class InMemoryMailboxStore:
    """One MemoryObjectStream per (team_run_id, agent). Backpressure: bounded buffer (default 256)."""
    def __init__(self, *, agents: list[str], buffer_size: int = 256,
                 event_sink: EventSink | None = None,
                 team_run_id: str | None = None) -> None: ...
```

Implementação interna:

- Para cada `agent` em `agents`, cria `send_stream, receive_stream = anyio.create_memory_object_stream(max_buffer_size=buffer_size)`.
- `send(msg)` faz `send_stream[msg.to_agent].send(msg)` + emite `MESSAGE_SENT`.
- `receive_stream(agent)` retorna o `MemoryObjectReceiveStream` (async iterator nativo). O receptor envolve cada `__anext__` para emitir `MESSAGE_DELIVERED` antes de devolver ao chamador.
- `aclose()` chama `.aclose()` em todos os streams — propagação canônica AnyIO; pendências são descartadas, `EndOfStream` é lançado em `receive`ers ativos.

### `TeamHook` (novo protocolo)

```python
# miniautogen/core/contracts/team_hook.py
@runtime_checkable
class TeamHook(Protocol):
    async def on_message_received(self, message: MailMessage,
                                  context: RunContext) -> None: ...
    async def on_teammate_idle(self, teammate: str,
                               context: RunContext) -> None: ...
    async def on_plan_approval_requested(self, request: PlanApprovalRequest,
                                         context: RunContext) -> None: ...
    async def on_plan_approval_decided(self, correlation_id: str,
                                       decision: Literal["granted","denied","timeout"],
                                       reason: str | None,
                                       context: RunContext) -> None: ...
```

`TeamRuntime` mantém uma lista `team_hooks: list[TeamHook]` e dispara em série (mesma semântica de `AgentHook.after_event`). Hooks têm default pass-through.

### Tools (factories injetando state per-team-run)

```python
# miniautogen/core/runtime/builtin_team_tools.py

def build_team_tools(
    *,
    agent_id: str,
    is_lead: bool,
    mailbox: MailboxStore,
    approvals: PlanApprovalRegistry,
    event_sink: EventSink,
    team_run_id: str,
) -> list[tuple[ToolDefinition, ToolHandler]]:
    """Devolve definições + handlers das 6 tools, com closures sobre o estado.

    - `agent_id` é o identity do chamador (gravado em from_agent e usado
      para validar approve_plan/reject_plan: só `is_lead=True` aceita).
    - `approvals` mantém dict {correlation_id: anyio.Event + slot resultado}.
    """
```

Tools registradas:

- `send_message(to_teammate, content, kind="chat", correlation_id?, metadata?)` → retorna `message_id`. `kind` é validado: teammates não emitem `plan_approval_*` diretamente — só via `request_plan_approval` / `approve_plan` / `reject_plan` (encapsulamento).
- `inbox_read(limit=10)` → `peek` não destrutivo.
- `inbox_pop(limit=10)` → consome via `receive_stream` com `move_on_after(0)`; útil para o agente compactar inbox; emite `INBOX_DRAINED`.
- `request_plan_approval(plan, to_lead=True, timeout_seconds=300)`:
  ```python
  corr_id = uuid4().hex
  evt = approvals.register(corr_id, timeout_seconds)
  await mailbox.send(MailMessage(kind="plan_approval_request",
                                 from_agent=agent_id, to_agent=lead,
                                 correlation_id=corr_id,
                                 content=json.dumps(plan) if isinstance(plan, dict) else plan))
  emit PLAN_APPROVAL_REQUESTED
  with anyio.move_on_after(timeout_seconds) as scope:
      decision = await evt.wait()           # resolved by lead's tool
  if scope.cancel_called:
      approvals.resolve(corr_id, "timeout", reason="timeout expired")
      emit PLAN_APPROVAL_TIMED_OUT
      return "timeout"
  return decision  # "granted" | "denied"
  ```
- `approve_plan(correlation_id, comment?)` (só lead): `approvals.resolve(corr_id, "granted", comment)`; envia `MailMessage(kind="plan_approval_granted")` para o requester; emite `PLAN_APPROVAL_GRANTED`. Se `agent_id != lead_agent`, retorna erro de validação.
- `reject_plan(correlation_id, reason)` (só lead): análogo, `PLAN_APPROVAL_DENIED`.

### `PlanApprovalRegistry`

```python
# miniautogen/core/runtime/team_plan_approval.py
class PlanApprovalRegistry:
    """Cross-teammate rendezvous para plan approval.
    Vive um por team_run; o mailbox loop do teammate consulta-o ao
    receber MailMessage com kind=plan_approval_* + correlation_id.
    """
    def __init__(self) -> None:
        self._slots: dict[str, tuple[anyio.Event, dict[str, Any]]] = {}

    def register(self, corr_id: str, timeout: float) -> ApprovalSlot: ...
    def resolve(self, corr_id: str, decision: str, reason: str | None = None) -> None: ...
    async def wait(self, corr_id: str) -> tuple[str, str | None]: ...
```

O loop principal do teammate (estendido da spec 016) faz duas coisas ao receber mensagem `kind="plan_approval_granted|denied"`: (a) chama `approvals.resolve(...)` para acordar o `request_plan_approval` pendente; (b) dispara `TeamHook.on_plan_approval_decided`.

### `ApprovalGatedToolRegistry` (decorator)

```python
# miniautogen/core/runtime/approval_gated_tool_registry.py
class ApprovalGatedToolRegistry:
    """ToolRegistryProtocol decorator que exige plan approval antes de
    executar tools listadas em `required_for`. Constraint §3.5: zero
    código novo em AgentRuntime — wrapping é injetado pelo TeamRuntime."""

    def __init__(
        self,
        *,
        inner: ToolRegistryProtocol,
        approval_tool: Callable[[str | dict], Awaitable[str]],  # = request_plan_approval
        required_for: set[str],
        agent_id: str,
        event_sink: EventSink,
    ) -> None: ...

    def list_tools(self) -> list[ToolDefinition]:
        return self._inner.list_tools()

    def has_tool(self, name: str) -> bool:
        return self._inner.has_tool(name)

    async def execute_tool(self, call: ToolCall) -> ToolResult:
        if call.tool_name in self._required_for:
            plan_summary = {"tool": call.tool_name, "params": call.params}
            decision = await self._approval_tool(plan_summary)
            if decision != "granted":
                return ToolResult(success=False,
                                  error=f"Plan approval {decision} for {call.tool_name}")
        return await self._inner.execute_tool(call)
```

### Novos `EventType`

```python
# miniautogen/core/events/types.py — adicionar à enum EventType:
MESSAGE_SENT             = "message_sent"
MESSAGE_DELIVERED        = "message_delivered"
INBOX_DRAINED            = "inbox_drained"
TEAMMATE_IDLE            = "teammate_idle"
PLAN_APPROVAL_REQUESTED  = "plan_approval_requested"
PLAN_APPROVAL_GRANTED    = "plan_approval_granted"
PLAN_APPROVAL_DENIED     = "plan_approval_denied"
PLAN_APPROVAL_TIMED_OUT  = "plan_approval_timed_out"
```

E exportar `TEAM_MAILBOX_EVENT_TYPES`, `TEAM_PLAN_APPROVAL_EVENT_TYPES` para filtros canônicos.

### `TeamPlan` estendido

```python
class MailboxConfig(BaseModel):
    enabled: bool = False
    buffer_size: int = 256
    idle_threshold_seconds: float = 5.0

class PlanApprovalConfig(BaseModel):
    timeout_seconds: float = 300.0
    required_for: list[str] = Field(default_factory=list)   # tool names

class TeamPlan(CoordinationPlan):
    # ... campos das specs 015 + 016 ...
    mailbox: MailboxConfig | None = None      # backwards-compatible
    plan_approval: PlanApprovalConfig | None = None
```

---

## Riscos e Mitigações

| Risco                                                                              | Impacto | Mitigação                                                                                                                  |
|------------------------------------------------------------------------------------|---------|----------------------------------------------------------------------------------------------------------------------------|
| **Vazamento de streams em cancelamento.** Cancel do team_group deixa `MemoryObjectStream`s pendurados (`send_stream` aberto, receptor em `__anext__`). | Alto    | `TeamRuntime` faz `try/finally` em torno do `task_group` chamando `mailbox.aclose()`; `aclose()` fecha `send_stream` primeiro → receptores recebem `EndOfStream` ordeiramente. Teste dedicado em `test_mailbox_cancellation.py`. |
| **Deadlock em plan approval.** Lead trava (e.g. esperando outra coisa); teammate fica preso indefinidamente. | Alto    | `request_plan_approval` SEMPRE envolto em `anyio.move_on_after(timeout)`. Test `test_plan_approval_timeout.py` força lead inativo e valida retorno em `timeout + ≤100ms`. |
| **Race entre timeout e resolve do lead.** Lead aprova exatamente quando `move_on_after` dispara. | Médio   | `PlanApprovalRegistry.resolve` é idempotente (no-op se já resolvido); resultado priorizado por quem chega primeiro. Coberto por teste com `anyio.fail_after` apertado. |
| **FIFO sob senders concorrentes.** N teammates enviam para 1 inbox; ordem percebida pode não bater com `sent_at`. | Médio   | `MemoryObjectStream.send` é serializável dentro do mesmo task scheduler; tiebreak por `(sent_at, message_id)` documentado em docstring. Teste `test_mailbox_concurrent_senders.py` valida ordem reprodutível com 5 senders. |
| **Backpressure.** Inbox cheia (>256 mensagens não lidas) bloqueia `send`. | Médio   | `buffer_size` configurável; quando atingido, `send` bloqueia o emissor — comportamento canônico de AnyIO, **não** descartamos mensagens. Documentado; emite `MAILBOX_BACKPRESSURE` (variante de `MESSAGE_SENT` com flag) opcionalmente em fase 2. |
| **Hardcoded prompts no AgentRuntime.** Tentação de "se mensagem kind=plan_approval_request, mostrar...". | Alto    | Constraint §3.5: AgentRuntime **INTOCADO**. `ApprovalGatedToolRegistry` (decorator) e `TeamHook` (no `TeamRuntime`) absorvem toda a lógica. Test arquitetural `test_mailbox_isolation.py` faz `grep` por `plan_approval` em `agent_runtime.py` e falha se encontrar. |
| **Confusão com `APPROVAL_*` existente.** Eventos `APPROVAL_REQUESTED` etc. já existem para pipeline-gates humanos (`ApprovalChannel`). | Médio   | Decisão: **eventos `PLAN_APPROVAL_*` são distintos** (justificativa nas Notas). Mantemos namespaces separados (`PLAN_*` para team peer↔peer; `APPROVAL_*` para humano↔pipeline). Documentado em CHANGELOG e no docstring do enum. |
| **`TeammateIdle` falso-positivo.** Hook dispara entre `inbox.next()` retornar `None` e teammate ainda processar último msg. | Médio   | `IdleAggregator` exige *três* condições atômicas: `pending_count(agent)==0` ∧ `task_list.claim_count(agent)==0` ∧ teammate não está em handler ativo. Marca/desmarca dentro do mesmo `anyio.Lock` por teammate. |
| **Validador `is_lead` em `approve_plan`.** Teammate malicioso/buggy tenta aprovar próprio plano. | Médio   | Tool factory captura `is_lead` no boot; runtime emite `TOOL_FAILED` com mensagem clara se `is_lead=False`. Não é segurança real (todos rodam no mesmo processo) mas defensive coding alinhado ao FC §6. |
| **Aninhamento de teams.** Team dentro de step de workflow tem inbox próprio (já isolado por `team_run_id`) mas hooks `TeammateIdle` poderiam atravessar fronteiras se mailbox fosse global. | Médio   | Decisão: **uma stream por `(team_run_id, agent_id)`** — isolamento total. `MailboxStore` recebe `team_run_id` no construtor e nunca compartilha streams. |
| **Tarefa adicionada via `task_add` durante state idle.** Teammate marcado idle, lead cria tarefa para ele — `TeammateIdle` deveria ser revogado mas o runtime já encerrou. | Médio   | `IdleAggregator.mark_busy(agent)` é chamado ao receber MailMessage OR ao `task_claim` bem-sucedido OR ao `task_add(assigned_to=agent)` — o último é um hook adicionado em `TaskListStore.add` (ponto de extensão sobre spec 016). |

---

## Estimativa de Complexidade

| Aspecto              | Estimativa                                                              |
|----------------------|-------------------------------------------------------------------------|
| Ficheiros novos      | 14 (6 código + 8 testes; 1 dos testes é arquitetural)                  |
| Ficheiros alterados  | 5 (`team_runtime.py`, `team_task_list.py`, `coordination.py`, `events/types.py`, `schemas.py`) |
| Testes novos         | ~38 (basic 6, concurrent 4, cancel 4, plan_approval_granted 5, denied 4, timeout 4, idle 5, e2e 4, gated_registry 2) |
| Esforço estimado     | **Large** (5-8 dias). Concorrência + cancelamento estruturado + rendezvous cross-agent + integração com 2 specs anteriores; semelhante em risco à própria 015. |

---

## Sequência de Implementação

Test-First. T01–T09 são testes falhando que cravam o contrato antes de qualquer linha de implementação.

1. **Test-first arquitetural:** `tests/architecture/test_mailbox_isolation.py` — varre `core/runtime/team_mailbox.py`, `team_plan_approval.py`, `approval_gated_tool_registry.py`, `builtin_team_tools.py` procurando imports de `litellm`, `google.generativeai`, qualquer adapter; varre `agent_runtime.py` procurando `plan_approval` / `MailboxStore` / `MailMessage`. Falha se encontrar.
2. **Test-first:** `tests/core/runtime/test_mailbox_basic.py` — `send` → `receive_stream`; FIFO single-sender; `peek` não destrutivo; `pending_count` correto antes/depois.
3. **Test-first:** `tests/core/runtime/test_mailbox_concurrent_senders.py` — 5 senders concorrentes via `create_task_group` enviam 100 msgs cada; receptor verifica ordem por timestamp + tiebreak determinístico; verifica ausência de drops.
4. **Test-first:** `tests/core/runtime/test_mailbox_cancellation.py` — task group recebendo de stream + outro enviando; cancel do escopo → `aclose()` → receptor pega `EndOfStream`, não `Cancelled`-into-loss; nenhum task warning de "task never finished".
5. **Test-first:** `tests/core/runtime/test_plan_approval_granted.py` — fixture com 2 teammates fake; A chama `request_plan_approval`; B (lead) consume inbox, lê `MailMessage(kind=plan_approval_request)`, invoca `approve_plan`; A recebe `"granted"` em ≤200ms.
6. **Test-first:** `tests/core/runtime/test_plan_approval_denied.py` — análogo, lead chama `reject_plan(corr_id, reason="risk")`; A vê `"denied"` + razão em payload.
7. **Test-first:** `tests/core/runtime/test_plan_approval_timeout.py` — lead nunca consome; teammate com `timeout_seconds=0.2` recebe `"timeout"` em ≤300ms; `PLAN_APPROVAL_TIMED_OUT` emitido com `correlation_id` correto.
8. **Test-first:** `tests/core/runtime/test_teammate_idle_hook.py` — teammate com inbox vazio + task list vazio → `TeammateIdle` dispara após `idle_threshold`; envio de mensagem cancela estado idle (mark_busy via mailbox); novo `TeammateIdle` quando inbox drena novamente.
9. **Test-first:** `tests/core/runtime/test_approval_gated_tool_registry.py` — wrap um `InMemoryToolRegistry` com tool `shell_command` em `required_for`; mock `approval_tool` retornando `"granted"` → tool executa; retornando `"denied"` → `ToolResult.success=False`; retornando `"timeout"` → erro com mensagem clara.
10. **Test-first E2E:** `tests/core/runtime/test_team_runtime_full.py` — `TeamPlan(lead, [A,B,C], mailbox=enabled, task_list=enabled, plan_approval={required_for:["shell_command"]})`. Lead popula 5 tarefas; B pega tarefa que invoca `shell_command` → aprovação automática; troca de 2 mensagens entre A e C via `send_message`; todos completam; event log canônico reconstrói toda a cronologia.
11. **Implementação:** `contracts/team_message.py` — `MailMessage`, `PlanApprovalRequest`, `MailKind` literal.
12. **Implementação:** `contracts/team_hook.py` — protocolo `TeamHook`.
13. **Implementação:** `events/types.py` — adicionar 8 `EventType` + `TEAM_MAILBOX_EVENT_TYPES` / `TEAM_PLAN_APPROVAL_EVENT_TYPES` sets exportados.
14. **Implementação:** `runtime/team_mailbox.py` — `InMemoryMailboxStore` (1 stream por agent, `aclose` cooperativo). Tests 2–4 passam.
15. **Implementação:** `runtime/team_plan_approval.py` — `PlanApprovalRegistry` com `register/resolve/wait` (`anyio.Event` interno, idempotente).
16. **Implementação:** `runtime/builtin_team_tools.py` — factory `build_team_tools(...)` retornando 6 (`ToolDefinition`, handler) com closures sobre `mailbox`/`approvals`/`agent_id`/`is_lead`. Tests 5–7 passam.
17. **Implementação:** `runtime/approval_gated_tool_registry.py` — decorator + teste 9 passa.
18. **Alteração:** `contracts/coordination.py` — `MailboxConfig`, `PlanApprovalConfig`, `TeamPlan.mailbox`, `TeamPlan.plan_approval` (default `None` = retrocompatível com specs 015/016).
19. **Alteração:** `schemas.py` — schema YAML correspondente; validação Pydantic (e.g. `required_for` deve ser subset de tools registradas — checado no boot do team).
20. **Alteração:** `runtime/team_runtime.py` — no boot, se `plan.mailbox.enabled`: instancia `MailboxStore(agents=lead+teammates, team_run_id=ctx.run_id)`, `PlanApprovalRegistry`, `IdleAggregator`. Adiciona 6 tools via `build_team_tools` ao `ToolRegistry` de cada teammate (e do lead — lead tem `approve_plan`/`reject_plan` + `send_message`; teammates têm `send_message`/`inbox_*`/`request_plan_approval`). Se `plan.plan_approval.required_for`: embrulha cada teammate's registry com `ApprovalGatedToolRegistry`. `try/finally` chama `mailbox.aclose()`.
21. **Alteração:** `runtime/team_task_list.py` — ponto de extensão do loop principal de teammate da spec 016. Loop passa de `claim → execute → complete` para:
    ```python
    while not cancelled:
        with anyio.move_on_after(idle_threshold) as scope:
            msg = await anext(mailbox.receive_stream(agent), None)
        if msg is not None:
            await team_hooks.fire_message_received(msg, ctx)
            if msg.kind in {"plan_approval_granted","plan_approval_denied"}:
                approvals.resolve(msg.correlation_id,
                                  "granted" if msg.kind.endswith("granted") else "denied")
            # caso "chat" ou "plan_approval_request": teammate processa via prompt do agente
            continue
        task = await task_list.try_claim(agent, ...)
        if task: execute_task(task); continue
        await idle_aggregator.mark_idle(agent)
        if idle_aggregator.all_idle(): break
    ```
    Teste 8 e 10 passam.
22. **Alteração:** `runtime/team_runtime.py` — `IdleAggregator` + bus de `TeamHook` (lista em série + emit canônico de `TEAMMATE_IDLE`).
23. Rodar `skills/run_anyio_tests.sh` → todos verdes. Cobertura `core/runtime/team_*.py` ≥ 85%.
24. Rodar `ruff` + `mypy` (módulos novos com tipagem estrita).
25. **Smoke manual:** rodar workspace de exemplo com 3 teammates + plan_approval (`shell_command` na lista) — validar via `miniautogen run` (com flag experimental da 015) que log canônico reconstrói o ciclo de aprovação.

---

## Notas

### Decisão 1: **`TeamHook` novo, não estender `AgentHook`**

`AgentHook` (`before_turn`, `after_event`, `on_error`) tem semântica de **turno individual de um único agente**: transforma `messages` waterfall, observa `ExecutionEvent`, recupera de erro. Os 4 hooks novos (`MessageReceived`, `TeammateIdle`, `PlanApprovalRequested`, `PlanApprovalDecided`) operam num plano diferente:

- **Disparados pelo `TeamRuntime`**, não pelo `AgentRuntime` (per Constraint #5 da spec).
- **Não transformam** input/output do turno; **observam o ciclo de vida do time**.
- Dois deles (`PlanApprovalRequested`/`Decided`) carregam tipos específicos (`PlanApprovalRequest`, `decision: Literal`) que não cabem semanticamente em `after_event`.

Trade-off considerado: estender `AgentHook` evita um protocolo novo; mas obrigaria pass-through em 4 hooks irrelevantes para 95% dos casos de uso (single-agent), inflando a superfície da API canônica e quebrando o ISP. Optamos pelo `TeamHook` separado — composição limpa, zero impacto em hooks de agente existentes, e `TeamRuntime` mantém um registry próprio (`team_hooks: list[TeamHook]`) gerenciado pelo bootstrap do team run.

### Decisão 2: **Eventos `PLAN_APPROVAL_*` são distintos de `APPROVAL_*`**

`APPROVAL_REQUESTED / GRANTED / DENIED / TIMEOUT` já existem (`events/types.py:51-54`) e são consumidos por `PipelineRunner` (`pipeline_runner.py:312-354`) + `ApprovalChannel` (`policies/approval_channel.py`). Semântica vigente: **gate humano-na-loop em pipelines**, com `ApprovalRequest(request_id, action, risk_assessment)` — orientado a "humano aprova ação arriscada antes de execução pipeline-level".

Plan approval da spec 017 é **peer-to-peer entre agentes do time**, com `correlation_id` ligando request↔decision, payload incluindo `plan` (string/dict livre), e ciclo de vida atrelado ao `team_run_id`. Reusar `APPROVAL_*` confundiria consumidores (e.g. dashboards de UI que filtram `APPROVAL_REQUESTED` esperando um pedido humano apareceriam ruidosamente notificados de aprovações inter-agente). Mantemos namespaces separados:

- `APPROVAL_*` → humano ↔ pipeline.
- `PLAN_APPROVAL_*` → teammate ↔ lead (peer ↔ peer dentro do team).

`APPROVAL_CHANNEL_*` permanece sem mexer (são o subset decoupled da abordagem antiga).

### Decisão 3: **`plan_approval.required_for` via decorator de `ToolRegistry`, não `RuntimeInterceptor`**

A spec lista duas opções: (a) `RuntimeInterceptor` existente, ou (b) hook novo. Análise:

- `RuntimeInterceptor` opera em **steps de flow** (`before_step` / `should_execute` / `after_step` / `on_error`). Toolcall dentro de um turno de agente **não é um step de flow** — é uma operação interna do `AgentRuntime`, abaixo da granularidade do interceptor. Forçar isso obrigaria a expor cada tool call como um step, mudança invasiva no `PipelineRunner`.
- `EffectInterceptor` envolve tool execution (caminho mais próximo), mas é orientado a **idempotência** via journal, não a aprovação humana/lead.

Escolhemos a opção mais limpa: **`ApprovalGatedToolRegistry` é um decorator `ToolRegistryProtocol`**. `TeamRuntime` injeta o wrapping ao construir o `ToolRegistry` de cada teammate — `AgentRuntime` consume `tool_registry.execute_tool(call)` agnóstico (já é o caminho normal, ver `agent_runtime.py:638`). **Zero linha nova no `AgentRuntime`**, satisfazendo §3.5 do CLAUDE.md de forma natural. O `approval_tool` injetado no decorator é a mesma closure `request_plan_approval` registrada como tool — reuso máximo.

### Decisão 4: **Uma `MemoryObjectStream` por destinatário**, não stream centralizada

Trade-off considerado:

| Opção | Prós | Contras |
|---|---|---|
| **1 stream por agente** (escolhida) | FIFO por destinatário trivial; cada teammate só ouve sua própria stream; cancelamento limpo (fecha N streams independentemente); backpressure isolada (inbox cheia de A não afeta B). | N streams para gerenciar; `aclose()` itera. |
| 1 stream centralizada com filtro `to_agent` | 1 stream só; mais simples conceitualmente. | Receptor precisa filtrar e descartar msgs de outros → wasted compute; backpressure compartilhada (inbox bloqueada de A trava todos); cancelamento de A sozinho é não trivial; FIFO global não é o que queremos (queremos FIFO per-destinatário). |

A opção escolhida é canonicamente AnyIO (cada stream tem seu próprio buffer bounded) e alinha-se com o modelo mental de "inbox por agente". O custo de "iterar N streams em `aclose()`" é negligenciável (N ≤ ~10 teammates em casos reais).

### Decisão 5: **`anyio.move_on_after(timeout)` vs `Cancelled` do team — quem vence**

Em `request_plan_approval`, o teammate espera dentro de `move_on_after(timeout_seconds)`. Cenários:

1. **Lead responde dentro do timeout** → `approvals.wait(corr_id)` retorna → função devolve `"granted"`/`"denied"`. Normal.
2. **Timeout dispara primeiro** → `scope.cancel_called=True`, `approvals.resolve(corr_id, "timeout")` é idempotente, função devolve `"timeout"`. Normal.
3. **Cancel externo do team chega durante a espera** → AnyIO regra: `Cancelled` do escopo pai **propaga através de `move_on_after`** sem ser absorvida (escopo interno só absorve seu próprio cancel relativo). `request_plan_approval` re-levanta `Cancelled` → AgentRuntime trata como `ErrorCategory.CANCELLATION`. `mailbox.aclose()` no `finally` do `TeamRuntime` libera quaisquer streams ainda ativos.
4. **Timeout E cancel chegam quase simultaneamente** → AnyIO prioriza `Cancelled` (canônico); função levanta `Cancelled` mesmo se `scope.cancel_called=True`. Documentado em docstring + teste no `test_mailbox_cancellation.py`.

Resumo: **cancel do team sempre prevalece sobre timeout** (consistência com AnyIO structured concurrency). Plan approval com timeout devolve `"timeout"`; cancel devolve `Cancelled` propagado.

### Pontos de extensão sobre specs 015 e 016

- **Sobre 015 (`TeamRuntime`):** boot do team run ganha 3 novos passos opcionais (`MailboxStore`, `PlanApprovalRegistry`, `IdleAggregator`) e 1 `try/finally` para `aclose`. `team_hooks` registrados em paralelo aos hooks de agente existentes. Lead pode opcionalmente rodar **junto** com os teammates (não mais "lead-depois") quando `mailbox_enabled=True`, porque ele precisa estar disponível para responder approvals em tempo real. Isso refina o `lead_runs_first` da 016 — quando mailbox ativo, fluxo passa a **lead concorrente, não sequencial**.
- **Sobre 016 (`TaskListStore` + loop de teammate):** o loop "claim → execute → complete" da 016 ganha um **branch de inbox** anterior ao claim (ver passo 21 da sequência). Isso é a única alteração no `team_task_list.py`; o store em si permanece intocado. A heurística de polling-para-idle da 016 (5s padrão) é **substituída** pelo `IdleAggregator` event-driven — mais determinístico e sem latência artificial. A 016 documentou explicitamente essa substituição como esperada.

### Future Work (fora deste ciclo)

- **`SqlAlchemyMailboxStore`** — persistência cross-process; depende de schema migration.
- **Broadcast** (`send_to_all`, `send_to_role`) — derivável de N peer-sends; espera caso de uso real.
- **Compactação automática de inbox** — quando histórico cresce demais, lead consolida.
- **TUI in-process** com alternância entre teammates (`Shift+Down`) — extensão do Rich Live (PR #44).
- **Quality gates declarativos** no YAML (tarefa só completa se passa em validação) — pode ser modelado com `task_complete` + hook `TaskCompletionRequested` (extensão da spec 016).
