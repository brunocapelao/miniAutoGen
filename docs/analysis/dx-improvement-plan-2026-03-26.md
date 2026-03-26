# Plano de Melhoria DX/UX — MiniAutoGen

**Data:** 2026-03-26
**Foco:** CLI + Web Console + SDK (sem TUI)
**Referência:** Análise competitiva vs TinyAGI, HiClaw, Toone
**Princípio:** "O agente é commodity. O runtime é o produto."

---

## 1. Resumo

Plano para elevar a Developer Experience do MiniAutoGen ao nível dos melhores frameworks do mercado, focando em **3 superfícies**: CLI, Web Console e SDK. O TUI existe mas não é prioridade de investimento.

**Meta:** Um developer deve ir de `pip install miniautogen` a "wow, meus agentes estão conversando" em **≤ 3 minutos**.

---

## 2. Gap Analysis — O que TinyAGI faz melhor (filtrado)

### 2.1 Gaps a implementar

| # | Feature TinyAGI | Estado MiniAutoGen | Prioridade | Superfície |
|---|---|---|---|---|
| G1 | `send` command — mensagem direta ao agente via CLI | Não existe | **P0** | CLI |
| G2 | `chat` command — conversa interativa com agente | Não existe | **P0** | CLI |
| G3 | Console CRUD — criar/editar/deletar agents/flows via web | Read-only | **P0** | Web Console |
| G4 | Init templates — quickstart, minimal, advanced | Só 1 scaffold fixo | **P0** | CLI |
| G5 | Hello-world example — zero a running em 2 min | Só tamagotchi (complexo) | **P0** | Docs/Examples |
| G6 | Settings editor no portal web | Não existe | **P1** | Web Console |
| G7 | Log viewer com streaming no portal web | Não existe | **P1** | Web Console |
| G8 | `status` command global (agentes, runs, server) | Só `server status` | **P1** | CLI |
| G9 | Docker image oficial | Não existe | **P1** | DevOps |
| G10 | Daemon mode como paradigma (start/stop/restart) | `server start --daemon` existe mas não é central | **P1** | CLI |
| G11 | In-chat routing (`@agent_id message`) | Router agent decide, sem input direto | **P2** | SDK |
| G12 | Persistência de conversas entre sessões | Em memória durante run | **P2** | SDK |
| G13 | Heartbeat system (agentes verificam pendências) | Não existe | **P2** | SDK |
| G14 | `update` command (self-update) | Não existe | **P3** | CLI |
| G15 | JSON auto-repair em config corrompido | Não existe | **P3** | CLI |
| G16 | Org chart visual de agents/teams | Não existe | **P3** | Web Console |

### 2.2 Gaps descartados (não alinhados com tese)

| Feature TinyAGI | Razão de exclusão |
|---|---|
| Multi-channel (Discord, Telegram, WhatsApp) | Fora do scope de framework — seria adapter futuro |
| Sender pairing / access control por channel | Dependente de channels |
| Kanban/task boards | Feature de produto, não de framework |
| Chat rooms persistentes entre agentes | AgenticLoopRuntime já resolve isso no runtime |
| TinyOffice como SaaS portal | MiniAutoGen é self-hosted by design |
| Mobile companion | Fora do público-alvo |

### 2.3 O que já temos e é superior

| Feature MiniAutoGen | vs TinyAGI |
|---|---|
| 5 modos de coordenação (workflow, group_chat, loop, debate, deliberation) | TinyAGI tem 2 (chain + fan-out) |
| 72 event types com sinks composáveis | TinyAGI tem ~5 (logs) |
| 3,045 testes automatizados | TinyAGI: N/D |
| Protocol-driven architecture (35+ contratos) | TinyAGI: acoplamento implícito |
| Delegation security (allowlists + depth + circular) | TinyAGI: inexistente |
| Engine discovery e auto-detection | TinyAGI: manual |
| `check` + `doctor` commands | TinyAGI: inexistente |
| Shell completions (bash/zsh/fish) | TinyAGI: inexistente |
| `--explain` flag (dry-run) | TinyAGI: inexistente |
| HITL approval workflow | TinyAGI: inexistente |
| AgenticLoopRuntime (router + stagnation detection) | TinyAGI: broadcast simples |

---

## 3. Plano de Implementação

### Sprint 1 — "Zero to Wow" (P0)

**Objetivo:** Developer instala e interage com agente em ≤ 3 minutos.

#### 3.1 `miniautogen send` — Mensagem direta ao agente

**O que faz:** Envia uma mensagem a um agente e retorna a resposta. Sem criar flow, sem run formal.

```bash
# Uso básico
miniautogen send "Olá, quem é você?" --agent architect

# Com agent padrão (primeiro do workspace)
miniautogen send "Explique a arquitetura do projeto"

# Pipe de stdin
echo "Review this code" | miniautogen send --agent reviewer

# Output JSON
miniautogen send "Analyze this" --agent analyst --format json
```

**Implementação:**
- Novo command em `miniautogen/cli/commands/send.py`
- Resolve o agente pelo nome (ou usa o primeiro do workspace)
- Cria um AgentRuntime temporário, executa 1 turn, retorna resposta
- Emite eventos normalmente (observabilidade mantida)
- Não cria run persistido (a menos que `--persist` flag)

**Arquivos:**
- `miniautogen/cli/commands/send.py` (novo)
- `miniautogen/cli/main.py` (registrar command)
- `miniautogen/cli/services/send_service.py` (novo — lógica de negócio)

**Testes:**
- `tests/cli/test_send_command.py`

---

#### 3.2 `miniautogen chat` — Conversa interativa com agente

**O que faz:** Abre uma sessão de chat interativa no terminal com um agente.

```bash
# Chat com agente específico
miniautogen chat architect

# Chat com agente padrão
miniautogen chat

# Com contexto de flow
miniautogen chat --flow dev-team
```

**Implementação:**
- Novo command em `miniautogen/cli/commands/chat.py`
- Loop de input/output no terminal (sem Textual, apenas `input()` + `click.echo()`)
- Mantém Conversation entre turns (memória de sessão)
- `Ctrl+C` ou `/quit` para sair
- `/clear` para limpar histórico
- `/switch <agent>` para trocar de agente
- Colorização via Click (prompt em verde, resposta em branco, erros em vermelho)

**Arquivos:**
- `miniautogen/cli/commands/chat.py` (novo)
- `miniautogen/cli/main.py` (registrar command)
- `miniautogen/cli/services/chat_service.py` (novo)

**Testes:**
- `tests/cli/test_chat_command.py`

---

#### 3.3 Console CRUD — Criar/editar/deletar agents e flows via web

**O que faz:** Adiciona endpoints de escrita à API e formulários ao frontend.

**Backend — Novos endpoints:**

```
POST   /api/v1/agents          # Criar agente
PUT    /api/v1/agents/{name}   # Atualizar agente
DELETE /api/v1/agents/{name}   # Deletar agente

POST   /api/v1/flows           # Criar flow
PUT    /api/v1/flows/{name}    # Atualizar flow
DELETE /api/v1/flows/{name}    # Deletar flow

PUT    /api/v1/workspace       # Atualizar config do workspace
```

**Implementação backend:**
- Expandir `ConsoleDataProvider` protocol com métodos de escrita
- Implementar em `StandaloneProvider`: read/write YAML atômico (write to .tmp → rename)
- Validação Pydantic nos payloads de entrada
- Backup automático antes de write (`.bak`)

**Frontend — Novos componentes:**

| Componente | Página | Funcionalidade |
|---|---|---|
| `AgentForm` | `/agents/new`, `/agents/edit?name=X` | Formulário de criação/edição de agente |
| `FlowForm` | `/flows/new`, `/flows/edit?name=X` | Formulário de criação/edição de flow |
| `WorkspaceSettings` | `/settings` | Editor de configurações do workspace |
| `DeleteConfirmModal` | Reutilizável | Modal de confirmação de exclusão |
| `AgentDetailPage` | `/agents/detail?name=X` | Página de detalhe do agente (falta hoje) |

**Arquivos backend:**
- `miniautogen/server/provider_protocol.py` (expandir protocol)
- `miniautogen/server/standalone_provider.py` (implementar writes)
- `miniautogen/server/routes/agents.py` (adicionar POST/PUT/DELETE)
- `miniautogen/server/routes/flows.py` (adicionar POST/PUT/DELETE)
- `miniautogen/server/routes/workspace.py` (adicionar PUT)

**Arquivos frontend:**
- `console/app/agents/new/page.tsx` (novo)
- `console/app/agents/detail/page.tsx` (novo)
- `console/app/agents/edit/page.tsx` (novo)
- `console/app/flows/new/page.tsx` (novo)
- `console/app/flows/edit/page.tsx` (novo)
- `console/app/settings/page.tsx` (novo)
- `console/components/AgentForm.tsx` (novo)
- `console/components/FlowForm.tsx` (novo)
- `console/components/DeleteConfirmModal.tsx` (novo)

**Testes:**
- `tests/server/test_agents_crud.py`
- `tests/server/test_flows_crud.py`
- `console/__tests__/agents-crud.test.tsx`
- `console/__tests__/flows-crud.test.tsx`

---

#### 3.4 Init templates — quickstart, minimal, advanced

**O que faz:** `miniautogen init` oferece escolha de template.

```bash
# Interativo (prompt de seleção)
miniautogen init my-project

# Direto
miniautogen init my-project --template quickstart
miniautogen init my-project --template minimal
miniautogen init my-project --template advanced
miniautogen init my-project --from-example tamagotchi-dev-team
```

**Templates:**

| Template | Conteúdo | Caso de uso |
|---|---|---|
| `quickstart` (default) | 1 agente, 1 flow (workflow), README com "next steps" | Primeiro contato |
| `minimal` | Só miniautogen.yaml + .env, sem exemplos | Developer experiente |
| `advanced` | 3 agentes, 2 flows (workflow + deliberation), skills, tools | Projetos reais |

**Implementação:**
- Novos diretórios de template em `miniautogen/cli/templates/`
- `--template` flag no `init` command
- `--from-example` copia de `examples/` e adapta
- Template `quickstart` gera README.md com walkthrough

**Arquivos:**
- `miniautogen/cli/templates/quickstart/` (novo)
- `miniautogen/cli/templates/minimal/` (novo)
- `miniautogen/cli/templates/advanced/` (novo)
- `miniautogen/cli/commands/init.py` (modificar)
- `miniautogen/cli/services/init_project.py` (modificar)

**Testes:**
- `tests/cli/test_init_templates.py`

---

#### 3.5 Hello-world example + Quickstart guide

**O que faz:** Exemplo mínimo que funciona em 2 minutos + guia passo-a-passo.

```bash
pip install miniautogen
miniautogen init hello --template quickstart
cd hello
export OPENAI_API_KEY=sk-...
miniautogen send "Hello! What can you do?" --agent assistant
```

**Conteúdo:**

1. `examples/hello-world/` — Projeto mínimo com 1 agente
2. `examples/hello-world/README.md` — Guia de 5 passos
3. `examples/dev-team/` — Renomear tamagotchi para nome mais genérico

**Arquivos:**
- `examples/hello-world/` (novo)
- `examples/hello-world/miniautogen.yaml`
- `examples/hello-world/agents/assistant.yaml`
- `examples/hello-world/.env.example`
- `examples/hello-world/README.md`

---

### Sprint 2 — "Dashboard Completo" (P1)

**Objetivo:** Web console com todas as features de gestão.

#### 3.6 Settings editor no portal web

**O que faz:** Página `/settings` para editar `miniautogen.yaml` visualmente.

- Editor de engines (criar, editar, deletar engine profiles)
- Editor de defaults (engine, memory profile)
- Editor de database config
- Visualização do .env (read-only, sem expor secrets)

**Endpoints:**
```
GET  /api/v1/engines          # Listar engines
POST /api/v1/engines          # Criar engine
PUT  /api/v1/engines/{name}   # Atualizar engine
DELETE /api/v1/engines/{name} # Deletar engine
GET  /api/v1/config           # Config geral (read-only view)
```

---

#### 3.7 Log viewer com streaming no portal web

**O que faz:** Página `/logs` com streaming de eventos em tempo real.

- Filtro por tipo de evento, agente, flow, run
- Auto-scroll com pause on hover
- Severity badges (info, warning, error)
- Export para JSON

**Implementação:**
- WebSocket endpoint `/ws/events` (global, não por run)
- Componente `EventStream` com virtualização para performance
- Filtros via query params

---

#### 3.8 `miniautogen status` — Status global

**O que faz:** Mostra estado completo do workspace em um comando.

```bash
$ miniautogen status

Workspace: my-project (v0.1.0)
Server:    ● running on :8080
Agents:    4 configured (architect, developer, tester, lead)
Engines:   2 configured (openai-gpt4, gemini-cli)
Flows:     2 configured (dev-workflow, code-review)
Runs:      12 total (10 completed, 1 running, 1 failed)
Last run:  dev-workflow — completed 2h ago
```

**Implementação:**
- Novo command em `miniautogen/cli/commands/status.py`
- Agrega info de config, server, runs store
- Colorizado com Click

---

#### 3.9 Docker image oficial

**O que faz:** Imagem Docker para deploy rápido.

```bash
docker run -v $(pwd):/workspace -e OPENAI_API_KEY=sk-... \
  miniautogen/miniautogen console --host 0.0.0.0
```

**Arquivos:**
- `Dockerfile` (novo)
- `docker-compose.yml` (novo)
- `.dockerignore` (novo)

---

#### 3.10 Daemon mode refinado

**O que faz:** `miniautogen` como serviço background com start/stop/restart/status.

```bash
miniautogen daemon start          # Inicia API server + event processing
miniautogen daemon stop           # Para o daemon
miniautogen daemon restart        # Reinicia
miniautogen daemon status         # Mostra se está rodando
miniautogen daemon logs           # Streaming de logs do daemon
miniautogen daemon logs --follow  # Tail -f
```

**Diferença do atual `server start --daemon`:**
- `daemon` é um conceito de primeiro nível, não sub-command de `server`
- Inclui log rotation e PID file management
- `logs` com `--follow` para streaming

---

### Sprint 3 — "Framework Completo" (P2)

#### 3.11 In-chat routing (`@agent_id`)

**O que faz:** No `miniautogen chat`, permitir routing direto:

```
You: @architect Design a REST API for user management
Architect: Here's my proposal...

You: @reviewer Review the architect's proposal
Reviewer: Looking at the design...
```

**Implementação:**
- Parser de `@agent_id` no chat service
- Resolve para o agente correto do workspace
- Mantém conversation context compartilhado

---

#### 3.12 Persistência de conversas

**O que faz:** Conversas do `chat` e `send` são persistidas entre sessões.

```bash
# Retomar conversa anterior
miniautogen chat architect --resume

# Listar sessões de chat
miniautogen sessions list --type chat

# Limpar
miniautogen sessions clean --type chat
```

**Implementação:**
- Extend `RunStore` para suportar tipo "chat_session"
- Serializar/deserializar `Conversation` para SQLite
- `--resume` flag nos commands `chat` e `send`

---

#### 3.13 Heartbeat system

**O que faz:** Agentes podem ter tarefas periódicas.

```yaml
# agents/monitor.yaml
id: monitor
name: System Monitor
heartbeat:
  interval: 3600  # a cada hora
  prompt: "Check for pending tasks and report status"
  enabled: true
```

**Implementação:**
- Background task no daemon que executa heartbeats
- Resultados persistidos como runs do tipo "heartbeat"
- Visíveis no console web

---

### Sprint 4 — "Polish" (P3)

#### 3.14 `miniautogen update`

```bash
miniautogen update          # pip install --upgrade miniautogen
miniautogen update --check  # Só verifica se há update
```

#### 3.15 Config auto-repair

- Detectar YAML inválido em `miniautogen.yaml` e `agents/*.yaml`
- Criar `.bak` antes de tentar repair
- Reportar o que foi corrigido

#### 3.16 Org chart visual

- Página `/org` no web console
- Visualização de agentes + flows em grafo
- Baseado no `FlowCanvas` existente

---

## 4. Estimativa de Esforço

| Sprint | Items | Esforço estimado | Impacto |
|---|---|---|---|
| **Sprint 1** (P0) | G1-G5: send, chat, console CRUD, templates, hello-world | 3-4 dias | Crítico — define adoção |
| **Sprint 2** (P1) | G6-G10: settings, logs, status, Docker, daemon | 3-4 dias | Alto — completa a experiência |
| **Sprint 3** (P2) | G11-G13: routing, persistência, heartbeat | 2-3 dias | Médio — diferencial SDK |
| **Sprint 4** (P3) | G14-G16: update, auto-repair, org chart | 1-2 dias | Baixo — polish |
| **Total** | 16 items | **~10-13 dias** | |

---

## 5. Critérios de Sucesso

| Métrica | Target |
|---|---|
| Time-to-first-interaction | ≤ 3 min (install → send → response) |
| Time-to-dashboard | ≤ 5 min (install → init → console → visualizing) |
| Web console coverage | CRUD para agents, flows, engines, settings |
| CLI coverage | send, chat, status, daemon — sem precisar do web |
| Zero regression | 3,045+ testes passando após cada sprint |
| Documentação | README + quickstart + hello-world example |

---

## 6. Princípios de Design

1. **CLI-first, Web-second:** Tudo que o web console faz, a CLI também faz. O web é visualização, não dependência.
2. **Sem TUI investment:** O TUI (Textual) existe e funciona, mas não é prioridade. Investir em CLI puro e Web Console.
3. **Framework, não produto:** Não vamos implementar channels (Discord/Telegram), Kanban boards, ou mobile apps. Somos SDK.
4. **Observabilidade mantida:** Todo novo command emite eventos canônicos. `send` e `chat` geram ExecutionEvents rastreáveis.
5. **Backward compatible:** Nenhuma mudança breaking. Novos commands e endpoints são aditivos.

---

*Plano criado em 2026-03-26. Referência: docs/analysis/competitive-analysis-2026-03-26.md*
