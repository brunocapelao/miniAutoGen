# MiniAutoGen — Análise Competitiva do Landscape de Orquestradores

**Frameworks analisados:** Claude Code, Kimi CLI, OpenClaw, ChatDev 2.0, Agno (ex-Phidata), OpenHands (ex-OpenDevin), LangGraph, CrewAI

---

## 1. Taxonomia do Mercado

Antes de comparar, é preciso entender que estes frameworks **não competem todos na mesma categoria**. O mercado de orquestração de agentes se divide em três segmentos distintos:

| Segmento | Descrição | Frameworks |
|---|---|---|
| **Coding Agents** | Agente único com tool-use para tarefas de desenvolvimento | Claude Code, Kimi CLI, OpenHands |
| **Multi-Agent Platforms** | Orquestração de múltiplos agentes com coordenação | ChatDev, Agno, CrewAI, LangGraph |
| **Personal AI Hubs** | Gateway multi-canal com routing para agentes | OpenClaw |

**MiniAutoGen compete no segmento Multi-Agent Platforms**, mas com ambição de ser um **runtime/SDK** (não um produto end-user como ChatDev ou OpenHands).

---

## 2. Análise Individual

### 2.1 Claude Code (Anthropic)

**Categoria:** Coding Agent (single-agent com tool-use avançado)

**Modelo de orquestração:**
- Agente único (Claude) com decisão autônoma sobre ferramentas
- Sem multi-agente — é o modelo como orquestrador de si mesmo
- Extensibilidade via hooks (pre/post tool call), MCP servers, e custom commands
- Subagents: spawna instâncias de si mesmo para tarefas paralelas isoladas

**Composição:**
- Hooks em `settings.json` → shell commands executados em eventos
- MCP servers → ferramentas externas expostas via protocol
- Custom slash commands → prompts reutilizáveis
- Plugins → extensões de funcionalidade

**Paralelismo:**
- Subagents em worktrees isolados (git worktree)
- Sem fan-out dinâmico — é o operador humano que decide quando spawnar subagents

**Forças:** UX excepcional, integração profunda com git/IDE, hooks como middleware leve
**Fraquezas:** Sem multi-agente real, sem coordenação entre subagents, sem planos de execução declarativos

**Relevância para MiniAutoGen:** O pattern de **hooks** é simples e poderoso. MiniAutoGen já tem algo superior (EventSink + interceptors propostos), mas a simplicidade dos hooks do Claude Code é um benchmark de DX.

---

### 2.2 Kimi CLI (Moonshot AI)

**Categoria:** Coding Agent (single-agent, inspirado no Claude Code)

**Modelo de orquestração:**
- Agente único com tool-use (shell, browser, filesystem)
- Sem multi-agente
- Extensível via MCP servers e ACP (Agent Client Protocol)
- Pode ser consumido como ACP server por IDEs

**Composição:**
- MCP tools como plugins
- ACP para integração bidirecional
- Sem flow, sem middleware, sem interceptors

**Paralelismo:** Nenhum documentado.

**Forças:** Suporte nativo a ACP, integração com ecossistema chinês de LLMs
**Fraquezas:** Zero orquestração multi-agente, sem abstrações de coordenação

**Relevância para MiniAutoGen:** O suporte a **ACP como protocol de exposição** é interessante. MiniAutoGen já tem `AgentDriver` que poderia expor agents via ACP. Convergência de protocols é uma tendência.

---

### 2.3 OpenClaw

**Categoria:** Personal AI Hub (gateway multi-canal + orquestração 24/7)

> Análise enriquecida com caso real documentado em [The Unwind AI — "How I Built an Autonomous AI Agent Team That Runs 24/7"](https://www.theunwindai.com/p/how-i-built-an-autonomous-ai-agent-team-that-runs-24-7)

**Modelo de orquestração:**
- Gateway WebSocket central (`ws://127.0.0.1:18789`) como processo persistente
- Multi-canal: 20+ plataformas de messaging (WhatsApp, Telegram, Slack, Discord, Signal, iMessage)
- Routing por workspace/sessão → cada canal pode ter agente dedicado
- Cross-agent messaging via `sessions_*` tools
- **Cron-based scheduling:** agentes executam em horários definidos (ex: pesquisa às 8h, drafts às 9h e 13h)
- **Heartbeat self-healing:** monitor verifica `lastRunAtMs` de cada job; se >26h stale, força re-execução

**Composição:**
- Device nodes (macOS, iOS, Android) como extensões do gateway
- Skills platform para funcionalidades extras
- Cron jobs e webhooks para automação
- Browser control via Chrome dedicado
- **SOUL.md por agente** — 40-60 linhas definindo identidade, role, princípios, relacionamentos com outros agentes (análogo a AgentSpec)

**Coordenação inter-agente (caso real com 6 agentes):**
- **Filesystem como barramento de coordenação** — sem APIs entre agentes, sem message queues
- Pattern **one-writer, many-readers**: agente de pesquisa escreve `intel/DAILY-INTEL.md`, agentes de conteúdo leem
- Ordem de execução importa: pesquisa roda primeiro porque todos dependem do output
- Agente coordenador (Monica/Chief of Staff) faz routing de tarefas ad-hoc via Telegram

**Memória e persistência:**
- **Daily logs:** `memory/YYYY-MM-DD.md` — notas brutas do dia
- **Long-term memory:** `MEMORY.md` — insights destilados dos logs diários
- **Memory distillation:** durante heartbeats, agentes destilam logs em MEMORY.md (feedback loop que acumula ao longo de semanas)
- Context management: carrega apenas today + yesterday para evitar overflow

**Human-in-the-Loop:**
- Telegram como interface primária — agentes enviam drafts, humano aprova/rejeita no chat
- Feedback corretivo armazenado em memória → comportamento persiste entre sessões
- Review matinal de ~10 min: pesquisa, tweets, posts LinkedIn pré-preparados para aprovação

**Paralelismo:**
- Implícito — múltiplas sessões simultâneas por natureza do gateway
- Sem orquestração de tarefas paralelas dentro de uma sessão
- Paralelismo é por scheduling (agentes rodando em horários diferentes), não por coordenação runtime

**Forças:** Modelo de hub pessoal é único, 20+ integrações de canal, **operação 24/7 validada em produção**, self-healing via heartbeat, memória de longo prazo com distillation
**Fraquezas:** Não é um framework de orquestração — é um produto. Coordenação é por filesystem (frágil para cenários complexos). Sem composição formal de agentes. Sem type safety.

**Relevância para MiniAutoGen:** OpenClaw valida patterns que MiniAutoGen deveria absorver:

| Pattern OpenClaw (validado) | Equivalente MiniAutoGen | Status |
|---|---|---|
| SOUL.md (identidade do agente) | AgentSpec | ✅ Existe |
| Filesystem como coordenação | EventSink + Conversation | ✅ Superior (tipado) |
| Cron scheduling + heartbeat | Nenhum | ❌ **Gap** — sem scheduler nativo |
| Memory distillation (daily → long-term) | Nenhum | ❌ **Gap** — sem memory lifecycle |
| Telegram como HITL | ApprovalGate (binário) | ⚠️ Parcial — precisa HumanInputInterceptor |
| One-writer, many-readers | Conversation (imutável) | ✅ Superior (imutável by design) |

---

### 2.4 ChatDev 2.0 (OpenBMB)

**Categoria:** Multi-Agent Platform (role-playing software development)

**Modelo de orquestração:**
- Agentes com roles (CEO, CTO, Programmer, Reviewer, Designer)
- **Chat Chains:** sequências de "functional seminars" entre pares de agentes
- **Phases:** etapas macro (Design → Coding → Testing → Documentation)
- YAML-driven: workflows definidos em templates YAML
- "Evolving Orchestration" (NeurIPS 2025): orquestrador central aprendível

**Composição:**
- YAML templates com interpolação de variáveis (`${VAR}`)
- Nós no canvas visual (web UI)
- Custom tools via `functions/` directory
- MCP integration para ferramentas externas

**Paralelismo:**
- **Não explícito na documentação.** Phases são sequenciais.
- Chat chains dentro de phases parecem ser sequenciais (pares de agentes conversam)
- "Broadcast" para todos os membros possível no 2.0

**Forças:** Pesquisa acadêmica sólida (NeurIPS), UI visual, YAML-driven, role-playing intuitivo
**Fraquezas:** Acoplado ao domínio de software development, phases rígidas, sem interceptors

**Relevância para MiniAutoGen:** O conceito de **"Evolving Orchestration"** (orquestrador que aprende a sequenciar agentes) é relevante para o futuro. MiniAutoGen poderia ter um `AdaptiveRouter` como extensão do AgenticLoopRuntime. O YAML-driven config é análogo ao `AgentSpec` do MiniAutoGen.

---

### 2.5 Agno (ex-Phidata)

**Categoria:** Multi-Agent Platform / Framework SDK

**Modelo de orquestração:**
- **3 níveis:** Agent → Team → Workflow
- **Team modes explícitos:**
  - `Route`: líder seleciona um agente para responder
  - `Coordinate`: líder delega e coordena múltiplos agentes
  - `Broadcast`: líder delega para TODOS os membros simultaneamente
- **Workflows:** Steps sequenciais, paralelos, loops, ou condicionais
- **Sub-teams:** Teams podem conter sub-teams (composição hierárquica)

**Composição:**
- Agents declarados com tools, instructions, knowledge
- Teams compostos por agents + mode de coordenação
- Workflows compostos por agents + teams + functions
- Callable factories para membros dinâmicos (com cache)

**Paralelismo:**
- Broadcast mode → fan-out para todos os membros
- Workflow parallel steps → execução simultânea
- "Multiple agents work simultaneously on independent subtasks"

**Human-in-the-Loop:**
- Runs podem pausar para aprovação e resumir depois
- Governança built-in: approval workflows, audit logs, guardrails

**Forças:** API limpa, 3 team modes cobrindo os patterns comuns, 100+ integrations, production-ready (FastAPI runtime)
**Fraquezas:** Sem interceptors/middleware, team modes são estáticos (escolhe um e usa), sem composição de modes dentro de um mesmo run

**Relevância para MiniAutoGen:** Agno é o **competidor mais direto**. Suas Team modes (Route/Coordinate/Broadcast) mapeiam para os runtimes do MiniAutoGen (AgenticLoop/Workflow/Deliberation). A diferença proposta é que MiniAutoGen com interceptors permitiria **combinar comportamentos** que no Agno são mutuamente exclusivos.

---

### 2.6 OpenHands (ex-OpenDevin)

**Categoria:** Coding Agent / Platform (com ambição multi-agente)

**Modelo de orquestração:**
- SDK Python como fundação ("composable Python library")
- Agente autônomo para desenvolvimento de software
- Multi-tier: SDK → CLI → GUI → Cloud → Enterprise
- "Scale to 1000s of agents in the cloud" (Enterprise)

**Composição:**
- Skills directory (`.agents/skills`)
- Integrations (Slack, Jira, Linear — Enterprise)
- SDK como building block para agentes customizados

**Paralelismo:**
- Escala horizontal (cloud/enterprise) — mais infra que orquestração
- Sem coordenação multi-agente visível na camada SDK

**Forças:** Ambição de escala (1000s de agentes), SDK well-designed, multi-tier deployment
**Fraquezas:** Multi-agente é feature enterprise (não open-source), sem coordenação sofisticada visível

**Relevância para MiniAutoGen:** O modelo **SDK → CLI → GUI** é exatamente o mesmo que MiniAutoGen está construindo (core → cli → tui). A diferença é que MiniAutoGen tem coordenação multi-agente real no SDK, enquanto OpenHands escala via instâncias independentes.

---

### 2.7 LangGraph (LangChain) — Análise Aprofundada

> Para análise completa de como superar o LangGraph, ver [docs/pt/plano-langgraph.md](pt/plano-langgraph.md)

**Categoria:** Multi-Agent Platform / Runtime de execução durável

**Modelo de orquestração:**
- Grafo de nós (agents/functions) + arestas (condicionais/fixas)
- State machine explícita com typed state
- Subgraphs para composição hierárquica com schemas compartilhados ou adaptados

**O que o LangGraph faz que poucos fazem (e MiniAutoGen ainda não):**

| Capacidade | Como funciona | Status MiniAutoGen |
|---|---|---|
| **Durable Execution** | Checkpoint transacional a cada step/superstep; crash-safe | ❌ CheckpointStore existe mas sem commit atômico por step |
| **Interrupts nativos** | `interrupt()` com payload JSON + retomada via `resume(thread_id, payload)` | ⚠️ ApprovalGate é binário, sem `resume_token` |
| **Time Travel (Replay/Fork)** | Replay do checkpoint N, fork com patch de estado, comparação de trajetórias | ❌ Não existe |
| **Schema Evolution** | Migração de state entre versões do grafo, mesmo com threads interrompidas | ❌ Não existe |
| **Persistence por thread** | Cada thread (conversa) tem seus checkpoints organizados | ⚠️ RunStore + CheckpointStore existem mas sem threading |
| **Pending writes** | Writes acumulados antes do commit do step | ❌ Não existe |

**O que o LangGraph NÃO faz bem (e MiniAutoGen pode superar):**

| Gap do LangGraph | Oportunidade MiniAutoGen |
|---|---|
| **Composição rígida** — extensão = redesenhar o grafo | Interceptors permitem extensão sem tocar no runtime |
| **Callbacks apenas observacionais** — não transformam fluxo | Interceptors transformam (before/after/on_routing) |
| **Acoplado ao ecossistema LangChain** — vendor lock | Protocol-based, provider-agnostic |
| **Side effects sem formalização** — recomenda idempotência mas não enforce | EffectPolicy + idempotency_key + effect journal |
| **Heterogeneidade de backends fraca** — focado em LLM calls | AgentDriver abstrai qualquer backend |
| **Fan-out estático** — branches definidos no grafo, não em runtime | Fan-out dinâmico via RouterDecision.next_agents |

**Paralelismo:** Fan-out estático (branches no grafo), join nodes
**Extensibilidade:** Nós customizados, callbacks (observacionais), subgraphs
**Forças:** Durable execution é best-in-class, persistência madura, time travel é diferencial real
**Fraquezas:** Grafo é rígido, extensão requer redesign, acoplamento LangChain, sem middleware transformativo

### 2.8 CrewAI — Referência

**Modelo:** Tasks declarativas + Agents com roles + Process (sequential/hierarchical)
**Paralelismo:** Async tasks (declarado na task config)
**Extensibilidade:** Custom tools, custom LLMs
**Fraqueza:** Sem hooks. Sem composição de modos. Process é fixo.

---

## 3. Matriz Comparativa Completa

### 3.1 Modelo de Orquestração

| Framework | Modelo | Multi-Agent | Composição |
|---|---|---|---|
| **Claude Code** | Single agent + tools | Subagents isolados | Hooks + MCP + Commands |
| **Kimi CLI** | Single agent + tools | Não | MCP + ACP |
| **OpenClaw** | Gateway + routing | Routing por sessão | Channels + Skills + Nodes |
| **ChatDev** | Role-playing + phases | Chat chains (pares) | YAML templates + canvas |
| **Agno** | Agent → Team → Workflow | 3 team modes | Declarativo + factories |
| **OpenHands** | SDK + agent autônomo | Escala horizontal (enterprise) | Skills + integrations |
| **LangGraph** | Grafo de nós + arestas | Nós são agentes | Grafo declarativo |
| **CrewAI** | Tasks + Agents + Process | Sequential/Hierarchical | Declarativo + tools |
| **MiniAutoGen** | Runtimes tipados + PipelineRunner | 4 runtimes + composite | Protocols + specs |
| **MiniAutoGen (proposta)** | + Interceptors composáveis | + Fan-out dinâmico | + Middleware transformativo |

### 3.2 Paralelismo

| Framework | Fan-out Estático | Fan-out Dinâmico | Dentro de Loop | Estratégia de Agregação |
|---|---|---|---|---|
| **Claude Code** | Subagents manuais | Não | Não | Não |
| **Kimi CLI** | Não | Não | Não | Não |
| **OpenClaw** | Sessões paralelas | Não | Não | Não |
| **ChatDev** | Broadcast (2.0) | Não | Não | Não |
| **Agno** | Broadcast mode | Não | Não | Líder agrega |
| **OpenHands** | Instâncias independentes | Não | Não | Não |
| **LangGraph** | Branches no grafo | Não | Não | Join node |
| **CrewAI** | Async tasks | Não | Não | Não |
| **MiniAutoGen** | WorkflowRuntime parallel | Não (ainda) | Não (ainda) | Synthesis agent |
| **MiniAutoGen (proposta)** | WorkflowRuntime parallel | **RouterDecision.next_agents** | **Interceptor + task group** | **ResultAggregatorInterceptor** |

### 3.3 Extensibilidade / Middleware

| Framework | Hooks/Events | Middleware Transformativo | Interceptors no Runtime |
|---|---|---|---|
| **Claude Code** | Hooks (shell commands) | Não | Não |
| **Kimi CLI** | Não | Não | Não |
| **OpenClaw** | Webhooks | Não | Não |
| **ChatDev** | Não | Não | Não |
| **Agno** | Guardrails (validação) | Não | Não |
| **OpenHands** | Não documentado | Não | Não |
| **LangGraph** | Callbacks (observacionais) | Não | Não |
| **CrewAI** | Não | Não | Não |
| **MiniAutoGen** | EventSink (47+ tipos) | Não (ainda) | Não (ainda) |
| **MiniAutoGen (proposta)** | EventSink (47+ tipos) | **Sim (interceptors transformam fluxo)** | **Sim (before/after/on_routing)** |

### 3.4 Human-in-the-Loop

| Framework | Tipo | Riqueza |
|---|---|---|
| **Claude Code** | Input natural no terminal | ★★★★★ (conversa livre) |
| **Kimi CLI** | Input natural no terminal | ★★★★ |
| **OpenClaw** | Chat multi-canal | ★★★★★ (20+ canais) |
| **ChatDev** | Feedback em fases | ★★★ |
| **Agno** | Pause/approve/resume | ★★★★ |
| **OpenHands** | GUI + CLI input | ★★★★ |
| **LangGraph** | Breakpoints no grafo | ★★★ |
| **CrewAI** | human_input flag na task | ★★ |
| **MiniAutoGen** | ApprovalGate (approve/deny) | ★★ |
| **MiniAutoGen (proposta)** | + HumanInputInterceptor | ★★★★ (input livre via interceptor) |

### 3.5 Durable Execution & Runtime Maturity

> Dimensão derivada da análise em [docs/pt/plano-langgraph.md](pt/plano-langgraph.md)

Esta é a dimensão onde o LangGraph lidera o mercado e onde MiniAutoGen tem o maior gap técnico a fechar.

| Capacidade | LangGraph | Agno | CrewAI | ChatDev | MiniAutoGen (atual) | MiniAutoGen (alvo) |
|---|---|---|---|---|---|---|
| **Checkpoint por step** | ✅ Transacional | ⚠️ Session-level | ❌ | ❌ | ⚠️ RunStore genérico | ✅ CheckpointManager atômico |
| **Interrupt/Resume** | ✅ `interrupt()` + `resume()` | ✅ Pause/resume | ❌ | ❌ | ⚠️ ApprovalGate binário | ✅ InterruptManager + ResumeController |
| **Replay/Fork** | ✅ Time travel | ❌ | ❌ | ❌ | ❌ | ✅ Replay + fork com lineage |
| **Schema Evolution** | ✅ Migration | ❌ | ❌ | ❌ | ❌ | ✅ Schema migrators |
| **Side Effect Policy** | ⚠️ Recomendação | ❌ | ❌ | ❌ | ❌ | ✅ EffectPolicy + idempotency |
| **Run State Machine** | ✅ Implícita | ⚠️ | ❌ | ❌ | ⚠️ RunStatus (4 estados) | ✅ 10 estados formais |
| **Deterministic Replay** | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ Effect journal + dedup |

**Tese estratégica (do plano LangGraph):**

> Para o MiniAutoGen ficar mais maduro que o LangGraph, ele não deve competir em "mais abstrações de agente", e sim em **qualidade de runtime**. A aposta vencedora é transformar o MiniAutoGen em um **microkernel de execução agentic, stateful, replayable, interruptible, composable e provider-agnostic**.

O LangGraph vence hoje em durable execution. MiniAutoGen pode superar em:
1. **Composição mais limpa** (interceptors vs redesenhar grafo)
2. **Semântica operacional mais explícita** (EffectPolicy, idempotency_key)
3. **Heterogeneidade de backends** (AgentDriver vs LangChain-only)

---

## 4. Gaps e Oportunidades Estratégicas

### 4.1 O que NINGUÉM faz bem

| Oportunidade | Quem tenta | Problema | MiniAutoGen pode? |
|---|---|---|---|
| **Fan-out dinâmico dentro de loops** | Ninguém | Todos fazem fan-out estático ou fora do loop | **Sim — interceptor + RouterDecision.next_agents** |
| **Middleware transformativo em runtime** | Ninguém (LangGraph tem callbacks, mas observacionais) | Ninguém transforma o fluxo em runtime, só observa | **Sim — interceptors before/after/on_routing** |
| **Composição de modos de coordenação** | MiniAutoGen (CompositeRuntime) | Agno tem 3 modes mas são mutuamente exclusivos | **Sim — já existe e pode expandir** |
| **Contratos tipados + protocols** | Ninguém no nível do MiniAutoGen | Agno tem types mas não Protocols formais | **Sim — já é diferencial** |

### 4.2 O que outros fazem e MiniAutoGen NÃO faz (ainda)

| Capacidade | Quem faz | Impacto |
|---|---|---|
| **UI visual para composição** | ChatDev (canvas), LangGraph Studio | Alto para adoção |
| **100+ integrations** | Agno | Alto para time-to-value |
| **Production runtime (FastAPI)** | Agno | Alto para deploy |
| **Operação 24/7 (scheduler + self-healing)** | OpenClaw (cron + heartbeat) | Alto para produção |
| **Memory lifecycle (daily → long-term)** | OpenClaw (memory distillation) | Alto para agentes de longa duração |
| **Evolving Orchestration (aprendível)** | ChatDev (pesquisa) | Médio — futuro |
| **ACP protocol** | Kimi CLI | Médio — interop |

### 4.3 Patterns Validados em Produção (caso OpenClaw 24/7)

> Fonte: [The Unwind AI — "How I Built an Autonomous AI Agent Team That Runs 24/7"](https://www.theunwindai.com/p/how-i-built-an-autonomous-ai-agent-team-that-runs-24-7)

Este case study documenta 6 agentes especializados rodando 24/7 em produção real (~$400/mês). Os patterns observados validam decisões do MiniAutoGen e revelam gaps:

**Patterns que VALIDAM a arquitetura MiniAutoGen:**

| Pattern observado | Lição | MiniAutoGen |
|---|---|---|
| Single agent → specialized team | Um agente genérico produz "mediocre everything"; agentes especializados com roles claros são superiores | ✅ AgentSpec com role/goal/backstory |
| "Constraints make agents better" | Jobs singulares + stop conditions > agentes generalistas | ✅ Limits (max_turns, timeout) |
| Ordem de execução importa | Pesquisa roda antes de conteúdo (dependência sequencial) | ✅ WorkflowRuntime (steps ordenados) |
| One-writer, many-readers | Evita conflitos sem locks | ✅ Conversation imutável |
| SOUL.md ≈ AgentSpec | Identidade declarativa por arquivo funciona em produção | ✅ AgentSpec já faz isso |

**Patterns que revelam GAPS no MiniAutoGen:**

| Pattern observado | Lição | Gap MiniAutoGen | Recomendação |
|---|---|---|---|
| **Cron + heartbeat = 24/7** | Agentes precisam de scheduler nativo, não apenas execução on-demand | Sem scheduler | Adicionar `SchedulerService` ao runtime |
| **Memory distillation** | Daily logs → curated MEMORY.md (feedback loop acumulativo ao longo de semanas) | Sem memory lifecycle | Adicionar `MemoryDistiller` como policy lateral |
| **Corrective feedback persists** | "No emojis" dito uma vez → comportamento muda permanentemente | AgentSpec é estático | Adicionar `adaptive_memory` ao MemoryConfig |
| **Chat como HITL** | Telegram para aprovar/rejeitar/dar feedback em texto livre | ApprovalGate é binário | HumanInputInterceptor (já no roadmap) |
| **Filesystem como barramento** | Simples mas funciona para coordenação assíncrona | EventSink é síncrono ao run | Considerar `AsyncEventBus` para coordenação cross-flow |

**Insight estratégico:** O artigo demonstra que **operação contínua** (24/7, cron, self-healing) é tão importante quanto **orquestração sofisticada** (runtimes, interceptors). MiniAutoGen foca na segunda mas ignora a primeira. Um framework que oferece ambos — coordenação elegante E operação durável — é mais valioso que um que só faz uma.

---

## 5. Posicionamento Estratégico

### Onde MiniAutoGen pode vencer

```
                    Flexibilidade de Composição
                            ▲
                            │
                    MiniAutoGen (proposta)
                            │
              ChatDev ──────┼────── Agno
                            │
              CrewAI ───────┼────── LangGraph
                            │
                            │
         ───────────────────┼──────────────────► Robustez / Type Safety
                            │
              OpenHands ────┼────── Claude Code
                            │
              Kimi CLI ─────┼────── OpenClaw
                            │
```

**Quadrante alvo:** Alta flexibilidade de composição + Alta robustez/type safety. **Nenhum framework ocupa este quadrante hoje.**

- **Agno** tem boa composição mas types fracos
- **LangGraph** tem boa robustez mas composição rígida (grafo estático)
- **MiniAutoGen (proposta)** com interceptors + protocols + runtimes tipados seria único

### 5.2 A Mudança Tectônica do Mercado

O mercado de agentes convergiu para dois extremos — e ambos têm um problema estrutural:

**Extremo 1 — Agentes monolíticos cada vez mais poderosos:**

Claude Code, Kimi CLI, OpenHands. O agente único que faz tudo: lê código, executa shell, navega web, spawna subagentes de si mesmo. A tendência é o agente ser **o** runtime — skills, hooks, MCP servers, tudo vive dentro do agente. Claude Code com seu sistema de hooks, subagents em worktrees, e MCP é o melhor exemplo: um agente que é uma plataforma.

**Problema:** Não orquestra múltiplos providers. Claude Code só spawna Claudes. Kimi CLI só spawna Kimis. Cada um é um silo.

**Extremo 2 — Frameworks que tentam recriar o agente do zero:**

LangGraph, CrewAI, Agno. Constroem agentes internos com prompts, tools, memory — reinventando o que Claude/GPT/Gemini já fazem nativamente.

**Problema:** Agentes de framework são mais fracos que os nativos. Um "agente" do CrewAI com um system prompt e uma lista de tools é infinitamente menos capaz que o Claude Code com seus 47+ tools nativos, context de 200k, e capacidade de raciocínio autônomo. O framework adiciona overhead sem adicionar inteligência.

**O buraco no mercado:**

```
Agentes monolíticos                    Frameworks que recriam agentes
(Claude Code, Kimi, OpenHands)          (LangGraph, CrewAI, Agno)
┌─────────────────────┐               ┌─────────────────────┐
│ Agente poderoso      │               │ Framework            │
│ mas isolado          │               │  └── Agente fraco   │
│ (só usa a si mesmo)  │               │      (reinventado)   │
└─────────────────────┘               └─────────────────────┘
         │                                       │
         │         ┌─────────────────┐           │
         └────────►│  MiniAutoGen    │◄──────────┘
                   │                 │
                   │  Não reinventa  │
                   │  o agente.      │
                   │                 │
                   │  Orquestra      │
                   │  agentes reais  │
                   │  de qualquer    │
                   │  provider.      │
                   └─────────────────┘
```

Ninguém faz o meio: **pegar agentes que já são poderosos e orquestrá-los como participantes de um runtime customizado.**

### 5.3 A Tese Estratégica do MiniAutoGen

**O agente é commodity. O runtime é o produto.**

Claude é melhor que qualquer agente que um framework consiga construir. GPT também. Gemini também. Cada novo release os torna mais capazes. Competir na qualidade do agente é uma corrida perdida — os providers investem bilhões nisso.

**O valor está em como agentes de diferentes providers trabalham juntos.** E é aqui que o MiniAutoGen se posiciona:

```
MiniAutoGen não compete com:              MiniAutoGen compete com:
┌──────────────────────────┐             ┌──────────────────────────┐
│ Claude Code (agente)      │             │ A cola que junta agentes │
│ GPT (agente)              │             │ de providers diferentes  │
│ Gemini (agente)           │             │ num runtime customizado  │
│ Qualquer LLM (agente)    │             │ com regras formais       │
└──────────────────────────┘             └──────────────────────────┘
     ↓ estes são INPUTS                       ↑ isto é o PRODUTO
```

**O AgentDriver é a abstração central.** Tudo o mais — interceptors, policies, coordination modes — são formas de compor o que os drivers expõem:

```
Runtime customizado (Flow)
├── Coordination Mode (como colaboram)
│   ├── WorkflowPlan, AgenticLoopPlan, DeliberationPlan, CompositePlan
│
├── Interceptors (o que acontece entre turns)
│   ├── ContentBasedRerouter, HumanInputInterceptor, BudgetGuard...
│
├── Policies (regras laterais)
│   ├── RetryPolicy, BudgetPolicy, TimeoutPolicy, EffectPolicy...
│
└── Participants (quem executa) ← O DIFERENCIAL
    ├── Claude via AgentAPIDriver (API nativa)
    ├── GPT via AgentAPIDriver (API nativa)
    ├── Gemini via GeminiCLIDriver (gateway local)
    ├── Ollama/vLLM via AgentAPIDriver (modelos locais)
    ├── Agente custom via AgentDriver (qualquer implementação)
    └── Outro MiniAutoGen runtime via CoordinatorCapability (recursão)
```

Cada participant mantém suas capacidades nativas (tools, memory, code interpreter) — o MiniAutoGen não as reinventa, apenas coordena.

### 5.4 Proposta de Valor Diferenciada (atualizada)

> **MiniAutoGen: o runtime que orquestra agentes de qualquer provider em flows customizados com interceptors composáveis, policies formais, e coordenação tipada — sem reinventar o agente.**

**Os 5 pilares:**
1. **Multi-provider nativo** — AgentDriver abstrai Claude, GPT, Gemini, modelos locais, agentes custom
2. **Runtime customizável** — Interceptors + Policies + Coordination Modes composáveis
3. **O agente é o que ele já é** — não enfraquece reinventando; cada provider expõe suas capacidades nativas
4. **Contratos tipados** — Protocols + Pydantic garantem segurança na composição
5. **Operação contínua** — Scheduler + MemoryDistiller + self-healing para agentes 24/7

---

## 6. Roadmap Estratégico Integrado

> Combina insights da análise competitiva com o plano de evolução LangGraph ([docs/pt/plano-langgraph.md](pt/plano-langgraph.md))

### Fase 1 — Diferencial Imediato + Onboarding (o que ninguém tem + porta de entrada)

Objetivo: criar as capacidades únicas E garantir que novos usuários consigam experimentá-las em minutos.

| # | Entrega | Justificativa competitiva | Origem |
|---|---|---|---|
| 1 | **RuntimeInterceptor protocol** | Único framework com middleware transformativo em runtimes agênticos | Análise competitiva |
| 2 | **Fan-out dinâmico** (`RouterDecision.next_agents`) | Paralelismo decidido em runtime, não em design-time | Análise competitiva |
| 3 | **ResultAggregator** (all, race, quorum, vote) | Estratégias de merge configuráveis — nenhum concorrente tem | Análise competitiva |
| 4 | **Quickstart mode** | API simplificada para "2 agentes conversando" em 5 min — sem isso nenhum diferencial importa | **v0 insight** (era usável em 5 min) |

> **Por que Quickstart subiu para Fase 1:** O v0 do MiniAutoGen era compreensível em 15 minutos. A arquitetura atual exige 30+ min para um hello world. Se o developer não consegue experimentar rápido, nunca chega a conhecer os diferenciais. Quickstart é pré-requisito de adoção, não feature de conforto.

### Fase 2 — Runtime Durável + Composição Vertical (empatar com LangGraph, recuperar v0)

Objetivo: fechar o gap de durable execution E restaurar o insight mais inovador da arquitetura original.

| # | Entrega | O que supera | Origem |
|---|---|---|---|
| 5 | **RunStateMachine** (10 estados formais) | LangGraph tem implícita; MiniAutoGen terá explícita | plano-langgraph.md |
| 6 | **CheckpointManager transacional** (commit atômico por step) | Empata com LangGraph, supera todos os outros | plano-langgraph.md |
| 7 | **InterruptManager** + **ResumeController** | Interrupt com payload tipado + `resume_token` + timeout + fallback | plano-langgraph.md |
| 8 | **HumanInputInterceptor** (input livre, seleção) | Supera LangGraph (breakpoints) e Agno (pause/approve) | **v0 insight** (UserResponseComponent + UserInputNextAgent) |
| 9 | **CoordinatorCapability** — agente que orquestra sub-runtimes | Recupera composição recursiva; CrewAI tem managers mas sem type safety | **v0 insight** (ChatAdmin extends Agent) |

> **Por que CoordinatorCapability é Fase 2:** No v0, `ChatAdmin` era um Agent que coordenava outros Agents — recursão natural. Isso se perdeu na refatoração. É o insight arquitetural mais profundo do v0 e um diferencial real: nenhum framework combina orquestrador-como-agente com contratos tipados. A implementação é um Protocol que permite a qualquer `AgentSpec` com capability `coordinator` instanciar `CoordinationPlan` e executar sub-runtimes dentro do runtime pai:
>
> ```python
> class CoordinatorCapability(Protocol):
>     """Agente que pode instanciar e executar sub-runtimes."""
>     async def coordinate(
>         self, plan: CoordinationPlan, ctx: RunContext
>     ) -> RunResult: ...
> ```
>
> Isso restaura a composição vertical (agente → sub-runtime → sub-agentes) que o v0 tinha naturalmente via `ChatAdmin(Agent)`.

### Fase 3 — Superar LangGraph + Operação Contínua (vantagem estrutural)

Objetivo: ir onde o LangGraph não vai por limitação de arquitetura, E habilitar operação 24/7.

| # | Entrega | Por que LangGraph não pode fazer | Origem |
|---|---|---|---|
| 10 | **Replay/Fork com lineage** | LangGraph tem time travel; MiniAutoGen terá com lineage metadata completo | plano-langgraph.md |
| 11 | **EffectPolicy** + idempotency_key + effect journal | LangGraph recomenda idempotência mas não enforce | plano-langgraph.md |
| 12 | **Schema evolution** com migrators | LangGraph tem mas é limitado; MiniAutoGen pode ser mais robusto | plano-langgraph.md |
| 13 | **Production runtime** (FastAPI wrapper) | Paridade com Agno, supera LangGraph (que depende de LangServe) | Análise competitiva |
| 14 | **AssistantsBackendDriver** | Backend com memória/tools/code interpreter server-side via AgentDriver | **v0 insight** (OpenAIThreadComponent) |
| 15 | **SchedulerService** (cron + heartbeat self-healing) | Nenhum framework multi-agente tem scheduler nativo com self-healing | **OpenClaw 24/7 case** |
| 16 | **MemoryDistiller** (daily → long-term memory lifecycle) | Nenhum framework trata memory lifecycle como policy do runtime | **OpenClaw 24/7 case** |

> **Por que Scheduler e MemoryDistiller são Fase 3:** O [caso documentado de 6 agentes rodando 24/7](https://www.theunwindai.com/p/how-i-built-an-autonomous-ai-agent-team-that-runs-24-7) demonstra que **operação contínua é tão importante quanto orquestração sofisticada**. O scheduler com heartbeat self-healing (>26h stale → force re-run) e a destilação de memória (daily logs → curated MEMORY.md) são os dois patterns que permitem agentes operar por semanas sem degradação. Nenhum framework do segmento multi-agent (LangGraph, Agno, CrewAI) oferece isso — é um gap de mercado real.

> **Por que AssistantsBackendDriver é Fase 3:** O v0 tinha `OpenAIThreadComponent` com integração direta à Assistants API (threads, runs, file retrieval). O `AgentDriver` protocol atual já comporta a abstração, mas o driver concreto nunca foi implementado. Assistants API oferece memória server-side, code interpreter e file search como built-ins — são capacidades valiosas que se expõem naturalmente via `BackendCapabilities(sessions=True, tools=True, artifacts=True)`.

### Fase 4 — Vantagem Futura

Objetivo: diferenciais de próxima geração.

| # | Entrega | Inspiração |
|---|---|---|
| 17 | **AdaptiveRouter** (router que aprende) | ChatDev "Evolving Orchestration" (NeurIPS 2025) |
| 18 | **ACP compatibility** | Kimi CLI — convergência de protocols é tendência |
| 19 | **Visual composer** | ChatDev canvas + LangGraph Studio — crítico para adoção |

### Rastreabilidade: Insights por Origem

> Para análise completa das features perdidas do v0, ver [docs/architecture-retrospective.md](architecture-retrospective.md)

**Insights da arquitetura v0 (recuperados):**

| Insight v0 | Entrega | Fase | Como volta |
|---|---|---|---|
| **ChatAdmin extends Agent** (composição recursiva) | #9 CoordinatorCapability | Fase 2 | Protocol tipado que permite agente instanciar sub-runtimes |
| **UserResponseComponent + UserInputNextAgent** (HITL rico) | #8 HumanInputInterceptor | Fase 2 | Interceptor com input livre + seleção de agente |
| **NextAgentMessageComponent** (routing por conteúdo) | #1 RuntimeInterceptor | Fase 1 | `ContentBasedRerouter` como interceptor no `on_routing` |
| **13 Flow Components** (composição em blocos) | #1 RuntimeInterceptor | Fase 1 | Interceptors são os novos "blocos LEGO" — composáveis nos runtimes |
| **ChatPipelineState** (comunicação ad-hoc) | #11 EffectPolicy + scratchpad | Fase 3 | `RunContext.scratchpad` mutável + EffectPolicy para controle |
| **OpenAIThreadComponent** (Assistants API) | #14 AssistantsBackendDriver | Fase 3 | Driver concreto que implementa AgentDriver para Assistants API |
| **Agent.from_json()** (setup em 5 min) | #4 Quickstart mode | Fase 1 | API simplificada que esconde maquinaria para o caso comum |

**Insights do caso OpenClaw 24/7 (novos):**

| Pattern produção | Entrega | Fase | O que resolve |
|---|---|---|---|
| **Cron + heartbeat self-healing** | #15 SchedulerService | Fase 3 | Agentes rodando 24/7 sem intervenção humana |
| **Memory distillation** (daily → long-term) | #16 MemoryDistiller | Fase 3 | Agentes que melhoram com o tempo sem fine-tuning |
| **Corrective feedback persists** | #16 MemoryDistiller | Fase 3 | "No emojis" dito uma vez → comportamento muda permanentemente |
| **Telegram como HITL** | #8 HumanInputInterceptor | Fase 2 | Chat como interface de aprovação e feedback |
| **SOUL.md por agente** | AgentSpec | — | ✅ Já existe — validado em produção |
| **Constraints make agents better** | Limits (max_turns, timeout) | — | ✅ Já existe — validado em produção |

### Mapa de Dependências (atualizado)

```
Fase 1 (Diferencial + DX)     Fase 2 (Durable + v0)        Fase 3 (Superar + 24/7)      Fase 4 (Futuro)
┌─────────────────┐     ┌───────────────────────┐    ┌───────────────────────┐   ┌──────────────────┐
│ 1. Interceptors ├────►│ 8. HumanInput         │    │ 10. Replay/Fork       │   │ 17. AdaptiveRouter│
│ 2. Fan-out      │     │    (usa interceptor)   │    │     (usa checkpoint)  │   │ 18. ACP          │
│ 3. Aggregator   │     │ 9. Coordinator [v0]    │    │ 11. EffectPolicy      │   │ 19. Visual       │
│ 4. Quickstart   │     ├───────────────────────┤    │ 12. Schema Evolution  │   └──────────────────┘
│    [v0]         │     │ 5. StateMachine       ├───►│ 13. FastAPI Runtime   │
└─────────────────┘     │ 6. CheckpointMgr      │    │ 14. AssistantsDriver  │
                        │ 7. InterruptMgr       │    │     [v0]              │
                        └───────────────────────┘    │ 15. Scheduler [24/7]  │
                                                     │ 16. MemoryDistiller   │
                                                     │     [24/7]            │
                                                     └───────────────────────┘

                        [v0] = insight recuperado da arquitetura original
                        [24/7] = insight do caso OpenClaw em produção
```

---

## 7. Síntese Final

### A mudança de paradigma

O mercado ensinou duas lições:
1. **Agentes monolíticos** (Claude Code, Kimi) ficam cada vez mais poderosos — tentar recriar o agente é uma corrida perdida
2. **Frameworks que reinventam o agente** (CrewAI, LangGraph) criam agentes mais fracos que os nativos — adicionam overhead sem inteligência

O MiniAutoGen se posiciona no **meio inexplorado**: não compete com o agente, orquestra agentes reais de qualquer provider. O AgentDriver é a abstração central; tudo o mais são formas de compor o que os drivers expõem.

### Posição competitiva atual

MiniAutoGen já tem vantagens estruturais reais:
- **Contratos tipados** (Protocols + Pydantic) — nenhum concorrente tem no mesmo nível
- **Composição de modos de coordenação** (CompositeRuntime) — exclusivo
- **AgentDriver como abstração multi-provider** — qualquer backend converge no mesmo protocol
- **Neutralidade de provider** — não é acoplado a nenhum ecossistema (vs LangGraph/LangChain)

### Gaps críticos

1. **Durable execution** — LangGraph lidera. Sem Fase 2 (StateMachine, Checkpoint, Interrupt), MiniAutoGen não é production-ready
2. **Operação contínua** — caso OpenClaw 24/7 demonstra que scheduler + memory lifecycle são essenciais. Sem #15-#16, é um framework on-demand, não um runtime autônomo
3. **Onboarding** — curva de aprendizado alta. Sem Quickstart (#4), ninguém chega a experimentar os diferenciais

### A refatoração como ativo

A arquitetura v0 tinha 3 insights perdidos na refatoração. O roadmap recupera todos — não como nostalgia, mas modernizados:
- ChatAdmin → **CoordinatorCapability** com type safety (Fase 2, #9) — um Claude coordena GPTs e Geminis como sub-runtime
- UserResponseComponent → **HumanInputInterceptor** com payload tipado (Fase 2, #8)
- Agent.from_json() → **Quickstart mode** (Fase 1, #4)

A refatoração criou a infraestrutura (Protocols, Runtimes, Events, AgentDriver) que permite implementar esses insights de forma **mais robusta** do que o v0 jamais poderia — e com a dimensão multi-provider que o v0 não tinha.

### Por que ninguém pode copiar facilmente

A combinação de:

| Pilar | O que faz | Por que é difícil de copiar |
|---|---|---|
| **AgentDriver multi-provider** | Abstrai qualquer agente de qualquer provider | Requer arquitetura protocol-first desde o dia zero |
| **Interceptors composáveis** | Customiza runtime sem tocar nos agentes | Requer que o runtime seja extensível por design, não por afterthought |
| **Coordination Modes + Composite** | Sequencia modos diferentes no mesmo flow | Requer runtimes como primitivas composáveis, não grafos monolíticos |
| **Contratos tipados** | Type safety na composição multi-provider | Requer Protocols formais, não duck typing |
| **Durable execution** (roadmap) | Checkpoints, interrupt, replay, fork | Requer kernel-level design, não features bolted on |
| **Operação 24/7** (roadmap) | Scheduler + memory distillation + self-healing | Requer integração com o runtime, não um cron externo |

LangGraph teria que abandonar o modelo de grafo para ter interceptors. Agno teria que adicionar Protocols formais. CrewAI teria que reescrever do zero. Claude Code teria que se abrir para outros providers. Nenhum está posicionado para convergir no que o MiniAutoGen pode oferecer.

### Oportunidade única

> **MiniAutoGen: o runtime que orquestra agentes de qualquer provider em flows customizados — sem reinventar o agente.**

Cada provider (Claude, GPT, Gemini, modelos locais) mantém suas capacidades nativas. O MiniAutoGen adiciona:
- **Como trabalham juntos** → Coordination Modes composáveis
- **O que acontece entre turns** → Interceptors transformativos
- **Que regras aplicam** → Policies laterais tipadas
- **Que garantias operacionais têm** → Durable execution + scheduler + memory lifecycle
- **Quem pode coordenar quem** → CoordinatorCapability (agente orquestra sub-runtimes)

### A frase que resume

**O agente é commodity. O runtime é o produto. MiniAutoGen é o runtime.**

---

*Relatório gerado em 2025-06-18 | Baseado em pesquisa direta dos repositórios, documentação oficial, [architecture-retrospective.md](architecture-retrospective.md), [plano-langgraph.md](pt/plano-langgraph.md), e [caso OpenClaw 24/7](https://www.theunwindai.com/p/how-i-built-an-autonomous-ai-agent-team-that-runs-24-7)*
