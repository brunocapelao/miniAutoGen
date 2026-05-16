# Especificação: Team Mailbox & Plan Approval — comunicação peer-to-peer e gate de aprovação

| Campo      | Valor                          |
|------------|--------------------------------|
| Data       | 2026-05-16                     |
| Autor      | Bruno Capelão                  |
| Status     | Rascunho                       |
| Spec ID    | 017                            |
| Depende de | Specs 015 (TeamRuntime), 016 (Task List) |

---

## Contrato de Prompt (G/C/FC)

### 🎯 Goal (Objetivo)

Fechar o gap com Claude Code Agent Teams completo, adicionando:

1. **Mailbox peer-to-peer.** Cada teammate (incluindo lead) tem uma inbox assíncrona; qualquer participante pode enviar mensagem dirigida (`send_message(to_teammate, content)`). Mensagens são entregues automaticamente; recipiente é notificado via hook canônico.
2. **Plan approval gate.** Teammate pode solicitar aprovação do lead antes de executar um plano de mudança (`request_plan_approval(plan)`); lead recebe na inbox, aprova/rejeita via tool dedicada. Útil para tarefas sensíveis (mudanças de schema, deletions, releases).
3. **Hooks canônicos do time.** `TeammateIdle`, `MessageReceived`, `PlanApprovalRequested`, `PlanApprovalDecided` — extensão de `AgentHook` ou novo `TeamHook` (a definir no plano).
4. **Idle real.** `TeammateIdle` dispara quando: task list vazia para o teammate **E** inbox vazia **E** nenhuma tarefa em `IN_PROGRESS` para ele. Substitui a heurística de polling da spec 016.

**Não-objetivo deste ciclo:**
- Broadcast (send_message_all) — pode ser adicionado depois se necessário; por ora, peer dirigido apenas.
- Mensagens persistentes entre team runs — mailbox é efêmero, igual à task list da 016.
- TUI split panes (tmux) — segue fora de escopo; in-process com Rich é entregue por extensão do PR #44 em ciclo separado.
- Quality gates declarativos no YAML (e.g. "team só termina se matriz de risco existe") — útil mas pode ser modelado como tarefa explícita no board (`task_add(title="Consolidar matriz de risco", assigned_to=lead)`); evitar inflar o escopo desta spec.

### 🚧 Constraint (Restrição)

1. **`MailboxStore` é `StoreProtocol`.** Mesmo padrão de `TaskListStore` da spec 016. Default `InMemoryMailboxStore` em `core/runtime/team_mailbox.py`.
2. **Isolamento de Adapters.** Zero referências a SDKs externos no módulo.
3. **AnyIO event-driven.** `await inbox.next_message(timeout=...)` usa `anyio.MemoryObjectReceiveStream` ou primitivo equivalente. Zero polling em loop.
4. **Tools padronizadas.** `send_message`, `inbox_read`, `inbox_pop`, `request_plan_approval`, `approve_plan`, `reject_plan` em `BuiltinToolRegistry`.
5. **Hooks canônicos.** `TeammateIdle`, `MessageReceived`, `PlanApprovalRequested`, `PlanApprovalDecided` são `AgentHook`s (ou `TeamHook`s, decisão no plano) — disparados pelo `TeamRuntime`, **não** pelo `AgentRuntime` direto. Per §3.5 do CLAUDE.md, `AgentRuntime` é compositor.
6. **Eventos canônicos.** `MESSAGE_SENT`, `MESSAGE_DELIVERED`, `PLAN_APPROVAL_REQUESTED`, `PLAN_APPROVAL_GRANTED`, `PLAN_APPROVAL_DENIED`, `TEAMMATE_IDLE`.

### 🛑 Failure Condition (Condição de Falha)

A implementação **falhou** se, ao fim do ciclo, qualquer um for verdadeiro:

1. Uma mensagem enviada para um teammate **não é entregue** dentro de 100ms em ambiente local (event bus saturado ou bug de routing).
2. `TeammateIdle` dispara enquanto o teammate ainda tem 1+ mensagem na inbox.
3. Plan approval: teammate pede aprovação, lead aprova, mas teammate **não vê** a aprovação chegar via inbox / hook — deadlock.
4. Plan approval com timeout: lead não responde dentro do `timeout_seconds`; teammate fica preso indefinidamente em vez de receber `PLAN_APPROVAL_DENIED(reason="timeout")`.
5. Cancelamento do team com mensagens pendentes nas inboxes **não limpa** os streams AnyIO — vazamento de recursos.
6. Algum hook hardcoded de aprovação aparece no `AgentRuntime` (e.g. "se prompt contém 'plan approved' então ...") — violação da §3.5.
7. `pytest tests/core/runtime/test_team_mailbox.py` ou cobertura do módulo < 85%.

---

## User Stories

- Como **teammate de auditoria**, quero perguntar diretamente ao teammate de compliance sobre um requisito BACEN sem ter que passar pelo lead — `send_message(to="compliance", content="...")` e receber resposta no meu inbox.
- Como **lead**, quero aprovar planos sensíveis (e.g. teammate quer alterar schema de DB) antes deles serem executados — `approve_plan(plan_id)` ou `reject_plan(plan_id, reason)`.
- Como **engenheiro de IA**, quero declarar no YAML que um teammate **sempre** exige plan approval para certas ações (toolset com flag `requires_approval: true`) — para que aprovação não dependa só de boa vontade do prompt.
- Como **operador**, quero ver no event log toda mensagem trocada entre teammates e todo ciclo de aprovação — auditoria completa do "diálogo" do time.

---

## Critérios de Aceitação

### Contratos novos

- [ ] `MailMessage(BaseModel)`:
  - `id: str` (UUID4)
  - `from_agent: str`
  - `to_agent: str`
  - `content: str`
  - `kind: Literal["chat", "plan_approval_request", "plan_approval_granted", "plan_approval_denied"]`
  - `correlation_id: str | None` — liga request → response em aprovações
  - `metadata: dict[str, Any]` — payload extra (e.g. `plan_summary`)
  - `sent_at: datetime`
- [ ] `MailboxStore(StoreProtocol)`:
  - `async send(message: MailMessage) -> None`
  - `async receive_stream(agent: str) -> AsyncIterator[MailMessage]` — drena inbox em ordem FIFO
  - `async peek(agent: str) -> list[MailMessage]` — leitura não destrutiva
  - `async pending_count(agent: str) -> int`
- [ ] `PlanApprovalRequest(BaseModel)` — wrapper sobre `MailMessage` para o caso plan approval; `plan: str | dict`, `timeout_seconds: float`, `created_at`.

### Tools registradas em `BuiltinToolRegistry`

- [ ] `send_message(to_teammate: str, content: str, kind="chat", correlation_id?=None, metadata?={}) -> message_id`
- [ ] `inbox_read(limit?=10) -> list[MailMessage]` (peek, não consome)
- [ ] `inbox_pop(limit?=10) -> list[MailMessage]` (consome)
- [ ] `request_plan_approval(plan: str | dict, to_lead: bool = True, timeout_seconds: float = 300) -> Literal["granted", "denied", "timeout"]` (bloqueia o teammate até resposta ou timeout)
- [ ] `approve_plan(correlation_id: str, comment?: str)` (lead apenas — validação por nome do agente que invoca)
- [ ] `reject_plan(correlation_id: str, reason: str)` (lead apenas)

### Hooks canônicos

- [ ] `TeammateIdle` — disparado pelo `TeamRuntime` quando: inbox vazia + task list não tem `PENDING` para o teammate + nenhum `IN_PROGRESS`. Permite que o teammate "termine seu turno" gracefully ou que o runtime conclua o team run quando todos estão idle simultaneamente.
- [ ] `MessageReceived` — disparado para o `agent_id == to_agent` na entrega; hook pode acionar tool de processamento ou apenas notificar.
- [ ] `PlanApprovalRequested` — disparado no lead quando teammate manda request.
- [ ] `PlanApprovalDecided` — disparado no teammate quando lead aprova/rejeita ou timeout expira.

### Integração com `TeamRuntime`

- [ ] `TeamPlan` ganha campo `mailbox_enabled: bool = False` (default off para retrocompatibilidade com spec 015 + 016).
- [ ] Quando `mailbox_enabled=True`, `TeamRuntime` instancia `MailboxStore` per-team-run e registra as 6 tools acima.
- [ ] Loop principal de cada teammate (com mailbox + task list) passa a ser:
  ```
  while not team_cancelled:
      message = await inbox.next(timeout=idle_threshold)
      if message: process_message_or_let_agent_decide()
      elif task = await task_list.claim(labels=...): execute_task()
      else: emit TeammateIdle; if all_teammates_idle: break
  ```
- [ ] Plan approval: chamada `request_plan_approval` envia `MailMessage(kind="plan_approval_request")` ao lead com `correlation_id` novo; teammate suspende via `anyio.move_on_after(timeout)`; aprovação/rejeição do lead emite mensagem com mesmo `correlation_id`; teammate retorna o veredito.

### Novos `EventType`

- [ ] `MESSAGE_SENT`, `MESSAGE_DELIVERED`, `INBOX_DRAINED`
- [ ] `PLAN_APPROVAL_REQUESTED`, `PLAN_APPROVAL_GRANTED`, `PLAN_APPROVAL_DENIED`, `PLAN_APPROVAL_TIMED_OUT`
- [ ] `TEAMMATE_IDLE` (substitui heurística de polling da spec 016 quando mailbox ativo)
- [ ] Payloads incluem `team_run_id`, `from_agent`, `to_agent`, `correlation_id?`.

### Configuração declarativa

- [ ] `miniautogen.yaml`:
  ```yaml
  teams:
    review_team:
      lead: orchestrator
      teammates: [legal, security, architect]
      mailbox_enabled: true
      task_list:
        enabled: true
      plan_approval:
        timeout_seconds: 300
        required_for:  # opcional: lista de tools que disparam approval automaticamente
          - shell_command
          - file_write
  ```
- [ ] Quando `plan_approval.required_for` lista uma tool, o `AgentRuntime` (via interceptor canônico, não código novo no runtime) sinaliza request antes da execução. **Decisão pendente para o plano:** se isso pode ser um `RuntimeInterceptor` existente ou exige hook novo.

### Concorrência e correctness

- [ ] Ordem FIFO de entrega por destinatário garantida (mesmo com vários remetentes concorrentes).
- [ ] Plan approval com timeout: teammate **não** fica suspenso indefinidamente; após timeout, recebe `"timeout"` e segue.
- [ ] Cancelamento do team: todos os `receive_stream` são fechados; `request_plan_approval` em flight retorna via `Cancelled` (não `timeout`); inboxes drenadas e descartadas.

### Testes (Test-First, AnyIO)

- [ ] `tests/core/runtime/test_mailbox_basic.py` — send/receive ordem FIFO; `pending_count`; `peek` é não destrutivo.
- [ ] `tests/core/runtime/test_mailbox_concurrent_senders.py` — 5 senders concorrentes para 1 inbox; ordem preservada por timestamp + tiebreak determinístico.
- [ ] `tests/core/runtime/test_plan_approval_granted.py` — teammate pede aprovação; lead aprova via tool; teammate recebe `"granted"`.
- [ ] `tests/core/runtime/test_plan_approval_denied.py` — lead rejeita com razão; teammate vê `"denied"` + razão.
- [ ] `tests/core/runtime/test_plan_approval_timeout.py` — lead nunca responde; teammate recebe `"timeout"` dentro de `timeout_seconds + 100ms`.
- [ ] `tests/core/runtime/test_teammate_idle_hook.py` — teammate com inbox vazia + task list vazia dispara `TeammateIdle`; chegada de mensagem cancela o estado idle.
- [ ] `tests/core/runtime/test_team_runtime_full.py` — E2E: time de 3 teammates + lead + task list + mailbox + 1 plan approval — todos completam, event log canônico reconstrutível.
- [ ] `tests/core/runtime/test_mailbox_cancellation.py` — cancelar team com inboxes pendentes não vaza streams AnyIO.

---

## Invariantes Afetadas

- [x] **Isolamento de Adapters** — `MailboxStore` puro.
- [x] **Microkernel** — sem novo runtime; estende `TeamRuntime`.
- [x] **Assincronismo Canônico (AnyIO)** — `MemoryObjectStream` / `move_on_after`; zero `threading`.
- [x] **Policies Event-Driven** — Plan approval e idle detection são reações a eventos, não policies novas (reutiliza `RuntimeInterceptor` se possível para o gate de tools sensíveis).

---

## Dependências

| Dependência                                | Tipo     | Estado            |
|--------------------------------------------|----------|-------------------|
| `TeamRuntime` + `TaskListStore`            | Interna  | Specs 015 e 016 entregues |
| `StoreProtocol`                            | Interna  | Pronta            |
| `BuiltinToolRegistry`                      | Interna  | Pronta — estender |
| `AgentHook` / `RuntimeInterceptor`         | Interna  | Pronta — possivelmente estender |
| `anyio.create_memory_object_stream`, `move_on_after` | Externa | Já em uso |

---

## Arquitetura proposta (alto nível)

```
miniautogen/
├── core/
│   ├── contracts/
│   │   ├── team_message.py         # NOVO — MailMessage, PlanApprovalRequest
│   │   └── agent_hook.py           # estendido — TeammateIdle, MessageReceived, PlanApproval*
│   └── runtime/
│       ├── team_runtime.py         # estendido — instancia MailboxStore quando enabled
│       ├── team_mailbox.py         # NOVO — InMemoryMailboxStore
│       └── builtin_tools.py        # estendido — send_message/inbox_*/request_plan_approval/approve_plan/reject_plan
└── schemas.py                       # estendido — MailboxConfig, PlanApprovalConfig
```

**Boundary:** `team_mailbox.py` importa apenas de `core/contracts/`, `anyio`, stdlib, `observability`.

---

## Notas Adicionais

### Por que peer-dirigido (não broadcast) na v1?

Broadcast (`send_to_all`) é trivialmente derivável de N peer-sends, mas tem cuidados próprios (deduplicação, idempotência). Mantemos o primitivo simples e adicionamos broadcast só quando aparecer caso de uso real. Reduz superfície de bug.

### Plan approval vs interceptor

Idealmente, `plan_approval.required_for: [shell_command]` é um `RuntimeInterceptor` que, antes da execução de uma tool sensível, dispara `request_plan_approval` automaticamente. Isso evita prompt-engineering frágil ("você deve pedir aprovação antes de..."). Decisão técnica fica para o `plan.md` desta spec — pode ser feita com `EffectInterceptor` existente.

### Idle threshold vs polling

Spec 016 usava polling com threshold de 5s para detectar fim do team run. Esta spec substitui pela combinação: cada teammate emite `TeammateIdle` quando seu loop principal não tem trabalho; `TeamRuntime` mantém set de teammates idle; quando o set cobre todos → fim do team run. Determinístico, sem latência artificial.

### Quality gates declarativos (fora de escopo, mas considerados)

Claude Code Agent Teams permite gates como "task só completa se tem teste". Equivalente em MiniAutoGen seria: tarefa com `acceptance_criteria` que o lead valida antes de aceitar `task_complete`. Pode ser modelado com:
- `task_complete(task_id, summary)` no teammate
- Hook `TaskCompletionRequested` → lead valida → `task_complete_confirmed`/`task_rejected`

Não entra nesta spec — fica como Future Work se demanda aparecer. Para o caso comum, o lead pode simplesmente conferir o `result_summary` e dar feedback via mailbox sem precisar de gate formal.

### Future Work (fora deste ciclo)

- **`SqlAlchemyMailboxStore`** para retomada cross-process.
- **Broadcast com fan-out** (`send_to_all_except`, `send_to_role`).
- **Mailbox compactação** — quando histórico cresce demais, lead resume.
- **Quality gates declarativos** no YAML, conforme nota acima.
- **TUI in-process** com alternância entre teammates (`Shift+Down`) inspirada no Claude Code — extensão do Rich Live (PR #44) em spec/PR separado.
- **Composição** — time dentro de step de workflow consumindo mailbox do workflow pai (atravessa fronteiras). Caso de uso futuro, validar arquitetura quando aparecer.
