# Especificação: TeamRuntime — coordenação peer-to-peer estilo Agent Teams

| Campo      | Valor                          |
|------------|--------------------------------|
| Data       | 2026-05-16                     |
| Autor      | Bruno Capelão                  |
| Status     | Rascunho                       |
| Spec ID    | 015                            |

---

## Contrato de Prompt (G/C/FC)

### 🎯 Goal (Objetivo)

Introduzir um novo `CoordinationKind.TEAM` e um `TeamRuntime` correspondente que executa **N agentes peer concorrentemente** sob um "team lead", inspirado em Claude Code Agent Teams. Cada teammate roda como `AgentRuntime` isolado, com contexto fresh (não herda histórico do lead), e contribui para um objetivo comum. O lead consolida ao final.

Esta spec entrega o **núcleo síncrono mínimo**: bootstrap do time, execução paralela de teammates, ciclo de vida e eventos canônicos. **Task list compartilhada** (spec 016) e **mailbox peer-to-peer** (spec 017) ficam em specs seguintes — não são pré-requisito desta.

**Não-objetivo deste ciclo:**
- Comunicação direta entre teammates (mailbox) → spec 017.
- Kanban compartilhado com claim/dependências → spec 016.
- Plan approval e hooks `TeammateIdle`/`TaskCreated` → spec 017.
- Split panes (tmux/iTerm2) → fora de escopo; wrapper externo opcional pós-MVP.
- Persistência/retomada de team runs entre processos → fora de escopo MVP.

### 🚧 Constraint (Restrição)

1. **Isolamento de Adapters preservado.** `TeamRuntime` vive em `miniautogen/core/runtime/team_runtime.py`, depende apenas de protocolos de `core/contracts/*`. Nada de SDK externo (LiteLLM, Gemini, etc.) é importado direto.
2. **Microkernel / PipelineRunner.** Cada teammate é instanciado via o caminho canônico (`AgentRuntime` + `PipelineRunner` interno se aplicável). Não há executor paralelo customizado — concorrência é via `anyio.create_task_group`.
3. **AnyIO end-to-end.** `TeamRuntime.run` é `async`. Cancelamento estruturado: cancelar o team cancela todos os teammates em flight via escopo aninhado.
4. **Eventos canônicos.** Novos `EventType` (`TEAM_STARTED`, `TEAMMATE_SPAWNED`, `TEAMMATE_FINISHED`, `TEAM_FINISHED`, `TEAM_FAILED`) emitidos com `parent_run_id` apontando para o `run_id` do team. Sub-runs dos teammates carregam `parent_run_id` no `RunContext`.
5. **Erros taxonomizados.** Falha de teammate isolado → `ErrorCategory` herdada do AgentRuntime; falha de bootstrap do team → `ErrorCategory.CONFIGURATION`; cancelamento estruturado → `ErrorCategory.CANCELLATION` propagada sem mascarar.
6. **Sem hardcoded prompts no runtime.** Per regra §3.5 do CLAUDE.md: `TeamRuntime` é compositor, não instrutor. Prompts do lead/teammates vêm 100% do YAML / `TeamPlan`.

### 🛑 Failure Condition (Condição de Falha)

A implementação **falhou** se, ao fim do ciclo, qualquer um for verdadeiro:

1. Executar um `TeamPlan` com 3 teammates **não produz** os 3 sub-runs concorrentes observáveis por `parent_run_id` nos eventos.
2. Cancelar o team run (via `CancelScope` ou `cancel_run` futuro) **não cancela** todos os teammates em até 1s — vazamento de tasks.
3. Um teammate que falha (`ValidationError`, `TimeoutError`) **derruba** os demais sem que isso seja a política configurada — falha de isolamento.
4. Existe import de `litellm.*`, `google.generativeai`, ou qualquer adapter dentro de `team_runtime.py`.
5. `pytest tests/core/runtime/test_team_runtime.py` falha ou cobertura do módulo < 85%.
6. Algum teammate **vê** mensagens do histórico do lead que não foram explicitamente passadas no seu prompt inicial — quebra de isolamento de contexto.
7. `skills/run_anyio_tests.sh` regride após a introdução do runtime.

---

## User Stories

- Como **engenheiro de IA**, quero declarar um time no `miniautogen.yaml` com um lead e 3 teammates especialistas (e.g. compliance, arquiteto, auditor) e disparar `miniautogen team run <team_name>` para que eles trabalhem em paralelo sobre o mesmo briefing — sem precisar codar coordenação manual.
- Como **operador de CI**, quero que um time experimental falhe em isolamento (1 teammate quebra, demais terminam normalmente) e o lead receba contexto suficiente do que aconteceu para gerar um parecer parcial — para que pipelines críticos não morram com falha pontual.
- Como **arquiteto MiniAutoGen**, quero que `TeamRuntime` se encaixe na taxonomia de `CoordinationKind` existente (`WORKFLOW`, `DELIBERATION`, `AGENTIC_LOOP` + novo `TEAM`) para que seja composável via `CompositeRuntime` (e.g. workflow → team → workflow) sem casos especiais.
- Como **observador**, quero que cada evento do team carregue `parent_run_id` para reconstruir a árvore lead→teammates a partir do event log, sem inferência baseada em timestamps.

---

## Critérios de Aceitação

### Contratos novos

- [ ] `CoordinationKind.TEAM = "team"` adicionado em `core/contracts/coordination.py`.
- [ ] `TeamPlan(CoordinationPlan)` declarado com campos:
  - `lead_agent: str` — nome do agente lead
  - `teammates: list[str]` — nomes dos agentes teammates (sem duplicatas; lead não pode estar na lista)
  - `lead_prompt: str | None` — prompt inicial para o lead
  - `teammate_prompts: dict[str, str]` — prompt inicial por teammate (chave = nome do agent)
  - `on_teammate_failure: Literal["isolate", "abort_team"] = "isolate"` — política em caso de falha de um teammate
  - `max_concurrent_teammates: int | None = None` — limita paralelismo via semáforo opcional
- [ ] `TeamRuntime` implementa `CoordinationMode[TeamPlan]` com `kind = CoordinationKind.TEAM`.
- [ ] Cada teammate recebe `RunContext` filho com `parent_run_id = team_run_context.run_id`.

### Novos `EventType`

- [ ] `TEAM_STARTED` — payload: `{lead, teammates, team_run_id}`
- [ ] `TEAMMATE_SPAWNED` — payload: `{teammate, sub_run_id, parent_run_id}`
- [ ] `TEAMMATE_FINISHED` — payload: `{teammate, sub_run_id, status, summary?}`
- [ ] `TEAMMATE_FAILED` — payload: `{teammate, sub_run_id, error_category, message}`
- [ ] `TEAM_FINISHED` — payload: `{team_run_id, status, lead_summary?}`
- [ ] `TEAM_FAILED` — payload: `{team_run_id, error_category, message}`
- [ ] Todos os eventos `TEAM_*` aparecem na lista canônica e são serializáveis via `ExecutionEvent.model_dump()`.

### Comportamento de execução

- [ ] Teammates rodam concorrentes via `anyio.create_task_group`; ordem de finalização não é prescrita.
- [ ] Lead roda **depois** dos teammates (na v1) e recebe no seu contexto um resumo estruturado das contribuições dos teammates (formato `dict[teammate_name, ContributionSummary]`).
- [ ] `on_teammate_failure="isolate"` → teammates restantes continuam; lead vê o erro do teammate falho marcado no resumo.
- [ ] `on_teammate_failure="abort_team"` → primeira falha cancela o task group; lead **não** roda; `TEAM_FAILED` é emitido.
- [ ] Cancelamento externo do team run propaga via `CancelScope` para todos os teammates ativos; `TEAMMATE_FINISHED` com `status="cancelled"` é emitido para cada um.

### Configuração declarativa

- [ ] `miniautogen.yaml` ganha schema `teams:` (sibling de `flows:`), validado por Pydantic:
  ```yaml
  teams:
    review_team:
      lead: orchestrator
      teammates: [legal_reviewer, security_reviewer, architect_reviewer]
      on_teammate_failure: isolate
  ```
- [ ] CLI `miniautogen run <team_name>` aceita um team como argumento de mesmo nível que flows (resolve por nome no YAML).
- [ ] Flag experimental: `MINIAUTOGEN_EXPERIMENTAL_TEAMS=1` é exigida pela CLI para habilitar `team run`; sem ela, falha com mensagem clara apontando para a flag. Default desabilitado segue prática do Claude Code.

### Isolamento de contexto

- [ ] Cada teammate inicia com `Conversation` vazia (não recebe o histórico do lead) — apenas o `teammate_prompt` específico + contexto de projeto (`miniautogen.yaml`, tools próprias, MCP bindings, skills).
- [ ] Teste explícito: lead envia mensagem `"SEGREDO"` ao seu próprio context antes de spawn; nenhum teammate consegue ler essa string no seu `Conversation`.

### Testes (Test-First, AnyIO)

- [ ] `tests/core/runtime/test_team_runtime_bootstrap.py` — instanciação do runtime e validação do `TeamPlan` (lead não duplicado, teammates únicos).
- [ ] `tests/core/runtime/test_team_runtime_parallel.py` — 3 teammates de sleep diferentes (100ms, 200ms, 300ms) completam em ≤ ~350ms (paralelismo real).
- [ ] `tests/core/runtime/test_team_runtime_isolation.py` — teste do segredo (acima); nenhum teammate vê histórico do lead.
- [ ] `tests/core/runtime/test_team_runtime_failure_isolate.py` — 1 de 3 teammates levanta exceção; outros 2 completam; lead recebe resumo com erro do falho.
- [ ] `tests/core/runtime/test_team_runtime_failure_abort.py` — `on_teammate_failure="abort_team"` aborta task group; lead não roda; `TEAM_FAILED` emitido.
- [ ] `tests/core/runtime/test_team_runtime_cancellation.py` — cancelamento externo propaga via AnyIO em <1s; todos os teammates emitem `cancelled`.
- [ ] `tests/core/runtime/test_team_runtime_events.py` — ordem canônica: `TEAM_STARTED` → N×`TEAMMATE_SPAWNED` → N×`TEAMMATE_FINISHED` → `TEAM_FINISHED`. Cada evento tem `parent_run_id` correto.
- [ ] `tests/cli/test_team_command.py` — `miniautogen run <team_name>` resolve YAML, dispara runtime, retorna `RunResult` coerente; flag experimental gate funciona.

---

## Invariantes Afetadas

- [x] **Isolamento de Adapters** — `team_runtime.py` não importa adapters concretos.
- [x] **Microkernel / PipelineRunner** — teammates são `AgentRuntime`s standard; concorrência via AnyIO task group, não loop paralelo.
- [x] **Assincronismo Canônico (AnyIO)** — runtime é `async`, cancelamento estruturado.
- [ ] **Policies Event-Driven** — não introduz policies novas; reutiliza emissão atual via `EventSink`.

Notas sobre invariantes:

> `TeamRuntime` segue o padrão dos runtimes existentes (`WorkflowRuntime`, `DeliberationRuntime`, `AgenticLoopRuntime`). A concorrência é a única adição estrutural — implementada via `anyio.create_task_group`, que é o primitivo canônico do projeto para paralelismo estruturado. Spawning de sub-runs reusa `AgentRuntime` direto (não há `SubAgentTool` aqui — isso fica como abstração interna do runtime, não exposta como tool).

---

## Dependências

| Dependência                                       | Tipo     | Estado      |
|---------------------------------------------------|----------|-------------|
| `AgentRuntime` (`core/runtime/agent_runtime.py`)  | Interna  | Pronta      |
| `RunContext` com `parent_run_id`                  | Interna  | **A estender** — pode ser que `parent_run_id` ainda não exista no campo |
| `CoordinationKind`, `CoordinationPlan`            | Interna  | Pronta — estender enum |
| `EventSink` / `ExecutionEvent`                    | Interna  | Pronta — adicionar novos `EventType` |
| `anyio.create_task_group`                         | Externa  | Já em uso   |
| CLI runner `cli/services/run_pipeline`            | Interna  | A estender para resolver `teams:` no YAML além de `flows:` |

---

## Arquitetura proposta (alto nível)

```
miniautogen/
├── core/
│   ├── contracts/
│   │   ├── coordination.py       # +CoordinationKind.TEAM, +TeamPlan
│   │   ├── run_context.py        # +parent_run_id: str | None (se não existir)
│   │   └── events.py             # +TEAM_* EventTypes
│   └── runtime/
│       └── team_runtime.py       # NOVO — TeamRuntime
├── cli/
│   ├── commands/run.py           # ajustar para resolver team OR flow por nome
│   └── services/
│       └── run_pipeline.py       # ajustar para despachar TeamPlan
└── schemas.py                     # +teams: schema no miniautogen.yaml
```

**Boundary:** `team_runtime.py` importa apenas de `core/contracts/`, `core/events/`, `anyio`, stdlib, `observability`. Zero adapters.

---

## Mapa lead/teammate vs Claude Code Agent Teams

| Claude Code | MiniAutoGen (esta spec) | Spec futura |
|---|---|---|
| Team lead | `TeamPlan.lead_agent` (roda **depois** dos teammates na v1) | Lead poderá rodar **antes** + delegar via task list (016) |
| Teammates | `TeamPlan.teammates`, cada um `AgentRuntime` isolado, concorrente | Mantém |
| Task list | Resumo estático passado ao lead (sem claim/deps) | 016 introduz `TaskListStore` |
| Mailbox peer-to-peer | Não existe nesta versão | 017 introduz `MailboxStore` |
| Plan approval | Não existe | 017 |
| Hooks `TeammateIdle` etc. | Não existe (teammates terminam após prompt inicial) | 017 |
| In-process switch | CLI mostra logs unificados; ainda sem alternância interativa | TUI Rich em fase 2 |

Esta v1 é deliberadamente **mais simples** que Agent Teams completo: teammates rodam um turno, lead consolida. É o esqueleto sobre o qual 016 e 017 adicionam o resto.

---

## Notas Adicionais

### Por que lead-depois-dos-teammates na v1?

Reproduz o padrão "fan-out + consolidação" que é o uso predominante de Agent Teams para tarefas de revisão/análise. Lead-antes (delegação ativa) exige uma task list compartilhada e ciclos de ida-e-volta, que dependem da spec 016. Adiar não bloqueia o MVP útil.

### Por que `parent_run_id` em vez de `team_run_id`?

`parent_run_id` é genérico — funciona para teams aninhados (team dentro de team), composições via `CompositeRuntime`, e futuros sub-agentes invocados como tool. Um campo específico `team_run_id` engessaria.

### Flag experimental

Seguindo o padrão de Claude Code (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`), MiniAutoGen usa `MINIAUTOGEN_EXPERIMENTAL_TEAMS=1`. CLI rejeita `miniautogen run <team>` se o YAML resolver para `teams:` e a env var não estiver setada. Mensagem aponta para docs/migração quando estabilizado.

### Future Work (fora deste ciclo)

- **Spec 016** — `TaskListStore`, kanban compartilhado, tools `task_claim`/`task_complete`, hooks `TaskCreated`/`TaskCompleted`. Habilita lead-antes-dos-teammates com delegação dinâmica.
- **Spec 017** — `MailboxStore` (peer-to-peer), tool `send_message(to_teammate, content)`, hook `TeammateIdle`, plan approval gate.
- **TUI in-process** — extensão do Rich Live (PR #44) para mostrar status do time (qual teammate está ativo, alternância com `Shift+Down`).
- **Composição** — uso de `TeamRuntime` como step de `WorkflowRuntime` (e.g. workflow → team → workflow). Já habilitado pela arquitetura; testar explicitamente em ciclo separado.
